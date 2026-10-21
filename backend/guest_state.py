"""Durable guest dialogue, dietary constraints, offer decisions and request replay.
Client history is never the authority for an existing server session.
"""
import asyncio
import hashlib
import json
import secrets
import time
import store

LOCKS={}
TTL=24*3600

def fingerprint(value):return hashlib.sha256(store.encode(value).encode()).hexdigest()

def init():
    with store.db() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS guest_dialogues (id TEXT PRIMARY KEY,payload TEXT NOT NULL,expires REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS guest_requests (session TEXT,request_id TEXT,digest TEXT,result TEXT,expires REAL,PRIMARY KEY(session,request_id));
        ''')

def key(token):return hashlib.sha256(token.encode()).hexdigest()

def create(table=None):
    token=secrets.token_urlsafe(32)
    state={'lang':None,'excludes':[],'diets':[],'budget':None,'history':[],'declined':False,'offered':[],'offer':None,'last_offer':0,'table':table}
    save(token,state);return token,state

def load(token):
    with store.db() as c:row=c.execute('SELECT payload FROM guest_dialogues WHERE id=? AND expires>?',(key(token),time.time())).fetchone()
    return json.loads(row['payload']) if row else None

def save(token,state):
    now=time.time()
    with store.db() as c:
        c.execute('INSERT OR REPLACE INTO guest_dialogues VALUES (?,?,?)',(key(token),store.encode(state),now+TTL))
        c.execute('DELETE FROM guest_dialogues WHERE expires<?',(now,))
        c.execute('DELETE FROM guest_requests WHERE expires<?',(now,))

def lock(token):
    now=time.monotonic()
    if len(LOCKS)>2000:
        for k,(l,ts) in list(LOCKS.items()):
            if not l.locked() and now-ts>300:LOCKS.pop(k,None)
    ident=key(token)
    if ident not in LOCKS:LOCKS[ident]=(asyncio.Lock(),now)
    obj=LOCKS[ident][0];LOCKS[ident]=(obj,now);return obj

def cached(token,rid,payload):
    with store.db() as c:r=c.execute('SELECT digest,result FROM guest_requests WHERE session=? AND request_id=? AND expires>?',(key(token),rid,time.time())).fetchone()
    if not r:return None
    if r['digest']!=fingerprint(payload):
        from fastapi import HTTPException
        raise HTTPException(409,'Этот request_id уже использован для другого сообщения')
    return json.loads(r['result'])

def remember(token,rid,payload,result):
    with store.db() as c:c.execute('INSERT OR REPLACE INTO guest_requests VALUES (?,?,?,?,?)',(key(token),rid,fingerprint(payload),store.encode(result),time.time()+TTL))
