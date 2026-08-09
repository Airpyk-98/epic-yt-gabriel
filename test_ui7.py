from playwright.sync_api import sync_playwright
import time

def test_run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.on("console", lambda msg: print(f"Browser console: {msg.text}"))
        
        try:
            page.goto('https://epic-yt-gab.web.app/')
            time.sleep(2)
            
            if page.locator('#authEmail').is_visible():
                page.fill('#authEmail', 'gabrielyoutubeautomation@gmail.com')
                page.fill('#authPassword', 'Airpyk98')
                page.click('#authSubmitBtn')
            
            try:
                page.wait_for_selector('#videoTitles', timeout=5000)
            except:
                page.wait_for_selector('.project-card', timeout=10000)
                page.click('.project-card')
                page.wait_for_selector('#videoTitles', timeout=5000)
            
            page.fill('#videoTitles', 'Is not going to the gym really linked to being broke?')
            
            file_input = page.locator('#mediaFile')
            file_input.set_input_files('test_image.png')
            
            page.select_option('#videoModelSelect', 'aptavatar')

            
            preview_toggle = page.locator('#previewScriptToggle')
            is_checked = preview_toggle.evaluate('el => el.checked')
            if is_checked:
                preview_toggle.uncheck()
                
            time.sleep(2)
            page.click('#submitContentBtn')
            
            page.wait_for_selector('#queue-status-0', timeout=30000)
            status_el = page.locator('#queue-status-0')
            
            last_text = ""
            start_time = time.time()
            while True:
                text = status_el.inner_text()
                if text != last_text:
                    print(f"Status changed to: {text}")
                    last_text = text
                    
                if "SUCCESS" in text.upper() or "FAILED" in text.upper() or "ERROR" in text.upper():
                    print("Finished with status:", text)
                    time.sleep(2)
                    full_text = page.locator('#bulkQueueList').inner_text()
                    print("\n--- FULL QUEUE OUTPUT ---")
                    print(full_text)
                    print("-------------------------\n")
                    break
                    
                if time.time() - start_time > 60 * 25: 
                    print("Timeout waiting for job completion")
                    break
                    
                time.sleep(5)
                
        except Exception as e:
            print("Error during test:", e)
        finally:
            browser.close()

test_run()
