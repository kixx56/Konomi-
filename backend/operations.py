"""Transactional staff approval, bearer-protected receipts and evidence-based analytics.
SQLite/WAL + BEGIN IMMEDIATE serialize approvals across requests. No external POS claim.
The kitchen board polls a persisted revision every two seconds; reconnects recover from DB.
"""
import hashlib
import hmac
import json
import secrets
import time
from collections import Counter, defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from typing import Literal
import store
import guest_state

ZONE=ZoneInfo('Europe/Warsaw')
STATES={'created':{'confirmed','cancelled'},'confirmed':{'ready','cancelled'},'ready':{'completed','cancelled'},'completed':set(),'cancelled':set()}
SALE={'confirmed','ready','completed'}

def sha(value):return hashlib.sha256(value.encode()).hexdigest()
def init():
    with store.db() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS order_control (
          id TEXT PRIMARY KEY REFERENCES orders(id), code TEXT UNIQUE NOT NULL,
          access_digest TEXT NOT NULL, visitor TEXT, fingerprint TEXT NOT NULL,
          version INTEGER NOT NULL DEFAULT 1, status TEXT NOT NULL,
          updated REAL NOT NULL, confirmed REAL, legacy INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS order_changes (
          seq INTEGER PRIMARY KEY AUTOINCREMENT, order_id TEXT NOT NULL,
          at REAL NOT NULL, old_status TEXT, new_status TEXT NOT NULL, actor TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS visitors (id TEXT PRIMARY KEY, at REAL NOT NULL, table_no INTEGER);
        CREATE TABLE IF NOT EXISTS events (
          id INTEGER PRIMARY KEY AUTOINCREMENT, at REAL NOT NULL, visitor TEXT NOT NULL,
          kind TEXT NOT NULL, detail TEXT NOT NULL, dedupe TEXT UNIQUE NOT NULL);
        CREATE TABLE IF NOT EXISTS upsell_conversions (offer_id TEXT PRIMARY KEY,order_id TEXT NOT NULL,item_ids TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS pin_attempts (identity TEXT PRIMARY KEY, started REAL, attempts INTEGER);
        CREATE INDEX IF NOT EXISTS events_at ON events(at);
        CREATE INDEX IF NOT EXISTS events_visitor ON events(visitor,kind);
        CREATE INDEX IF NOT EXISTS order_status ON order_control(status,updated);
        ''')
        # Old guest checks are not historic revenue. Keep them explicitly pending.
        for row in c.execute('SELECT id,at,payload FROM orders WHERE id NOT IN (SELECT id FROM order_control)').fetchall():
            d=json.loads(row['payload']);code=d.get('code') or 'GP-'+secrets.token_hex(3).upper()
            if c.execute('SELECT 1 FROM order_control WHERE code=?',(code,)).fetchone():code='GP-'+secrets.token_hex(6).upper()
            d.update(code=code,status='created',legacy=True,version=1)
            c.execute('UPDATE orders SET payload=? WHERE id=?',(store.encode(d),row['id']))
            c.execute('INSERT INTO order_control VALUES (?,?,?,?,?,1,?,?,NULL,1)',(row['id'],code,'','', '', 'created',row['at']))
        if not c.execute("SELECT 1 FROM settings WHERE key='hall_pin_hash'").fetchone():
            import os
            pin=os.getenv('HALL_PIN','').strip()
            if pin:
                if not pin.isascii() or not pin.isdigit() or not 4<=len(pin)<=8:raise RuntimeError('HALL_PIN must contain 4-8 digits')
                c.execute('INSERT INTO settings VALUES (?,?)',('hall_pin_hash',store.encode(store.password_hash(pin))))

def visitor(request,required=False):
    value=request.cookies.get('konomi_visit','')
    if value:
        with store.db() as c:row=c.execute('SELECT id FROM visitors WHERE id=?',(sha(value),)).fetchone()
        if row:return row['id']
    if required:raise HTTPException(409,'OPEN_MENU_FIRST')
    return None

def record(ident,kind,detail=None,dedupe=None,connection=None):
    if not ident:return
    values=(time.time(),ident,kind,store.encode(detail or {}),dedupe or secrets.token_hex(24))
    if connection:connection.execute('INSERT OR IGNORE INTO events(at,visitor,kind,detail,dedupe) VALUES (?,?,?,?,?)',values)
    else:
        with store.db() as c:c.execute('INSERT OR IGNORE INTO events(at,visitor,kind,detail,dedupe) VALUES (?,?,?,?,?)',values)

def note_chat(request,body,result):
    if body.event!='message':return
    ident=visitor(request)
    rid=result.get('request_id') or secrets.token_hex(16)
    prefs=__import__('dining').parse(body.message)
    named=[d['id'] for d in store.dishes() if d['name'].casefold() in body.message.casefold()]
    if not named and set(prefs.get('topics',[])) & {'DUCK','GOOSE','FISH','PORK','DUMPLINGS'}:
        choices=__import__('dining').select(__import__('dining').eligible(),prefs,{})
        if len(choices)==1:named=[choices[0]['id']]
    record(ident,'ai_chat',{'table':body.table,'engine':result['engine'],'topics':prefs.get('topics',[]),'dishes':result.get('dishes',[]),'excludes':sorted(prefs['excludes']),'requested_ids':named},f'chat:{ident}:{rid}')

def submit(body,request,quote_fn,now_iso):
    ident=visitor(request)
    signature=sha(store.encode(body.model_dump(exclude={'idempotency_key'})))
    token=secrets.token_urlsafe(32)
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        previous=c.execute('SELECT o.payload,k.* FROM orders o JOIN order_control k ON k.id=o.id WHERE o.id=?',(body.idempotency_key,)).fetchone()
        if previous:
            if previous['fingerprint']!=signature:raise HTTPException(409,'IDEMPOTENCY_CONFLICT')
            # An unguessable idempotency key is used only for retrying this exact checkout.
            if previous['visitor'] and previous['visitor']!=ident:raise HTTPException(404,'ORDER_NOT_FOUND')
            result=json.loads(previous['payload'])
            # Deterministic receipt capability derived from server secret, never a short check code.
            result['access_token']=receipt_token(body.idempotency_key)
            return result
        if body.session_id:
            state=guest_state.load(body.session_id)
            if not state:raise HTTPException(409,'GUEST_SESSION_EXPIRED')
            if state['table']!=body.table:raise HTTPException(409,'TABLE_CONTEXT_MISMATCH')
            body.excludes=sorted(set(body.excludes)|set(state['excludes']))
            body.diets=sorted(set(body.diets)|set(state['diets']))
        else:state={}
        quote=quote_fn(body)
        for _ in range(10):
            code='GP-'+secrets.token_hex(3).upper()
            if not c.execute('SELECT 1 FROM order_control WHERE code=?',(code,)).fetchone():break
        else:raise HTTPException(503,'CHECK_CODE_RETRY')
        token=receipt_token(body.idempotency_key)
        ai=bool(ident and c.execute("SELECT 1 FROM events WHERE visitor=? AND kind='ai_chat'",(ident,)).fetchone()) or bool(state.get('history'))
        accepted=state.get('offer') or {}
        ledger=dict(state.get('accepted_upsells',{}))
        if accepted.get('status')=='accepted':ledger.setdefault(accepted['id'],accepted.get('item_ids',[]))
        bought={i for line in body.lines for i in line.ids}
        upsell_ids=set()
        for offer_id,ids in ledger.items():
            converted=[i for i in ids if i in bought]
            if converted and not c.execute('SELECT 1 FROM upsell_conversions WHERE offer_id=?',(sha(offer_id),)).fetchone():
                c.execute('INSERT INTO upsell_conversions VALUES (?,?,?)',(sha(offer_id),body.idempotency_key,store.encode(converted)))
                upsell_ids.update(converted)
        upsell_ids=sorted(upsell_ids)
        result={**quote,'code':code,'status':'created','created_at':now_iso(),'table':body.table,'excludes':body.excludes,'diets':body.diets,'ai_assisted':ai,'upsell_ids':upsell_ids,'version':1}
        c.execute('INSERT INTO orders VALUES (?,?,?)',(body.idempotency_key,time.time(),store.encode(result)))
        c.execute('INSERT INTO order_control VALUES (?,?,?,?,?,1,?,?,NULL,0)',(body.idempotency_key,code,sha(token),ident,signature,'created',time.time()))
        c.execute('INSERT INTO order_changes(order_id,at,old_status,new_status,actor) VALUES (?,?,NULL,?,?)',(body.idempotency_key,time.time(),'created','guest'))
        record(ident,'check_created',{'table':body.table},'check:'+body.idempotency_key,c)
    return {**result,'access_token':token}

def receipt_token(ident):
    # Stable across restarts, independent from rotating Gemini encryption keys.
    with store.db() as c:r=c.execute("SELECT value FROM settings WHERE key='receipt_secret'").fetchone()
    if not r:raise HTTPException(503,'RECEIPT_SECRET_MISSING')
    return hmac.new(json.loads(r['value']).encode(),ident.encode(),hashlib.sha256).hexdigest()

def bootstrap_secret():
    with store.db() as c:c.execute('INSERT OR IGNORE INTO settings VALUES (?,?)',('receipt_secret',store.encode(secrets.token_urlsafe(48))))

def find_receipt(code,token,c):
    row=c.execute('SELECT k.*,o.payload,o.at FROM order_control k JOIN orders o ON o.id=k.id WHERE k.code=?',(code,)).fetchone()
    if not row or not row['access_digest'] or not hmac.compare_digest(sha(token),row['access_digest']):raise HTTPException(404,'ORDER_NOT_FOUND')
    return row

def change(c,row,target,actor,version=None):
    if row['status']==target:return json.loads(row['payload'])
    if version is not None and version!=row['version']:raise HTTPException(409,'Заказ уже изменён другим сотрудником. Обновите доску.')
    if target not in STATES.get(row['status'],set()):raise HTTPException(409,'Недопустимый переход статуса заказа')
    now=time.time();payload=json.loads(row['payload']);payload.update(status=target,version=row['version']+1,updated_at=datetime.fromtimestamp(now,ZONE).isoformat())
    confirmed=row['confirmed'] or (now if target=='confirmed' else None)
    if confirmed:payload['confirmed_at']=datetime.fromtimestamp(confirmed,ZONE).isoformat()
    c.execute('UPDATE order_control SET status=?,version=version+1,updated=?,confirmed=? WHERE id=?',(target,now,confirmed,row['id']))
    c.execute('UPDATE orders SET payload=? WHERE id=?',(store.encode(payload),row['id']))
    c.execute('INSERT INTO order_changes(order_id,at,old_status,new_status,actor) VALUES (?,?,?,?,?)',(row['id'],now,row['status'],target,actor))
    return payload

class Visit(BaseModel):
    table:int|None=Field(default=None,ge=1,le=9999)
    view_id:str=Field(min_length=12,max_length=100)
class Event(BaseModel):
    kind:Literal['cart_add','filter']
    event_id:str=Field(min_length=12,max_length=100)
    table:int|None=Field(default=None,ge=1,le=9999)
    dish_id:str|None=Field(default=None,max_length=80)
    filter:str|None=Field(default=None,max_length=40)
class Pin(BaseModel):
    pin:str=Field(pattern=r'^[0-9]{4,8}$')
class Approval(Pin):
    access_token:str=Field(min_length=32,max_length=100)
class Transition(BaseModel):
    status:Literal['confirmed','ready','completed','cancelled']
    version:int=Field(ge=1)

def register(app,admin,write_guard,limit,ip):
    @app.post('/api/visit')
    def visit(body:Visit,request:Request,response:Response):
        limit('visit:'+ip(request),120)
        token=request.cookies.get('konomi_visit','');ident=visitor(request)
        if not ident:
            token=secrets.token_urlsafe(32);ident=sha(token)
            with store.db() as c:c.execute('INSERT INTO visitors VALUES (?,?,?)',(ident,time.time(),body.table))
        import os
        from runtime import production
        response.set_cookie('konomi_visit',token,httponly=True,samesite='lax',secure=os.getenv('COOKIE_SECURE','true' if production() else 'false').lower()=='true',max_age=86400,path='/')
        record(ident,'view',{'table':body.table},f'view:{ident}:{body.view_id}')
        return {'ok':True}

    @app.post('/api/events')
    def event(body:Event,request:Request):
        limit('events:'+ip(request),180)
        ident=visitor(request,True)
        if body.kind=='filter' and body.filter not in __import__('dining').ALLERGENS|{'hit'}:raise HTTPException(422,'UNKNOWN_FILTER')
        if body.kind=='cart_add' and body.dish_id not in {d['id'] for d in store.dishes()}:raise HTTPException(422,'UNKNOWN_DISH')
        record(ident,body.kind,body.model_dump(exclude={'kind','event_id'}),f'event:{ident}:{body.event_id}')
        return {'ok':True}

    @app.get('/api/orders/{code}')
    def receipt(code:str,request:Request):
        limit('receipt:'+ip(request),120)
        token=request.headers.get('X-Order-Token','')
        with store.db() as c:row=find_receipt(code,token,c)
        return json.loads(row['payload'])

    @app.post('/api/orders/{code}/confirm')
    def approve(code:str,body:Approval,request:Request):
        # PIN attempts are persisted and applied per IP, not per easily rotated receipt.
        limit('pin:'+ip(request),90,60)
        now=time.time();identity=sha(ip(request))
        with store.db() as c:
            c.execute('BEGIN IMMEDIATE')
            r=c.execute('SELECT * FROM pin_attempts WHERE identity=?',(identity,)).fetchone()
            count=(r['attempts'] if r and now-r['started']<300 else 0)
            if count>=8:raise HTTPException(429,'Слишком много попыток PIN. Подождите 5 минут.')
            c.execute('INSERT OR REPLACE INTO pin_attempts VALUES (?,?,?)',(identity,r['started'] if r and now-r['started']<300 else now,count+1))
        saved=store.settings().get('hall_pin_hash')
        if not saved:raise HTTPException(409,'PIN зала не настроен. Подтвердите заказ через админку.')
        if not store.check_password(body.pin,saved):raise HTTPException(403,'Неверный PIN зала')
        with store.db() as c:
            c.execute('BEGIN IMMEDIATE')
            c.execute('DELETE FROM pin_attempts WHERE identity=?',(identity,))
            row=find_receipt(code,body.access_token,c)
            if row['status'] in SALE:return json.loads(row['payload'])
            return change(c,row,'confirmed','hall_pin')

    @app.get('/api/admin/hall-pin')
    def pin_info(user=Depends(admin)):
        return {'configured':bool(store.settings().get('hall_pin_hash'))}

    @app.put('/api/admin/hall-pin')
    def set_pin(body:Pin,user=Depends(admin)):
        with store.db() as c:c.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',('hall_pin_hash',store.encode(store.password_hash(body.pin))))
        store.audit('hall_pin_changed',user)
        return {'configured':True}

    @app.get('/api/admin/board')
    def board(user=Depends(admin)):
        with store.db() as c:
            rows=c.execute("SELECT k.id,k.updated,o.at,o.payload FROM order_control k JOIN orders o ON o.id=k.id WHERE k.status IN ('created','confirmed','ready') ORDER BY o.at LIMIT 500").fetchall()
            revision=c.execute('SELECT COALESCE(MAX(seq),0) FROM order_changes').fetchone()[0]
        return {'revision':revision,'server_time':time.time(),'orders':[dict(json.loads(r['payload']),id=r['id'],at=r['at'],updated=r['updated']) for r in rows],'capacity':500,'truncated':len(rows)==500}

    @app.post('/api/admin/orders/{code}/status')
    def transition(code:str,body:Transition,user=Depends(admin)):
        with store.db() as c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT k.*,o.payload FROM order_control k JOIN orders o ON o.id=k.id WHERE code=?',(code,)).fetchone()
            if not row:raise HTTPException(404,'ORDER_NOT_FOUND')
            return change(c,row,body.status,'admin:'+user,body.version)

    @app.get('/api/admin/analytics')
    def analytics(since:str|None=None,until:str|None=None,table:int|None=None,user=Depends(admin)):
        return report(since,until,table)

    @app.get('/api/admin/sales')
    def sales(status:str='all',since:str|None=None,until:str|None=None,table:int|None=None,offset:int=0,limit:int=50,user=Depends(admin)):
        if status not in {'all','sales','pending','cancelled','created','confirmed','ready','completed'}:raise HTTPException(422,'UNKNOWN_STATUS')
        if offset<0 or not 1<=limit<=200:raise HTTPException(422,'INVALID_PAGE')
        rows=selected_orders(since,until,table)
        if status!='all':rows=[r for r in rows if r['status'] in (SALE if status=='sales' else {'created'} if status=='pending' else {status})]
        return {'total':len(rows),'orders':list(reversed(rows))[offset:offset+limit]}

def bounds(since,until):
    def date(value,default):
        if not value:return default
        try:
            d=datetime.fromisoformat(value)
            return (d.replace(tzinfo=ZoneInfo(store.settings()['timezone'])) if d.tzinfo is None else d).timestamp()
        except ValueError:raise HTTPException(422,'Дата должна быть в ISO 8601')
    a,b=date(since,0),date(until,time.time()+1)
    if a>b:raise HTTPException(422,'Начало периода позже окончания')
    return a,b

def selected_orders(since=None,until=None,table=None):
    a,b=bounds(since,until)
    with store.db() as c:rows=c.execute('SELECT o.id,o.at,o.payload,k.confirmed FROM orders o JOIN order_control k ON k.id=o.id WHERE o.at>=? AND o.at<=? ORDER BY o.at',(a,b)).fetchall()
    return [dict(json.loads(r['payload']),id=r['id'],at=r['at'],confirmed_timestamp=r['confirmed']) for r in rows if table is None or json.loads(r['payload']).get('table')==table]

def report(since=None,until=None,table=None):
    a,b=bounds(since,until);orders=selected_orders(since,until,table)
    with store.db() as c:events=[dict(r) for r in c.execute('SELECT * FROM events WHERE at>=? AND at<=?',(a,b))]
    for e in events:e['data']=json.loads(e['detail'])
    if table is not None:events=[e for e in events if e['data'].get('table')==table]
    sales=[o for o in orders if o['status'] in SALE]
    tables=defaultdict(lambda:{'views':0,'confirmed_sales':0,'revenue_cents':0});hours=Counter();filters=Counter();demand=Counter();top=Counter();requested=Counter()
    for e in events:
        table_key=str(e['data'].get('table') or 'unassigned')
        if e['kind']=='view':tables[table_key]['views']+=1;hours[datetime.fromtimestamp(e['at'],ZoneInfo(store.settings()['timezone'])).hour]+=1
        if e['kind']=='filter':filters[e['data'].get('filter','unknown')]+=1
        if e['kind']=='ai_chat':
            for topic in set(e['data'].get('topics',[])):demand[topic]+=1
            for ident in set(e['data'].get('requested_ids',[])):requested[ident]+=1
            for restriction in set(e['data'].get('excludes',[])):filters['chat:'+restriction]+=1
    cents=__import__('dining').cents
    for o in sales:
        tables[str(o.get('table') or 'unassigned')]['confirmed_sales']+=1
        tables[str(o.get('table') or 'unassigned')]['revenue_cents']+=cents(o['total'])
        for l in o['lines']:
            for ident,name in zip(l['ids'],l['names']):top[(ident,name)]+=l['qty']
    revenue=sum(cents(o['total']) for o in sales)
    def avg(group):return round(sum(cents(o['total']) for o in group)/len(group)/100,2) if group else None
    ai=[o for o in sales if o.get('ai_assisted')];no_ai=[o for o in sales if not o.get('ai_assisted')]
    return {'currency':store.settings()['currency'],'period':{'since':a,'until':b,'basis':'order_created_at','timezone':store.settings()['timezone']},
    'funnel':{'views':sum(e['kind']=='view' for e in events),'unique_visitors':len({e['visitor'] for e in events if e['kind']=='view'}),'ai_chats':len({e['visitor'] for e in events if e['kind']=='ai_chat'}),'cart_adds':len({e['visitor'] for e in events if e['kind']=='cart_add'}),'checks_created':len(orders),'confirmed_sales':len(sales)},
    'finance':{'confirmed_revenue':revenue/100,'completed_revenue':sum(cents(o['total']) for o in sales if o['status']=='completed')/100,'pending_value':sum(cents(o['total']) for o in orders if o['status']=='created')/100,'average_ai':avg(ai),'average_no_ai':avg(no_ai),'ai_orders':len(ai),'no_ai_orders':len(no_ai),'combo_units':sum(l['qty'] for o in sales for l in o['lines'] if l['combo']),'upsell_units':sum(1 for o in sales for l in o['lines'] for ident in l['ids'] if ident in o.get('upsell_ids',[]))},
    'tables':[dict(table=k,views=v['views'],confirmed_sales=v['confirmed_sales'],revenue=v['revenue_cents']/100) for k,v in sorted(tables.items(),key=lambda kv:-kv[1]['revenue_cents'])],
    'hours':[{'hour':h,'views':hours[h]} for h in range(24)],'top_dishes':[{'id':i,'name':n,'qty':q} for (i,n),q in top.most_common(20)],'requested_topics':dict(demand.most_common()),'requested_dishes':[{'id':ident,'name':next((d['name'] for d in store.dishes() if d['id']==ident),ident),'requests':count} for ident,count in requested.most_common(20)],'allergen_filters':dict(filters.most_common()),
    'notes':['Views are menu opens, not verified physical QR scans. Browser telemetry can be blocked or imitated.','AI participation is observational attribution, not proof of incremental revenue.','Confirmed revenue excludes cancelled orders; completed is marked by staff, not a verified payment.','Time filter is the order creation cohort. Legacy checks remain pending and do not count as sales.']}
