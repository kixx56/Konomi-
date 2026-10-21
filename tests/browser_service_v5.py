"""Real Chromium staff/guest acceptance path. Isolated database only."""
import os
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
BASE=os.environ.get('KONOMI_TEST_URL','http://127.0.0.1:18777')
OUT=Path(os.environ.get('KONOMI_SCREENSHOTS','/home/user/konomi-v5-previews'));OUT.mkdir(parents=True,exist_ok=True)
errors=[];checks=[]
def ok(message):checks.append(message);print('PASS:',message)
with sync_playwright() as p:
    browser=p.chromium.launch(args=['--no-sandbox'])
    guest_context=browser.new_context(viewport={'width':390,'height':844},locale='ru-RU')
    staff_context=browser.new_context(viewport={'width':1366,'height':1000},accept_downloads=True)
    g=guest_context.new_page();a=staff_context.new_page()
    for page in (g,a):page.on('pageerror',lambda err:errors.append(str(err)))
    a.goto(BASE+'/admin/');a.locator('#loginForm [name=password]').fill('Browser-test-password-123');a.locator('#loginForm button').click();a.locator('#workspace').wait_for(state='visible')
    a.locator('[data-tab=service]').click();a.locator('#hallPin').fill('7391');a.locator('#hallPinForm button').click();a.wait_for_function("document.querySelector('#hallPinStatus').textContent.includes('обновлён')")
    a.locator('#boardSound').click()
    g.goto(BASE+'/?table=23');g.locator('.dish').first.wait_for();g.wait_for_timeout(700)
    assert g.locator('#messageInput').evaluate('e=>parseFloat(getComputedStyle(e).fontSize)')>=16
    assert g.evaluate("document.activeElement.id!=='messageInput'")
    g.locator('[data-lang=pl]').click();g.locator('#messageInput').fill('Здравствуйте хочу суп');g.locator('#composer').evaluate('f=>f.requestSubmit()');g.locator('.message[lang=ru]').wait_for()
    ids=g.locator('.message[lang=ru] [data-focus]').evaluate_all('els=>els.map(e=>e.dataset.focus)');assert ids and all(x in ['s1','s2','s3'] for x in ids),ids
    ok('PL interface / Russian soup request => Russian response and only soup cards')
    g.locator('#closeChat').click();g.locator('#menuGrid [data-add=s1]').click();g.wait_for_function('S.quote && S.quote.total===31');g.locator('#cartOpen').click();g.locator('#checkout').click();g.locator('#receiptDialog[open]').wait_for();g.locator('#staffStatus').wait_for()
    code=g.locator('.checkout-code strong').inner_text();a.locator('.order-ticket').filter(has_text=code).wait_for(timeout=10000)
    g.screenshot(path=str(OUT/'guest-pending-mobile.png'))
    a.locator('[data-tab=analytics]').click();a.wait_for_function("document.querySelector('#salesStats').textContent.includes('31,00')")
    report=staff_context.request.get(BASE+'/api/admin/analytics').json();assert report['finance']['confirmed_revenue']==0,report
    ok('Guest creates a real pending check; board receives it; pending is not revenue')
    g.locator('#showStaffPIN').click();g.locator('#staffPIN').fill('0000');g.locator('#staffConfirmForm button[type=submit]').click();g.locator('#staffPINError').filter(has_text='Неверный').wait_for()
    g.locator('#staffPIN').fill('7391');g.locator('#staffConfirmForm button[type=submit]').click();g.locator('#staffStatus.accepted').wait_for()
    a.locator('[data-tab=service]').click();a.locator('.order-ticket').filter(has_text=code).locator('[data-status=ready]').wait_for(timeout=10000)
    ok('Wrong PIN rejected; staff PIN approves guest receipt and updates the kitchen')
    a.screenshot(path=str(OUT/'kitchen-board-desktop.png'),full_page=True)
    a.locator('.order-ticket').filter(has_text=code).locator('[data-status=ready]').click()
    a.locator('.order-ticket').filter(has_text=code).locator('[data-status=completed]').wait_for();a.locator('.order-ticket').filter(has_text=code).locator('[data-status=completed]').click()
    a.locator('.order-ticket').filter(has_text=code).wait_for(state='detached')
    a.locator('[data-tab=analytics]').click();a.locator('#salesHistory').filter(has_text=code).wait_for()
    report=staff_context.request.get(BASE+'/api/admin/analytics').json();assert report['finance']['confirmed_revenue']==31 and report['finance']['completed_revenue']==31
    assert report['funnel']['confirmed_sales']==1 and report['funnel']['ai_chats']==1 and report['funnel']['cart_adds']==1
    a.screenshot(path=str(OUT/'analytics-desktop.png'),full_page=True)
    ok('Ready → completed is persisted; confirmed/completed totals and funnel are exact')
    a.locator('#salesTable').fill('999');a.locator('#salesFilters button[type=submit], #salesFilters button:not([type])').first.click();a.wait_for_timeout(1000)
    assert 'Пока нет данных' in a.locator('#salesHistory').inner_text()
    a.locator('#salesTable').fill('23');a.locator('#salesFilters button:not([type])').first.click();a.locator('#salesHistory').filter(has_text=code).wait_for()
    with a.expect_download() as download:a.locator('#salesCSV').click()
    download.value.save_as(OUT/'sales-export.csv');assert code in (OUT/'sales-export.csv').read_text('utf-8-sig')
    ok('History filters table correctly; CSV download contains the confirmed sale')
    for width in (390,320):
        a.set_viewport_size({'width':width,'height':844});a.locator('[data-tab=service]').click();a.wait_for_timeout(300)
        assert a.evaluate('document.documentElement.scrollWidth<=innerWidth+1'),width
        a.locator('[data-tab=analytics]').click();a.wait_for_timeout(500)
        assert a.evaluate('document.documentElement.scrollWidth<=innerWidth+1'),width
    a.screenshot(path=str(OUT/'analytics-mobile.png'),full_page=True)
    g.reload();g.locator('.receipt-restore').wait_for();g.locator('.receipt-restore').click();g.locator('#staffStatus.accepted').wait_for()
    ok('320/390px staff screens fit; reload restores a protected guest receipt')
    browser.close()
assert not errors,errors
(OUT/'service-browser-results.json').write_text(json.dumps({'checks':checks,'javascript_errors':errors},ensure_ascii=False,indent=2))
print(len(checks),'service end-to-end scenarios passed; no JavaScript errors')
