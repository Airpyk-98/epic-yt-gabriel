from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.on('pageerror', lambda err: print(f'ERROR: {err.name} {err.message}\n{err.stack}'))
    
    def handle_request(route, request):
        print(f'FETCHING: {request.url}')
        route.continue_()
    
    page.route('**/*', handle_request)
    
    print("Navigating...")
    page.goto('https://epic-yt-gab.web.app/')
    page.wait_for_timeout(3000)
    browser.close()
