from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    # 访问情景分析页，默认 1day
    page.goto('http://localhost:8000/#/scenario?sub=饰品指数&period=1day')
    page.wait_for_load_state('networkidle', timeout=30000)
    page.wait_for_timeout(5000)
    page.screenshot(path='/workspace/debug_daily.png', full_page=False)
    # 获取 K 线图 canvas 信息
    canvases = page.locator('canvas').all()
    print(f'canvas数量: {len(canvases)}')
    # 获取页面文本
    text = page.locator('body').inner_text()
    # 找 K 线相关文字
    import re
    # 找 "根K线" "data_source" 等关键词
    for kw in ['根K线', 'real', 'synthetic', '真实', '合成', '缓存', 'data_source', '饰品指数', '1day', '日线']:
        matches = [l for l in text.split('\n') if kw in l]
        if matches:
            print(f'[{kw}]: {matches[:3]}')
    browser.close()
