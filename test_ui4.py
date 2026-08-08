from playwright.sync_api import sync_playwright
import time

def test_run():
    with sync_playwright() as p:
        print("Launching browser...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        
        try:
            print("Navigating to https://epic-yt-gab.web.app...")
            page.goto('https://epic-yt-gab.web.app/')
            
            # Wait a bit for initialization
            time.sleep(2)
            
            # 1. Login
            if page.locator('#authEmail').is_visible():
                print("Logging in...")
                page.fill('#authEmail', 'gabrielyoutubeautomation@gmail.com')
                page.fill('#authPassword', 'Airpyk98')
                page.click('#authSubmitBtn')
            
            # Wait for either project cards or the studio to appear
            print("Waiting for dashboard...")
            try:
                page.wait_for_selector('#videoTitlesInput', timeout=5000)
                print("Already in Studio.")
            except:
                print("Selecting first project...")
                page.wait_for_selector('.project-card', timeout=10000)
                page.click('.project-card')
                page.wait_for_selector('#videoTitlesInput', timeout=5000)
            
            # 3. Enter details
            print("Entering video titles...")
            page.fill('#videoTitlesInput', 'Is not going to the gym really linked to being broke?')
            
            # 4. Upload image
            print("Uploading image...")
            file_input = page.locator('#mediaFileInput')
            file_input.set_input_files('test_image.png')
            
            # 5. Disable preview mode
            print("Disabling preview script mode...")
            preview_toggle = page.locator('#previewScriptToggle')
            is_checked = preview_toggle.evaluate('el => el.checked')
            if is_checked:
                preview_toggle.uncheck()
                
            # Wait for button to enable
            time.sleep(2)
            
            # 6. Click submit
            print("Submitting...")
            page.click('#submitContentBtn')
            
            # 7. Monitor status
            print("Waiting for job completion...")
            
            page.wait_for_selector('#queue-status-0', timeout=10000)
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
                    break
                    
                if time.time() - start_time > 60 * 15: # 15 mins timeout
                    print("Timeout waiting for job completion")
                    break
                    
                time.sleep(5)
                
        except Exception as e:
            print("Error during test:", e)
            page.screenshot(path="error_shot4.png")
            print("Saved error_shot4.png")
            
        finally:
            browser.close()

test_run()
