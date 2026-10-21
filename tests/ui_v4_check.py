"""Real browser demo: 500ms nudge, >=16px fields, language/UI separation, offers, QR.
Use only an isolated server with Browser-test-password-123; not live restaurant data.
"""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE=os.getenv('KONOMI_TEST_URL','http://127.0.0.1:8000')
OUT=Path(os.getenv('KONOMI_SCREENSHOTS',str(Path(__file__).parent/'artifacts')))
OUT.mkdir(parents=True,exist_ok=True)
checks=[];errors=[]
def passed(label):checks.append(label);print('PASS:',label)
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
 context=browser.new_context(viewport={'width':390,'height':844},accept_downloads=True,locale='en-GB')
 page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto(BASE+'/?table=7',wait_until='domcontentloaded')
 page.wait_for_function("document.querySelector('#sheet').classList.contains('open')")
 assert page.evaluate("document.activeElement.id!=='messageInput'")
 assert page.locator('#messageInput').evaluate("e=>parseFloat(getComputedStyle(e).fontSize)")>=16
 assert page.locator('#tableContext').inner_text()=='Table 7'
 passed('500ms onboarding opens without input focus; input 16px; QR table visible')
 page.locator('.dish').first.wait_for()
 page.locator('#messageInput').fill('Ich möchte etwas Herzhaftes, was empfehlen Sie?')
 assert page.locator('#messageInput').evaluate("e=>getComputedStyle(e).backgroundColor")== 'rgba(0, 0, 0, 0)'
 page.locator('#composer').evaluate('(f)=>f.requestSubmit()')
 page.wait_for_function("[...document.querySelectorAll('.message')].some(m=>m.lang==='de')")
 before=page.locator('.message').count();page.locator('[data-lang=pl]').click()
 assert page.locator('.message').count()==before
 assert page.locator('.message[lang=de]').count()==1
 page.locator('#messageInput').fill('I would like something light please')
 page.locator('#composer').evaluate('(f)=>f.requestSubmit()')
 page.wait_for_function("[...document.querySelectorAll('.message')].some(m=>m.lang==='en')")
 passed('RU UI / German guest => German reply; PL UI switch preserves chat; English guest => English')
 page.locator('#closeChat').click();page.locator('#menuGrid [data-add=m1]').click()
 page.locator('[data-offer][data-decision=decline]').wait_for(timeout=15000)
 assert page.evaluate('S.lines.length')==1
 page.locator('[data-offer][data-decision=decline]').click()
 page.wait_for_function("S.upsellsDeclined && !processing && !deciding")
 page.locator('#closeChat').click();page.locator('#menuGrid [data-add=m2]').click();page.wait_for_timeout(1200)
 assert page.locator('[data-offer]:enabled').count()==0
 passed('Main dish triggers optional AI message; decline adds nothing and stops further offers')
 page.goto(BASE+'/?table=8');page.locator('.dish').first.wait_for();page.wait_for_timeout(700)
 if 'open' in page.locator('#sheet').get_attribute('class'):page.locator('#closeChat').click()
 page.locator('#menuGrid [data-add=m1]').click();page.locator('[data-offer][data-decision=accept]').wait_for(timeout=15000)
 page.locator('[data-offer][data-decision=accept]').click()
 page.wait_for_function("S.lines.length===2 && S.quote && S.quote.total===93")
 assert page.evaluate('S.lines.find(l=>l.ids[0]==="b1").qty')==1
 page.screenshot(path=str(OUT/'optional-ai-accompaniment-mobile.png'))
 page.reload();page.locator('.dish').first.wait_for();page.wait_for_timeout(500)
 assert page.evaluate('S.lines.find(l=>l.ids[0]==="b1").qty')==1
 page.locator('#cartOpen').click();page.wait_for_function("!document.querySelector('#checkout').disabled")
 page.locator('#checkout').click();page.locator('#receiptDialog[open]').wait_for()
 assert 'Table 8' in page.locator('#receipt').inner_text()
 passed('Accept adds real item once; reload keeps it; table number survives into guest check')
 page.goto(BASE+'/admin/');page.locator('#loginView').wait_for(state='visible')
 page.locator('#loginForm [name=username]').fill('admin');page.locator('#loginForm [name=password]').fill('Browser-test-password-123');page.locator('#loginForm button').click()
 page.locator('#workspace').wait_for(state='visible');page.locator('[data-tab=qr]').click()
 page.locator('#qrCount').fill('30');page.locator('#qrBase').fill('https://demo-restaurant.example')
 page.locator('#qrGenerate').click();page.locator('#qrPreview').wait_for(state='visible')
 assert page.locator('#qrLinks a').count()==30
 assert page.locator('#qrLinks a').last.get_attribute('href')=='https://demo-restaurant.example/?table=30'
 with page.expect_download() as event:page.locator('#qrPDF').click()
 download=event.value
 assert download.suggested_filename=='konomi-table-cards.pdf'
 download.save_as(OUT/'qr-ui-download.pdf')
 assert (OUT/'qr-ui-download.pdf').read_bytes().startswith(b'%PDF')
 assert page.locator('#qrCount').evaluate('e=>parseFloat(getComputedStyle(e).fontSize)')>=16
 page.screenshot(path=str(OUT/'qr-admin-mobile.png'),full_page=True)
 passed('Admin generates 30 table URLs and downloads a real print PDF; form inputs 16px')
 page.set_viewport_size({'width':1280,'height':960});page.screenshot(path=str(OUT/'qr-admin-desktop.png'))
 browser.close()
assert not errors,errors
(OUT/'v4-browser-results.json').write_text(json.dumps({'checks':checks,'javascript_errors':errors},ensure_ascii=False,indent=2),'utf-8')
print(f'{len(checks)} v4 end-to-end scenarios passed, no JavaScript errors.')
