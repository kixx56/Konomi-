"""Offline recovery and coherent backups.
  python manage.py reset-password --user admin
  python manage.py backup
Only someone with access to the server filesystem should run these commands.
"""
import argparse
import getpass
import os
import sqlite3
import tempfile
import time
import zipfile
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name('.env'))
import store

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('action',choices=['reset-password','backup'])
parser.add_argument('--user',default='admin')
args=parser.parse_args()
store.init()
if args.action=='reset-password':
    password=getpass.getpass('New password (12+ characters): ')
    confirm=getpass.getpass('Confirm password: ')
    if len(password)<12 or password!=confirm:
        raise SystemExit('Passwords must match and contain at least 12 characters.')
    with store.db() as c:
        if not c.execute('UPDATE admins SET password=? WHERE username=?',(store.password_hash(password),args.user)).rowcount:
            raise SystemExit('Admin user not found.')
        c.execute('DELETE FROM sessions WHERE username=?',(args.user,))
    store.audit('password_changed','offline recovery')
    print('Password changed; all sessions revoked.')
else:
    target=store.ROOT.parent/'backups'
    target.mkdir(exist_ok=True,mode=0o700)
    output=target/('konomi-'+time.strftime('%Y%m%d-%H%M%S')+'.zip')
    with tempfile.TemporaryDirectory() as tmp:
        copy=Path(tmp)/'konomi.db'
        source=sqlite3.connect(store.DATA/'konomi.db')
        dest=sqlite3.connect(copy)
        source.backup(dest);dest.close();source.close()
        with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
            archive.write(copy,'konomi.db')
            archive.write(store.DATA/'encryption.key','encryption.key')
    os.chmod(output,0o600)
    print(f'Backup ready: {output}')
    print('Contains credentials and the encryption key. Store privately. Never send to guests.')
