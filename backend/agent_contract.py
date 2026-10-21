"""Universal agent boundary: the model sees everything; only validated effects execute.
No model-supplied price, availability, publication or promotion is trusted.
"""
import copy
import hashlib
import json
import re
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, StrictInt
from fastapi import HTTPException
import dining
import store

MAX_LINES=200
MAX_QTY=30

class CartAction(BaseModel):
    model_config=ConfigDict(extra='forbid')
    action:Literal['add','remove','set_qty','clear']
    id:str|None=Field(default=None,max_length=80)
    qty:StrictInt=Field(default=1,ge=1,le=MAX_QTY)

class AgentReply(BaseModel):
    reply:str=Field(min_length=1,max_length=12000)
    dishes:list[str]=Field(default_factory=list)
    combo:dict|None=None
    cart_actions:list[dict]=Field(default_factory=list,max_length=200)
    filters:dict=Field(default_factory=dict)
    excludes:list[str]=Field(default_factory=list,max_length=40)
    diets:list[str]=Field(default_factory=list,max_length=8)
    unresolved_allergy:bool=False
    plan:list[dict]=Field(default_factory=list,max_length=200)


def signature(lines):
    value=[line.model_dump() if hasattr(line,'model_dump') else {k:line[k] for k in ('ids','qty','combo')} for line in lines]
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()


def authorized_actions(message):
    """Only the current guest instruction authorizes effects, never model/history text."""
    low=message.casefold()
    if re.search(r'что (?:можно |лучше )?добавить|что (?:можно )?убрать|what (?:can|could|should)|was (?:kann|könnte)|co (?:można|moge)',low):return set()
    verbs={
    'add':r'\b(?:добавь\w*|добавит\w*|положи\w*|закажи\w*|додай\w*|add|put|order|dodaj|zamów|hinzufügen|füge|bestell\w*)\b',
    'remove':r'\b(?:убери\w*|удали\w*|прибери\w*|remove|delete|usuń|usun|entfern\w*|lösche)\b',
    'set_qty':r'\b(?:поставь|измени\w*|сделай|количеств\w*|set|change|zmień|ustaw|ändere|setze)\b',
    'clear':r'\b(?:очисти\w*|сбрось|очисть|clear|empty|wyczyść|wyczysc|leere)\b'}
    found={kind for kind,pattern in verbs.items() if re.search(pattern,low)}
    if re.search(r'замени|поменяй|replace|swap|zamień|ersetze',low):found.update(('add','remove','set_qty'))
    if 'clear' in found and re.search(r'собери|заново|build|rebuild|fill|zbuduj|zusammen',low):found.add('add')
    if re.search(r'в (?:корзину|заказ)|to (?:my |the )?cart|do koszyka|warenkorb',low) and re.search(r'собери|оформи|build|fill|zestaw|zusammen',low):found.add('add')
    return found


def catalog(excludes=()):
    """EVERY available row, including unverified recipes, before ANY LLM call.
    Drafts are visible as facts but explicitly not orderable; staff controls publication.
    No internal provenance, costs or encrypted settings are exposed to the model.
    """
    rows=[]
    for d in store.dishes():
        if d.get('available') is False:continue
        blocked=sorted(set(d.get('allergens',[])) & set(excludes))
        row={k:d.get(k) for k in ('id','name','category','price','weight','ingredients','desc','details','tags','allergens','allergens_verified','diets','available')}
        row['publication_status']=d.get('status','published')
        row['orderable']=d.get('status','published')=='published' and not blocked
        row['warnings']=[f'[CONTAINS EXCLUDED ALLERGEN: {a}]' for a in blocked]
        if not d.get('allergens_verified'):row['warnings'].append('[RECIPE NOT VERIFIED: do not guarantee allergen absence]')
        row['diet_class']=dining.diet_class(d)
        rows.append(row)
    return rows


def priced_plan(lines,by,currency):
    normalized=[];total=0;grams=0;unknown=[]
    for row in lines:
        ident=row.get('id');qty=row.get('qty',1)
        if ident not in by or isinstance(qty,bool) or not isinstance(qty,int) or not 1<=qty<=MAX_QTY:raise ValueError('Invalid plan line')
        d=by[ident];subtotal=dining.cents(d['price'])*qty;total+=subtotal
        weight=dining.weight(d)
        if d['category']!='beverage':
            if weight:grams+=weight*qty
            else:unknown.append(ident)
        normalized.append({'id':ident,'qty':qty,'unit':d['price'],'total':subtotal/100})
    return {'lines':normalized,'total':total/100,'currency':currency,'known_food_grams':grams,'unknown_weights':list(dict.fromkeys(unknown))}


def validate_combo(raw,by):
    if not raw:return None
    ids=raw.get('ids')
    if not isinstance(ids,list) or not 2<=len(ids)<=100 or len(set(ids))!=len(ids) or any(i not in by for i in ids):return None
    sub=sum(dining.cents(by[i]['price']) for i in ids)
    discount=store.settings()['combo_discount']
    saving=int((Decimal(sub)*discount/100).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
    return {'ids':ids,'discount':discount,'subtotal':sub/100,'saving':saving/100,'total':(sub-saving)/100,'currency':store.settings()['currency']}


def apply_actions(raw,cart,message,eligible,quote_fn,excludes,diets,budget=None):
    """Validate all actions, then price the ENTIRE proposed cart; all-or-nothing."""
    if not raw:return [],None,None
    permissions=authorized_actions(message)
    by={d['id']:d for d in eligible};original=[l.model_dump() if hasattr(l,'model_dump') else copy.deepcopy(l) for l in cart]
    lines=copy.deepcopy(original);actions=[]
    if len(raw)>200:raise ValueError('Too many cart actions')
    for data in raw:
        a=CartAction.model_validate(data)
        if a.action not in permissions:raise ValueError('Cart action not explicitly requested')
        if a.action=='clear':lines=[];actions.append({'action':'clear'});continue
        if not a.id:raise ValueError('Dish id required')
        if a.action in ('add','set_qty') and a.id not in by:raise ValueError('Dish not orderable under current restrictions')
        if a.action=='remove':
            # Removing one item from a combo dissolves that set; remaining items have full price.
            dissolved=[]
            for line in lines:
                if a.id in line['ids']:
                    dissolved.extend({'ids':[i],'qty':line['qty'],'combo':False} for i in line['ids'] if i!=a.id)
                else:dissolved.append(line)
            lines=dissolved
        else:
            targets=[l for l in lines if l['ids']==[a.id] and not l['combo']]
            if a.action=='set_qty' and not targets:raise ValueError('set_qty target is not in cart')
            if targets:targets[0]['qty']=targets[0]['qty']+a.qty if a.action=='add' else a.qty
            else:lines.append({'ids':[a.id],'qty':a.qty,'combo':False})
        if len(lines)>MAX_LINES or any(l['qty']>MAX_QTY for l in lines):raise ValueError('Order quantity limit exceeded')
        actions.append(a.model_dump(exclude_none=True))
    # Merge identical standalone rows after dissolving combos.
    merged=[]
    for line in lines:
        same=next((x for x in merged if x['ids']==line['ids'] and x['combo']==line['combo']),None)
        if same:same['qty']+=line['qty']
        else:merged.append(line)
    if any(l['qty']>MAX_QTY for l in merged):raise ValueError('Quantity limit exceeded')
    from types import SimpleNamespace
    quote=quote_fn(merged,excludes,diets) if merged else {'lines':[],'total':0,'saving':0,'currency':store.settings()['currency']}
    increases=any(a['action']=='add' for a in actions) or any(a['action']=='set_qty' and a.get('qty',1)>sum(l['qty'] for l in original if a.get('id') in l['ids']) for a in actions)
    if budget is not None and increases and dining.cents(quote['total'])>dining.cents(budget):raise ValueError('Proposed cart exceeds guest budget')
    return actions,merged,quote
