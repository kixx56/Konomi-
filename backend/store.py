"""SQLite persistence. Secrets are encrypted; passwords are scrypt hashes."""
import hashlib
import hmac
import json
import logging
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from cryptography.fernet import Fernet, InvalidToken
from runtime import data_dir, production, validate_data_location

ROOT = Path(__file__).resolve().parent
DATA = data_dir()

def encode(value):
    return json.dumps(value, ensure_ascii=False)

@contextmanager
def db():
    conn = sqlite3.connect(DATA / 'konomi.db', timeout=15)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return salt + ':' + digest

def check_password(password, stored):
    salt = stored.split(':')[0]
    return hmac.compare_digest(password_hash(password, salt), stored)

def cipher():
    return Fernet((DATA / 'encryption.key').read_bytes())

def create_encryption_key(key):
    fd = os.open(key, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, 'wb') as f:f.write(Fernet.generate_key())

def init():
    validate_data_location()
    DATA.mkdir(parents=True, exist_ok=True, mode=0o700)
    key = DATA / 'encryption.key'
    if not key.exists():
        if (DATA / 'konomi.db').exists():
            if not (os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY') or os.getenv('OPENAI_API_KEY')):
                raise RuntimeError('Encryption key is missing beside an existing database. Restore encryption.key from the same backup; do not create a replacement.')
            logging.getLogger('konomi').warning('Encryption key missing; environment Gemini key available. Restore original encryption.key before saving encrypted secrets.')
        else:
            create_encryption_key(key)
    with db() as c:
        c.execute('PRAGMA journal_mode=WAL')
        c.executescript('''
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS admins (username TEXT PRIMARY KEY, password TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, username TEXT, expires REAL);
        CREATE TABLE IF NOT EXISTS dishes (id TEXT PRIMARY KEY, payload TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS imports (id TEXT PRIMARY KEY, payload TEXT NOT NULL, expires REAL);
        CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY, at REAL, action TEXT, detail TEXT);
        CREATE TABLE IF NOT EXISTS orders (id TEXT PRIMARY KEY, at REAL, payload TEXT NOT NULL);
        ''')
        if not c.execute('SELECT 1 FROM admins LIMIT 1').fetchone():
            if production() and not os.getenv('ADMIN_PASSWORD'):
                raise RuntimeError('First production launch requires ADMIN_PASSWORD (12+ characters) in service variables. No default production password is created.')
            password = os.getenv('ADMIN_PASSWORD') or secrets.token_urlsafe(18)
            if len(password) < 12:
                raise RuntimeError('ADMIN_PASSWORD must contain at least 12 characters')
            username = os.getenv('ADMIN_USERNAME', 'admin')
            c.execute('INSERT INTO admins VALUES (?,?)', (username, password_hash(password)))
            if not os.getenv('ADMIN_PASSWORD'):
                print(f'\nFIRST START: admin login = {username}\nTemporary password = {password}\nChange it in the admin panel.\n', flush=True)
        if not c.execute('SELECT 1 FROM dishes LIMIT 1').fetchone() and not c.execute("SELECT 1 FROM settings WHERE key='seeded'").fetchone():
            for d in json.loads((ROOT / 'menu.json').read_text('utf-8')):
                c.execute('INSERT INTO dishes VALUES (?,?,1)', (d['id'], encode(d)))
            c.execute("INSERT OR REPLACE INTO settings VALUES ('seeded','true')")

def dishes():
    with db() as c:
        return [dict(json.loads(r['payload']), version=r['version']) for r in c.execute('SELECT * FROM dishes ORDER BY rowid')]

def settings():
    with db() as c:values={r['key']:json.loads(r['value']) for r in c.execute('SELECT * FROM settings')}
    cfg={'model':os.getenv('GEMINI_MODEL','auto'),'openai_model':os.getenv('OPENAI_MODEL','gpt-4o-mini'),'ai_provider':os.getenv('AI_PROVIDER','auto'),'discount':15,'venue':os.getenv('VENUE_NAME','Restaurant'),'city':os.getenv('VENUE_CITY',''),'currency':os.getenv('VENUE_CURRENCY','PLN'),'tone':'warm, professional, helpful','latitude':None,'longitude':None,'timezone':'Europe/Warsaw',**values}
    cfg['combo_discount']=values.get('combo_discount',cfg['discount']);cfg['discount']=cfg['combo_discount']
    return cfg

KEY_STATE={'source':'none','storage_error':False}
def api_key(provider='gemini'):
    """Never leak ciphertext/errors. An environment key can recover an unreadable vault."""
    KEY_STATE.update(source='none',storage_error=False)
    try:
        encrypted=settings().get('openai_key' if provider=='openai' else 'gemini_key')
        if encrypted:
            value=cipher().decrypt(encrypted.encode()).decode().strip()
            if value:
                KEY_STATE['source']='store';return value
    except (OSError, ValueError, TypeError, UnicodeError, InvalidToken):
        KEY_STATE['storage_error']=True
    for name in (('OPENAI_API_KEY',) if provider=='openai' else ('GEMINI_API_KEY','GOOGLE_API_KEY')):
        value=os.getenv(name,'').strip()
        if value:KEY_STATE['source']=name;return value
    return ''

def audit(action, detail=''):
    with db() as c:
        c.execute('INSERT INTO audit (at,action,detail) VALUES (?,?,?)', (time.time(),action,detail))
