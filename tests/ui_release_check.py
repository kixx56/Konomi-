"""Extra UI checks for admin aliases, model picker, diagnostics and SVG semantics.
Run only on the isolated server used by browser_check.py.
"""
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE=os.getenv('KONOMI_TEST_URL','http://127.0.0.1:8000')
OUT=Path(os.getenv('KONOMI_SCREENSHOTS',str(Path(__file__).parent/'artifacts')))
OUT.mkdir(parents=True,exist_ok=True)
errors=[]
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1280,'height':960})
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto(BASE);page.locator('.dish').first.wait_for()
    assert page.locator('[data-filter="pork"] svg[data-symbol="pork-off"]').count()==1
    assert page.locator('[data-filter="gluten"] svg[data-symbol="grain-off"]').count()==1
    page.wait_for_timeout(700)
    page.screenshot(path=str(OUT/'guest-icons-desktop.png'))
    page.goto(BASE+'/admin/');page.locator('#loginView').wait_for(state='visible')
    page.locator('#loginForm [name=username]').fill('admin')
    page.locator('#loginForm [name=password]').fill('Browser-test-password-123')
    page.locator('#loginForm button[type=submit]').click();page.locator('#workspace').wait_for(state='visible')
    page.locator('[data-tab=settings]').click()
    page.wait_for_function("document.querySelector('#deployDiagnostics').textContent.includes('4.0.0-dining')")
    assert page.locator('#settingModel').input_value()=='auto'
    assert page.locator('#loadModels').is_visible()
    # A fake API response validates picker behavior, without a paid provider request.
    page.route('**/api/admin/ai/models?refresh=true',lambda route:route.fulfill(json={'models':[{'id':'gemini-test-flash','label':'Test Flash'}],'selected':'auto'}))
    page.locator('#loadModels').click()
    page.wait_for_function("document.querySelector('#settingModel').options.length===2")
    page.locator('#settingModel').select_option('gemini-test-flash')
    assert page.locator('#settingModel').input_value()=='gemini-test-flash'
    # Restore unsaved auto; don't save a mock model into settings.
    page.locator('#settingModel').select_option('auto')
    page.locator('[data-tab=overview]').click();page.locator('[data-tab=settings]').click()
    page.wait_for_function("document.querySelector('#settingModel').options.length===1")
    page.wait_for_timeout(800)
    page.screenshot(path=str(OUT/'admin-settings-desktop.png'))
    page.set_viewport_size({'width':390,'height':844});page.goto(BASE);page.locator('.dish').first.wait_for();page.wait_for_timeout(600)
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.screenshot(path=str(OUT/'guest-icons-mobile.png'))
    browser.close()
assert not errors,errors
print('PASS: semantic pig/grain icons, /admin/ login, discovered model picker, deployment diagnostics, mobile viewport. No JS errors.')
