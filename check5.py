from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    
    def handle_console(msg):
        print(f"CONSOLE [{msg.type}]: {msg.text}")
        print(f"LOCATION: {msg.location}")
        
    page.on('console', handle_console)
    
    print("Navigating...")
    page.goto('https://epic-yt-gab.web.app/')
    page.wait_for_timeout(3000)
    browser.close()
