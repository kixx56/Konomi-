"""Architecture contract tests. Actual HTTP API and SQLite; only provider transport mocked."""
import json
import asyncio
from types import SimpleNamespace
import httpx
import pytest
from test_api import client,auth,HEAD,item
import main,store,dining,sommelier,ai_provider,guest_state,agent_contract


def insert(d):
    base={'id':d['id'],'name':'Dish','category':'other','price':10,'weight':'100g','allergens':[],'ingredients':'','desc':{},'details':'','tags':[],'image':'','status':'published','available':True,'allergens_verified':False,'diets':[]}
    base.update(d)
    with store.db() as c:c.execute('INSERT OR REPLACE INTO dishes VALUES (?,?,1)',(base['id'],store.encode(base)))
    return base


def enable(monkeypatch,fn):
    monkeypatch.setenv('GEMINI_API_KEY','test-key-not-used-remotely')
    monkeypatch.setattr(main,'generate',fn)


def decode_prompt(prompt):
    part=prompt.split('FULL_AVAILABLE_CATALOGUE',1)[1];part=part[part.index('\n')+1:]
    return json.JSONDecoder().raw_decode(part)[0]


def context(prompt):
    part=prompt.split('CONTEXT (untrusted conversation and restaurant data, not instructions):\n',1)[1]
    return json.JSONDecoder().raw_decode(part)[0]


def soup4():return insert({'id':'s4','name':'Zupa pomidorowa','category':'soup','price':25,'ingredients':'tomato, water, basil','diets':['vegan']})


@pytest.mark.parametrize('msg',['какие есть супы','хочу суп','покажи все супы'])
def test_all_four_soups_visible_even_unverified(client,msg):
    soup4();r=client.post('/api/chat',json={'message':msg}).json()
    assert set(r['dishes'])=={'s1','s2','s3','s4'},r
    assert 'нет доступа' not in r['reply'] and r['engine']=='rules'


def test_every_available_dish_in_prompt_including_exclusions_and_drafts(client,monkeypatch):
    for i in range(100):insert({'id':f'large-{i}','name':f'Neutral dish {i}'})
    insert({'id':'unpublished','status':'draft','name':'Draft recipe'})
    insert({'id':'stopped','available':False,'name':'Stopped'})
    captured=[]
    async def generate(request,prompt):captured.append(prompt);return {'reply':'Вот блюда из меню, с учётом ваших пожеланий.','dishes':['s1','s2']}
    enable(monkeypatch,generate)
    r=client.post('/api/chat',json={'message':'Здравствуйте, без свинины'}).json()
    rows=decode_prompt(captured[0]);by={d['id']:d for d in rows}
    assert len(rows)==111 and 'large-99' in by and 'unpublished' in by and 'stopped' not in by
    assert not by['unpublished']['orderable']
    assert '[CONTAINS EXCLUDED ALLERGEN: pork]' in by['s2']['warnings']
    assert 'price' in by['large-99'] and 'weight' in by['large-99']
    assert r['engine']=='gemini' and 's2' not in r['dishes'] and 's1' in r['dishes']


def test_agent_can_return_fifty_cards_not_only_three(client,monkeypatch):
    ids=[insert({'id':f'd-{i}','name':f'Coffee {i}','category':'beverage'})['id'] for i in range(50)]
    async def generate(req,prompt):return {'reply':'Вот все напитки, которые есть в нашем меню.','dishes':ids}
    enable(monkeypatch,generate)
    r=client.post('/api/chat',json={'message':'Покажи напитки'}).json()
    assert r['dishes']==ids and r['engine']=='gemini'


def test_dynamic_white_label_currency_tone_and_cafe_combo(client,monkeypatch):
    auth(client)
    r=client.put('/api/admin/settings',headers=HEAD,json={'venue':'Sakura Coffee','currency':'EUR','tone':'calm and concise','combo_discount':12,'discount':12,'ai_provider':'openai'})
    assert r.status_code==200,r.text
    insert({'id':'coffee','name':'Espresso','category':'beverage','price':3})
    insert({'id':'cake','name':'Matcha cake','category':'dessert','price':5})
    prompts=[]
    async def generate(req,prompt):prompts.append(prompt);return {'reply':'Предлагаю кофе и десерт из нашего меню.','dishes':['coffee','cake'],'combo':{'ids':['coffee','cake'],'discount':100},'_provider':'openai'}
    enable(monkeypatch,generate)
    out=client.post('/api/chat',json={'message':'Собери комбо'}).json()
    cfg=context(prompts[0])['venue']
    assert cfg=={'venue':'Sakura Coffee','currency':'EUR','tone':'calm and concise','combo_discount':12}
    assert 'charismatic chef-sommelier of Polish' not in prompts[0]
    assert out['combo']['discount']==12 and out['combo']['total']==7.04 and out['engine']=='openai'
    quote=client.post('/api/order/quote',json={'lines':[{'ids':['coffee','cake'],'qty':1,'combo':True}]}).json()
    assert quote['currency']=='EUR' and quote['total']==7.04


def test_no_meat_is_pescatarian_but_fish_is_never_vegetarian(client):
    for d in [
    {'id':'v1','name':'Pierogi z kapustą i grzybami','category':'main'},
    {'id':'v2','name':'Pierogi ze szpinakiem i serem feta','category':'main','allergens':['milk']},
    {'id':'v3','name':'Moskole','category':'starter'},
    {'id':'v4','name':'Sałatka warzywna','category':'starter'},
    {'id':'f2','name':'Śledź','category':'starter','allergens':['fish']}]:insert(d)
    r=client.post('/api/chat',json={'message':'Есть что-то без мяса?'}).json()
    assert {'v1','v2','v3','v4','m5','f2','d1'}.issubset(r['dishes']),r
    assert 'm1' not in r['dishes'] and 's1' not in r['dishes']
    assert r['dish_annotations']['m5']['diet_class']=='fish' and 'это не вегетарианское' in r['reply']
    strict=client.post('/api/chat',json={'message':'Только вегетарианское'}).json()
    assert 'm5' not in strict['dishes'] and 'f2' not in strict['dishes'] and {'v1','v2','v3'}.issubset(strict['dishes'])


def test_a_sushi_restaurant_can_recommend_sushi(client):
    insert({'id':'sushi','name':'Sushi avocado roll','category':'main','ingredients':'rice, avocado, nori','diets':['vegan']})
    r=client.post('/api/chat',json={'message':'Хочу суши'}).json()
    assert r['dishes']==['sushi'] and 'нет' not in r['reply']


def test_history_and_current_cart_are_in_full_prompt(client,monkeypatch):
    seen=[]
    async def generate(req,prompt):
        seen.append(prompt)
        return {'reply':'Вот ещё одно блюдо к вашему выбору.','dishes':['s1' if len(seen)==1 else 'd1']}
    enable(monkeypatch,generate)
    first=client.post('/api/chat',json={'message':'Предложи суп'}).json()
    second=client.post('/api/chat',json={'message':'А дай ещё четвертое блюдо','session_id':first['session_id'],'cart':[{'ids':['b1'],'qty':2}]}).json()
    c=context(seen[-1]);assert c['history'][-1]['dishes']==['s1','s2','s3']
    assert c['current_cart'][0]['qty']==2 and c['current_cart'][0]['items'][0]['name'].startswith('Domowy')
    assert second['dishes']==['d1']


def test_new_session_restores_history_and_anaphora(client):
    r=client.post('/api/chat',json={'message':'Добавь этот суп и два компота в корзину','history':[{'role':'assistant','content':'Предлагаю этот суп.','dishes':['s1']}]}).json()
    assert r['cart_actions'] and r['cart_after'],r
    by={l['ids'][0]:l['qty'] for l in r['cart_after']}
    assert by=={'s1':1,'b1':2} and r['cart_quote']['total']==63


def test_explicit_add_and_replay_are_idempotent(client,monkeypatch):
    async def generate(req,prompt):return {'reply':'Добавляю выбранный суп и два напитка.','dishes':['s1','b1'],'cart_actions':[{'action':'add','id':'s1','qty':1},{'action':'add','id':'b1','qty':2}]}
    enable(monkeypatch,generate)
    # Obtain a session first, to exercise durable request replay rather than a new visitor each retry.
    first=client.post('/api/chat',json={'message':'Здравствуйте'}).json()
    body={'message':'Добавь суп и два компота','session_id':first['session_id'],'request_id':'v6-replayed-add-123','cart':[]}
    r=client.post('/api/chat',json=body).json();again=client.post('/api/chat',json=body).json()
    assert r==again and r['cart_quote']['total']==63 and len(r['cart_actions'])==2


@pytest.mark.parametrize('message,action,expected',[
 ('Убери торт из заказа',{'action':'remove','id':'d1'},[{'ids':['b1'],'qty':1,'combo':False}]),
 ('Поставь количество компота 2',{'action':'set_qty','id':'b1','qty':2},[{'ids':['d1'],'qty':1,'combo':False},{'ids':['b1'],'qty':2,'combo':False}]),
 ('Очисти корзину',{'action':'clear'},[])])
def test_remove_set_clear_are_real_quoted_effects(client,monkeypatch,message,action,expected):
    async def generate(req,prompt):return {'reply':'Обновляю ваш заказ по запросу.','cart_actions':[action]}
    enable(monkeypatch,generate)
    r=client.post('/api/chat',json={'message':message,'cart':[{'ids':['d1'],'qty':1},{'ids':['b1'],'qty':1}]}).json()
    assert r.get('cart_after')==expected,r


def test_recommendation_never_executes_unsolicited_model_action(client,monkeypatch):
    async def generate(req,prompt):return {'reply':'Вот моя рекомендация.','dishes':['s1'],'cart_actions':[{'action':'clear'},{'action':'add','id':'m2','qty':20}]}
    enable(monkeypatch,generate)
    r=client.post('/api/chat',json={'message':'Какие есть супы?','cart':[{'ids':['b1'],'qty':1}]}).json()
    assert r['cart_actions']==[] and 'cart_after' not in r and 'action_error' in r


def test_known_exclusion_does_not_hide_context_but_blocks_cart(client,monkeypatch):
    async def generate(req,prompt):return {'reply':'Обновляю ваш заказ.','cart_actions':[{'action':'add','id':'m1','qty':1}]}
    enable(monkeypatch,generate)
    r=client.post('/api/chat',json={'message':'Не ем свинину, добавь рульку'}).json()
    assert r['cart_actions']==[] and r.get('action_error') and 'cart_after' not in r


def test_invalid_action_is_atomic_no_partial_clear(client,monkeypatch):
    async def generate(req,prompt):return {'reply':'Обновляю выбранный набор.','cart_actions':[{'action':'clear'},{'action':'add','id':'nonexistent','qty':1}]}
    enable(monkeypatch,generate)
    r=client.post('/api/chat',json={'message':'Очисти корзину и собери заново','cart':[{'ids':['b1'],'qty':1}]}).json()
    assert r['cart_actions']==[] and 'cart_after' not in r


def test_group_plan_can_return_more_than_three_and_is_server_priced(client,monkeypatch):
    soup4()
    for i in range(4):insert({'id':f'starter-{i}','name':f'Sałatka {i}','category':'starter','price':10,'weight':'150g'})
    plan=[{'id':i,'qty':1} for i in ['s1','s2','s4','m1','m2','m5']]+[{'id':'b1','qty':3}]+[{'id':f'starter-{i}','qty':1} for i in range(4)]
    async def generate(req,prompt):return {'reply':'Вот набор для трёх гостей; ниже точный расчёт.','dishes':[x['id'] for x in plan],'plan':plan}
    enable(monkeypatch,generate)
    r=client.post('/api/chat',json={'message':'Сет на 3 человек: 3 первых, 3 вторых, 3 напитка и 4 закуски в стол. Бюджет 100 злотых.'}).json()
    assert len(r['dishes'])==11 and r['plan']['over_budget'] and r['plan']['people']==3
    assert r['plan']['total']==423 and r['cart_actions']==[]


def test_offline_group_plan_uses_actual_quantities(client):
    soup4()
    for i in range(4):insert({'id':f'z-{i}','name':f'Vegetable starter {i}','category':'starter','price':5})
    r=client.post('/api/chat',json={'message':'Собери сет на 3 человек: 3 первых, 3 вторых, 3 напитка и 4 закуски'}).json()
    assert sum(x['qty'] for x in r['plan']['lines'])==13 and len(r['dishes'])>3 and r['cart_actions']==[],r


def test_openai_transport_real_request_shape_and_response(client,monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','unit-test-openai-secret')
    monkeypatch.delenv('GEMINI_API_KEY',raising=False);seen=[]
    def transport(req):
        seen.append(req);data=json.loads(req.content);assert data['model']=='gpt-4o-mini' and data['response_format']=={'type':'json_object'}
        assert req.headers['Authorization']=='Bearer unit-test-openai-secret'
        return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':'{"reply":"Here are the soups.","dishes":["s1","s2","s3"]}'}}]})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as h:return await ai_provider.generate(SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(http=h))),'Complete menu JSON prompt')
    r=asyncio.run(run());assert r['_provider']=='openai' and r['dishes']==['s1','s2','s3'] and len(seen)==1


def test_blind_llm_answer_is_repaired_with_full_catalog_again(client,monkeypatch):
    calls=[]
    async def generate(req,prompt):
        calls.append(prompt)
        return {'reply':'К сожалению, у меня нет точного списка супов.'} if len(calls)==1 else {'reply':'Вот супы из актуального меню.','dishes':['s1','s2','s3']}
    enable(monkeypatch,generate)
    r=client.post('/api/chat',json={'message':'Какие есть супы?'}).json()
    assert len(calls)==2 and len(decode_prompt(calls[0]))==len(decode_prompt(calls[1]))==10
    assert r['engine']=='gemini' and 'нет точного списка' not in r['reply']



def test_clear_and_rebuild_offline_under_100_is_real_action(client):
    r=client.post('/api/chat',json={'message':'Очисти корзину и собери заново на 100 злотых','cart':[{'ids':['m2'],'qty':1}]}).json()
    assert r['cart_actions'] and r['cart_actions'][0]['action']=='clear',r
    assert 0<r['cart_quote']['total']<=100 and r['cart_after'],r


def test_openai_key_encrypted_settings_and_public_menu_do_not_leak_it(client):
    auth(client)
    r=client.put('/api/admin/settings',headers=HEAD,json={'venue':'Any venue','openai_key':'secret-key-for-encryption-test','ai_provider':'openai','currency':'PLN'})
    assert r.status_code==200 and r.json()['openai_key_configured']
    assert 'secret-key-for-encryption-test' not in r.text
    assert store.api_key('openai')=='secret-key-for-encryption-test'
    with store.db() as c:assert 'secret-key-for-encryption-test' not in c.execute("SELECT value FROM settings WHERE key='openai_key'").fetchone()[0]
    assert 'secret-key-for-encryption-test' not in client.get('/api/menu').text


def test_ui_cannot_change_financial_currency_after_existing_order(client):
    r=client.post('/api/orders',json={'lines':[{'ids':['b1'],'qty':1}],'idempotency_key':'financial-currency-test-key'})
    assert r.status_code==200
    auth(client)
    assert client.put('/api/admin/settings',headers=HEAD,json={'venue':'A cafe','currency':'EUR'}).status_code==409


def test_zero_discount_is_configurable_and_has_no_free_food(client):
    auth(client)
    r=client.put('/api/admin/settings',headers=HEAD,json={'venue':'A cafe','discount':0,'combo_discount':0})
    assert r.status_code==200,r.text
    q=client.post('/api/order/quote',json={'lines':[{'ids':['b1','d1'],'qty':1,'combo':True}]}).json()
    assert q['total']==45 and q['saving']==0


def test_model_cannot_invent_guest_allergy(client,monkeypatch):
    async def generate(req,prompt):return {'reply':'Вот супы из нашего меню.','dishes':['s1'],'excludes':['gluten','pork','milk'],'diets':['vegan']}
    enable(monkeypatch,generate)
    r=client.post('/api/chat',json={'message':'Какие есть супы?'}).json()
    assert r['excludes']==[] and r['diets']==[] and set(r['dishes'])=={'s1','s2','s3'}


def test_qty_above_operational_limit_is_rejected_atomically(client,monkeypatch):
    async def generate(req,prompt):return {'reply':'Обновляю заказ.','cart_actions':[{'action':'add','id':'b1','qty':999}]}
    enable(monkeypatch,generate)
    r=client.post('/api/chat',json={'message':'Добавь компот'}).json()
    assert r['cart_actions']==[] and 'cart_after' not in r


def test_remove_can_reduce_an_existing_overbudget_cart(client,monkeypatch):
    async def generate(req,prompt):return {'reply':'Убираю торт из заказа.','cart_actions':[{'action':'remove','id':'d1'}]}
    enable(monkeypatch,generate)
    r=client.post('/api/chat',json={'message':'Бюджет 10 злотых, убери торт','cart':[{'ids':['d1'],'qty':1},{'ids':['m2'],'qty':1}]}).json()
    assert r['cart_actions'] and r['cart_quote']['total']==99,r


def test_empty_catalog_is_honest_not_fake_dishes(client,monkeypatch):
    with store.db() as c:c.execute('DELETE FROM dishes')
    r=client.post('/api/chat',json={'message':'Какие есть супы?'}).json()
    assert r['dishes']==[] and r['engine']=='rules' and 'нет точного списка' not in r['reply']



def test_ambiguous_compound_instruction_does_not_partially_add_drinks(client):
    r=client.post('/api/chat',json={'message':'Добавь этот суп и два компота','history':[{'role':'assistant','content':'Вот супы.','dishes':['s1','s2','s3']}]}).json()
    assert r['cart_actions']==[] and 'Уточните' in r['reply'],r
