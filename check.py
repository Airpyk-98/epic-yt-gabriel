from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.on('console', lambda msg: print(f'CONSOLE: {msg.text}'))
    page.on('pageerror', lambda err: print(f'ERROR: {err}'))
    print("Navigating...")
    page.goto('https://epic-yt-gab.web.app/')
    page.wait_for_timeout(3000)
    browser.close()
