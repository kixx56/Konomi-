"""Universal SPA end-to-end using the real offline agent, staff API and SQLite.
Never run against a restaurant database: inserts test dishes/settings and creates checks.
"""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright
BASE=os.environ.get('KONOMI_TEST_URL','http://127.0.0.1:18806')
OUT=Path(os.environ.get('KONOMI_SCREENSHOTS','/home/user/konomi-v6-previews'));OUT.mkdir(parents=True,exist_ok=True)
checks=[];errors=[]
def ok(msg):checks.append(msg);print('PASS:',msg)
with sync_playwright() as p:
 browser=p.chromium.launch(args=['--no-sandbox'])
 admin=browser.new_context(viewport={'width':1280,'height':1000})
 a=admin.new_page();a.on('pageerror',lambda e:errors.append(str(e)))
 a.goto(BASE+'/admin/');a.locator('#loginForm [name=password]').fill('Browser-test-password-123');a.locator('#loginForm button').click();a.locator('#workspace').wait_for(state='visible')
 a.locator('[data-tab=settings]').click();a.locator('#settingProvider').wait_for(state='visible')
 a.locator('#settingVenue').fill('Universal Demo');a.locator('#settingTone').fill('Friendly and concise');a.locator('#saveSettings').click()
 a.wait_for_function("document.querySelector('#settingsStatus').textContent.includes('сохранены')")
 cfg=admin.request.get(BASE+'/api/admin/settings').json();assert cfg['venue']=='Universal Demo' and cfg['tone']=='Friendly and concise'
 for data in [{'id':'s4','name':'Zupa pomidorowa','category':'soup','price':25,'ingredients':'tomato, basil','diets':['vegan'],'weight':'350g'},{'id':'v1','name':'Pierogi z kapustą i grzybami','category':'main','price':35,'weight':'300g'},{'id':'v2','name':'Moskole','category':'starter','price':20,'weight':'200g'}]:
  r=admin.request.post(BASE+'/api/admin/menu',headers={'X-Konomi-Admin':'1'},data={**data,'status':'published','available':True,'allergens_verified':False})
  assert r.ok or r.status==409,r.text()
 ok('Venue, tone and provider settings save in real admin; unverified recipes stay visible')
 guest=browser.new_context(viewport={'width':390,'height':844},locale='ru-RU')
 g=guest.new_page();g.on('pageerror',lambda e:errors.append(str(e)))
 g.goto(BASE+'/?table=64');g.locator('.dish').first.wait_for();g.wait_for_timeout(600)
 def send(msg):
  before=g.locator('.message[lang]').count();g.locator('#messageInput').fill(msg);g.locator('#composer').evaluate('f=>f.requestSubmit()')
  g.wait_for_function('n=>document.querySelectorAll(".message[lang]").length>n',arg=before)
  g.wait_for_function('!processing');g.wait_for_timeout(500)
 send('Какие есть супы?')
 ids=g.locator('.message[lang]').last.locator('[data-add]').evaluate_all('es=>es.map(e=>e.dataset.add)')
 assert set(ids)=={'s1','s2','s3','s4'},ids
 assert g.evaluate('S.history.length')==2
 g.screenshot(path=str(OUT/'four-soups-mobile.png'))
 ok('All four soups rendered, with four usable add buttons and no verification gate')
 send('Добавь s1 и два компота в корзину')
 g.wait_for_function('S.quote && S.quote.total===63')
 assert g.evaluate('S.lines.find(l=>l.ids[0]==="b1").qty')==2
 assert g.evaluate('S.history.length')==4
 ok('Natural-language add updates real cart quantities and server quote')
 send('Убери компот из заказа')
 g.wait_for_function('S.quote && S.quote.total===31')
 assert g.evaluate('S.lines.length')==1
 send('Очисти корзину')
 g.wait_for_function('S.lines.length===0')
 assert g.locator('#cartOpen').is_hidden()
 ok('Remove and clear execute through cart_actions, not just conversational promises')
 send('Есть что-то без мяса?')
 last=g.locator('.message[lang]').last;ids=last.locator('[data-add]').evaluate_all('es=>es.map(e=>e.dataset.add)')
 assert {'v1','v2','m5','d1'}.issubset(ids),ids
 assert 'm1' not in ids
 g.screenshot(path=str(OUT/'no-meat-mobile.png'))
 ok('No-meat catalogue includes actual vegetarian choices and labelled fish, not empty handoff text')
 # Start a new table session without the previous food preferences for command-race verification.
 g.goto(BASE+'/?table=65');g.locator('.dish').first.wait_for();g.wait_for_timeout(700)
 requests=[]
 def delayed(route):
  requests.append(route.request.post_data_json)
  g.evaluate("S.lines=[{ids:['b1'],qty:1,combo:false}];saveCart();renderCart();requestQuote();")
  route.fulfill(status=200,content_type='application/json',body=json.dumps({'reply':'Добавляю суп в выбранный заказ.','lang':'ru','engine':'gemini','request_id':'browser-delayed-cart-action','dishes':['s1'],'excludes':[],'diets':[],'cart_actions':[{'action':'add','id':'s1','qty':1}],'cart_after':[{'ids':['s1'],'qty':1,'combo':False}],'cart_action_id':'browser-delayed-cart-action'}))
 g.route('**/api/chat',delayed)
 # Submit without waiting for response, then mutate the cart from the menu.
 g.locator('#messageInput').fill('Добавь суп');g.locator('#composer').evaluate('f=>f.requestSubmit()')
 g.wait_for_function('!processing && document.querySelectorAll(".message[lang]").length>0')
 assert g.evaluate('S.lines.length===1 && S.lines[0].ids[0]==="b1"')
 assert 'не буду перезаписывать' in g.locator('.message[lang]').last.inner_text()
 assert requests[0]['cart']==[] and isinstance(requests[0]['history'],list)
 g.unroute('**/api/chat',delayed)
 ok('Delayed model action cannot overwrite a manual cart change; history and cart are sent')
 for width in [390,320]:
  g.set_viewport_size({'width':width,'height':844});assert g.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
  a.set_viewport_size({'width':width,'height':844});a.locator('[data-tab=settings]').click();a.wait_for_timeout(300)
  assert a.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
 ok('New universal controls and multi-card chat fit 320px and 390px viewports')
 browser.close()
assert not errors,errors
(OUT/'universal-browser-results.json').write_text(json.dumps({'checks':checks,'javascript_errors':errors},ensure_ascii=False,indent=2))
print(len(checks),'universal browser scenarios passed')
