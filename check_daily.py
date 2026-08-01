from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto('http://localhost:8000/#/scenario')
    page.wait_for_load_state('networkidle', timeout=30000)
    page.wait_for_timeout(3000)
    page.screenshot(path='/workspace/debug_scenario.png', full_page=False)
    import re
    periods = page.locator('text=/1day|4hour|1hour|7day|日线|周线/').all_text_contents()
    print('周期相关文本:', periods[:10])
    ds = page.locator('text=/real|synthetic|真实|合成|缓存/').all_text_contents()
    print('数据源提示:', ds[:5])
    charts = page.locator('canvas').count()
    print('canvas数量:', charts)
    browser.close()
