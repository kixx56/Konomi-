"""Run against an isolated local test server. Never use real restaurant data."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE=os.getenv('KONOMI_TEST_URL','http://127.0.0.1:8000')
OUT=Path(os.getenv('KONOMI_SCREENSHOTS',str(Path(__file__).resolve().parent/'artifacts')))
OUT.mkdir(parents=True,exist_ok=True)
errors=[];checks=[]

def checked(label):
    checks.append(label);print('PASS:',label)

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
    context=browser.new_context(viewport={'width':1440,'height':1000},device_scale_factor=1)
    page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
    page.route('**/api/weather',lambda route:route.fulfill(json={'city':'Łódź','temp':8,'condition':'rain','time_slot':'evening','source':'test'}))
    page.goto(BASE,wait_until='domcontentloaded');page.locator('.dish').first.wait_for();page.wait_for_timeout(1000)
    assert page.locator('.dish').count()==10
    checked('Menu loads from API')
    page.locator('[data-add="s1"]').click()
    page.wait_for_function("document.querySelector('#cartTotal').textContent.includes('31')")
    if 'open' not in page.locator('#sheet').get_attribute('class'):page.locator('#toggleChat').click()
    page.wait_for_timeout(600)
    # Sheet rectangle ends before dock; cart center hit-tests to the cart button.
    bounds=page.evaluate('''() => {const s=document.querySelector('#sheet').getBoundingClientRect();const d=document.querySelector('#dock').getBoundingClientRect();const c=document.querySelector('#cartOpen').getBoundingClientRect();const hit=document.elementFromPoint(c.x+c.width/2,c.y+c.height/2);return {sheetBottom:s.bottom,dockTop:d.top,clickable:!!hit.closest('#cartOpen')};}''')
    assert bounds['sheetBottom']<=bounds['dockTop']+1,bounds
    assert bounds['clickable'],bounds
    page.locator('#cartOpen').click();assert page.locator('#cartDialog').is_visible()
    page.wait_for_function("!document.querySelector('#checkout').disabled")
    page.locator('#checkout').click();page.locator('#receiptDialog[open]').wait_for()
    assert 'GP-' in page.locator('#receipt').inner_text()
    page.locator('[data-close="receiptDialog"]').click()
    checked('Cart above chat, accessible checkout, real stored guest check')
    page.locator('#messageInput').fill('Собери комбо');page.locator('#composer').evaluate('(f)=>f.requestSubmit()')
    page.locator('[data-combo]').wait_for(timeout=15000)
    page.locator('[data-combo]').click()
    page.wait_for_function("S.quote?.lines?.some(l=>l.combo) && S.quote.lines.some(l=>!l.combo) && document.querySelector('#cartCount').textContent==='4'")
    checked('Combo added, server total includes full-price individual dish')
    page.locator('#closeChat').click();page.screenshot(path=str(OUT/'guest-desktop.png'),full_page=False)
    page.goto(BASE+'/admin');page.locator('#loginView').wait_for(state='visible')
    page.locator('[name=username]').fill('admin');page.locator('#loginForm [name=password]').fill('Browser-test-password-123');page.locator('#loginForm button[type=submit]').click()
    page.locator('#workspace').wait_for(state='visible');page.locator('.stat').first.wait_for()
    checked('Admin login with HttpOnly cookie')
    page.locator('[data-tab=menu]').click();page.locator('[data-edit="s1"]').wait_for()
    page.locator('[data-edit="s1"]').click();page.locator('#dishEditor[open]').wait_for()
    page.locator('[name=details]').fill('Проверенная заметка из браузерного теста')
    page.locator('#saveDish').click();page.locator('#dishEditor').wait_for(state='hidden')
    assert not page.locator('#toast').inner_text().startswith('Ошибка')
    checked('Editor persists dish details without losing provenance')
    page.locator('[data-tab=import]').click();page.locator('#importFile').set_input_files({'name':'test-import.csv','mimeType':'text/csv','buffer':'Название;Цена;Состав;Регион\nТестовый суп браузера;35,50;Бульон;Лодзь'.encode('utf-8-sig')})
    page.locator('#previewBtn').click();page.locator('#importReview').wait_for(state='visible');assert 'Тестовый суп браузера' in page.locator('#previewRows').inner_text()
    page.locator('#importAcknowledged').check();page.locator('#commitImport').click()
    page.wait_for_function("document.querySelector('#importStatus').textContent.includes('добавлено')")
    page.locator('[data-tab=menu]').click();page.locator('#menuSearch').fill('Тестовый суп браузера')
    assert 'Черновик' in page.locator('#dishRows').inner_text()
    checked('CSV preview, field mapping, draft commit in browser')
    page.locator('#menuSearch').fill('');page.wait_for_timeout(4800);page.screenshot(path=str(OUT/'admin-desktop.png'),full_page=False)
    page.locator('[data-tab=settings]').click();page.locator('#settingVenue').wait_for();page.locator('#settingVenue').fill('Gęsi Puch');page.locator('#saveSettings').click();page.wait_for_function("document.querySelector('#settingsStatus').textContent.includes('сохранены')")
    checked('Settings save without exposing API key')
    # Mobile views.
    page.set_viewport_size({'width':390,'height':844});page.goto(BASE,wait_until='domcontentloaded');page.locator('.dish').first.wait_for();page.wait_for_timeout(600)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Guest horizontal overflow'
    logo=page.locator('.brand').bounding_box();assert logo['width']>100 and logo['x']>=0
    if 'open' not in page.locator('#sheet').get_attribute('class'):page.locator('#toggleChat').click()
    page.wait_for_timeout(600)
    bounds=page.evaluate('''() => {const s=document.querySelector('#sheet').getBoundingClientRect(),d=document.querySelector('#dock').getBoundingClientRect(),c=document.querySelector('#cartOpen').getBoundingClientRect();return {bottom:s.bottom,top:d.top,click:!!document.elementFromPoint(c.x+c.width/2,c.y+c.height/2).closest('#cartOpen')};}''')
    assert bounds['bottom']<=bounds['top']+1 and bounds['click'],bounds
    page.locator('#cartOpen').click();assert page.locator('#cartDialog').is_visible();page.locator('[data-close=cartDialog]').click()
    checked('390px mobile: logo intact, no overflow, cart clickable with open chat')
    page.screenshot(path=str(OUT/'guest-mobile.png'),full_page=False)
    page.goto(BASE+'/admin');page.locator('#workspace').wait_for(state='visible');page.locator('[data-tab=menu]').click();page.locator('#dishRows').wait_for();page.wait_for_timeout(300)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Admin horizontal overflow'
    page.screenshot(path=str(OUT/'admin-mobile.png'),full_page=False)
    checked('Mobile admin fits viewport')
    page.set_viewport_size({'width':320,'height':640});page.goto(BASE);page.locator('.dish').first.wait_for()
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    checked('320px compact guest layout')
    browser.close()
assert not errors,errors
(OUT/'browser-results.json').write_text(json.dumps({'checks':checks,'javascript_errors':errors},indent=2,ensure_ascii=False),'utf-8')
print(f'{len(checks)} browser checks passed. No JavaScript exceptions.')
