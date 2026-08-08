from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.on('console', lambda msg: print(f'CONSOLE: {msg.text}'))
    
    def on_page_error(err):
        print(f'ERROR: {err}')
        if err.stack:
            print(err.stack)
    
    page.on('pageerror', on_page_error)
    
    print("Navigating...")
    page.goto('https://epic-yt-gab.web.app/')
    page.wait_for_timeout(3000)
    browser.close()
