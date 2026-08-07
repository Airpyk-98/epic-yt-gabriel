import sys
import time
import json
import asyncio
from playwright.async_api import async_playwright

async def run_audit():
    results = {
        "auth_test": {},
        "navigation_test": {},
        "projects_test": {},
        "settings_test": {},
        "studio_test": {},
        "logs_test": {},
        "console_errors": [],
        "uncaught_exceptions": [],
        "dialogs": []
    }

    async with async_playwright() as p:
        # Launch chromium browser with 1280x800 viewport
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 800})
        page = await context.new_page()

        # Capture console messages & errors
        def on_console(msg):
            print(f"[CONSOLE {msg.type}] {msg.text}")
            results["console_errors"].append({"type": msg.type, "text": msg.text})

        def on_page_error(exc):
            print(f"[UNCAUGHT EXCEPTION] {exc}")
            results["uncaught_exceptions"].append(str(exc))

        def on_dialog(dialog):
            print(f"[DIALOG {dialog.type}] {dialog.message}")
            results["dialogs"].append({"type": dialog.type, "message": dialog.message})
            asyncio.create_task(dialog.accept())

        page.on("console", on_console)
        page.on("pageerror", on_page_error)
        page.on("dialog", on_dialog)

        print("--- Step 1: Navigating to live web app ---")
        url = "https://epic-yt-gab.web.app"
        response = await page.goto(url)
        print(f"Page loaded status: {response.status}")
        await page.wait_for_timeout(1000)

        # Screenshot 1: Auth overlay
        await page.screenshot(path="c:/Users/DELL/Desktop/Epic YT Gabriel/.agents/explorer_1/screenshot_01_auth.png")

        # Test Auth
        email = "gabrielyoutubeautomation@gmail.com"
        pwd = "Airpyk98"
        print(f"Logging in with email={email}")
        await page.fill("#authEmail", email)
        await page.fill("#authPassword", pwd)
        await page.click("#authSubmitBtn")
        await page.wait_for_timeout(3000)

        auth_overlay_visible = await page.is_visible("#authOverlay")
        print(f"Auth overlay visible after submit: {auth_overlay_visible}")

        results["auth_test"] = {
            "logged_in": not auth_overlay_visible,
            "used_email": email
        }

        # Screenshot 2: Dashboard after login
        await page.screenshot(path="c:/Users/DELL/Desktop/Epic YT Gabriel/.agents/explorer_1/screenshot_02_dashboard.png")

        badge_text = await page.inner_text("#activeProjectBadge")
        print(f"Active Project Badge: '{badge_text}'")

        # Helper function to open drawer safely
        async def ensure_drawer_open():
            is_open = await page.evaluate("document.getElementById('navDrawer').classList.contains('open')")
            if not is_open:
                await page.click("#hamburgerBtn")
                await page.wait_for_timeout(300)

        async def ensure_drawer_closed():
            is_open = await page.evaluate("document.getElementById('navDrawer').classList.contains('open')")
            if is_open:
                await page.click("#closeDrawerBtn")
                await page.wait_for_timeout(300)

        # Step 2: Test Navigation Links
        print("--- Step 2: Testing Navigation Drawer ---")
        views = ["view-dashboard", "view-projects", "view-settings", "view-logs"]
        nav_results = {}
        for target in views:
            await ensure_drawer_open()
            link_selector = f'a.nav-link[data-target="{target}"]'
            await page.click(link_selector)
            await page.wait_for_timeout(800)
            is_active = await page.evaluate(f"document.getElementById('{target}').classList.contains('active')")
            nav_results[target] = is_active
            print(f"View transition to '{target}': {'SUCCESS' if is_active else 'FAILED'}")
            await ensure_drawer_closed()
            await page.screenshot(path=f"c:/Users/DELL/Desktop/Epic YT Gabriel/.agents/explorer_1/screenshot_nav_{target}.png")
        results["navigation_test"] = nav_results

        # Step 3: Projects View & Creation
        print("--- Step 3: Testing Projects View ---")
        await ensure_drawer_open()
        await page.click('a.nav-link[data-target="view-projects"]')
        await page.wait_for_timeout(800)
        await ensure_drawer_closed()

        test_proj_name = f"QA_Project_{int(time.time())}"
        print(f"Submitting new project name: {test_proj_name}")
        await page.fill("#newProjectName", test_proj_name)
        await page.click('#createProjectForm button[type="submit"]')
        await page.wait_for_timeout(2500)
        await page.screenshot(path="c:/Users/DELL/Desktop/Epic YT Gabriel/.agents/explorer_1/screenshot_04_projects.png")

        updated_badge = await page.inner_text("#activeProjectBadge")
        print(f"Updated Active Project Badge: '{updated_badge}'")

        # Test Connect YouTube Button
        print("Testing Connect YouTube button...")
        yt_btns = page.locator(".btn-yt")
        if await yt_btns.count() > 0:
            await yt_btns.first.click()
            await page.wait_for_timeout(1000)

        # Step 4: Settings View
        print("--- Step 4: Testing Settings View ---")
        await ensure_drawer_open()
        await page.click('a.nav-link[data-target="view-settings"]')
        await page.wait_for_timeout(800)
        await ensure_drawer_closed()
        await page.screenshot(path="c:/Users/DELL/Desktop/Epic YT Gabriel/.agents/explorer_1/screenshot_05_settings.png")

        # Test Fetch Models with empty vs filled inputs
        print("Testing Fetch Models...")
        await page.click("#fetchModelsBtn")
        await page.wait_for_timeout(1000)
        status1 = await page.inner_text("#fetchModelsStatus")
        print(f"Fetch models status (empty): '{status1}'")

        await page.fill("#aiBaseUrl", "https://api.openai.com/v1")
        await page.fill("#aiApiKey", "sk-test-dummy-key-qa-audit")
        await page.click("#fetchModelsBtn")
        await page.wait_for_timeout(2000)
        status2 = await page.inner_text("#fetchModelsStatus")
        print(f"Fetch models status (with key): '{status2}'")

        # Save settings
        print("Saving Settings...")
        await page.fill("#aiSystemPrompt", "Generate ultra viral YouTube Shorts scripts under 60 seconds with hooks.")
        await page.check("#autoPostToggle")
        await page.click("#saveSettingsBtn")
        await page.wait_for_timeout(2000)

        # Step 5: Dashboard Script & Video Generation Workflows
        print("--- Step 5: Testing Script Generation ---")
        await ensure_drawer_open()
        await page.click('a.nav-link[data-target="view-dashboard"]')
        await page.wait_for_timeout(800)
        await ensure_drawer_closed()

        await page.fill("#videoTitles", "10 Shocking Facts About Space That Will Blow Your Mind")
        await page.click("#genScriptBtn")
        await page.wait_for_timeout(3500)
        await page.screenshot(path="c:/Users/DELL/Desktop/Epic YT Gabriel/.agents/explorer_1/screenshot_06_script_gen.png")

        script_area_visible = await page.is_visible("#scriptResultArea")
        gen_script_val = await page.input_value("#generatedScriptText") if script_area_visible else ""
        print(f"Script result visible: {script_area_visible}, generated length: {len(gen_script_val)}")

        # Step 6: Testing Video Generation Form & Upload
        print("--- Step 6: Testing Video Generation Form ---")
        # Check launch button disabled status
        btn_disabled = await page.is_disabled("#submitVideoBtn")
        print(f"Launch GPU button disabled: {btn_disabled}")

        # Create a dummy portrait image file to test upload
        dummy_img_path = "c:/Users/DELL/Desktop/Epic YT Gabriel/.agents/explorer_1/test_portrait.png"
        import PIL.Image as PILImage
        img = PILImage.new('RGB', (1080, 1920), color = (73, 109, 137))
        img.save(dummy_img_path)

        await page.set_input_files("#mediaFile", dummy_img_path)
        await page.wait_for_timeout(500)
        filename_text = await page.inner_text("#fileName")
        print(f"File upload status text: '{filename_text}'")

        btn_disabled_after_file = await page.is_disabled("#submitVideoBtn")
        print(f"Launch GPU button disabled after file upload: {btn_disabled_after_file}")

        # Try submitting video generation form if enabled
        if not btn_disabled_after_file:
            print("Submitting video generation form...")
            await page.click("#submitVideoBtn")
            await page.wait_for_timeout(4000)
            await page.screenshot(path="c:/Users/DELL/Desktop/Epic YT Gabriel/.agents/explorer_1/screenshot_07_video_sub.png")

        # Step 7: Execution Logs View
        print("--- Step 7: Testing Execution Logs ---")
        await ensure_drawer_open()
        await page.click('a.nav-link[data-target="view-logs"]')
        await page.wait_for_timeout(1000)
        await ensure_drawer_closed()
        await page.screenshot(path="c:/Users/DELL/Desktop/Epic YT Gabriel/.agents/explorer_1/screenshot_08_logs.png")

        logs_inner = await page.inner_text("#executionLogsList")
        print(f"Logs view text content: '{logs_inner.strip()}'")

        # Step 8: Session Persistence & Logout
        print("--- Step 8: Session Persistence & Logout ---")
        print("Reloading page...")
        await page.reload()
        await page.wait_for_timeout(3000)
        reloaded_overlay = await page.is_visible("#authOverlay")
        print(f"After page reload, Auth Overlay visible: {reloaded_overlay}")
        results["auth_test"]["session_persisted"] = not reloaded_overlay

        print("Testing Logout...")
        await ensure_drawer_open()
        await page.click("#logoutBtn")
        await page.wait_for_timeout(2000)
        post_logout_overlay = await page.is_visible("#authOverlay")
        print(f"After logout, Auth Overlay visible: {post_logout_overlay}")
        results["auth_test"]["logout_successful"] = post_logout_overlay

        await page.screenshot(path="c:/Users/DELL/Desktop/Epic YT Gabriel/.agents/explorer_1/screenshot_09_logout.png")

        await browser.close()

    with open("c:/Users/DELL/Desktop/Epic YT Gabriel/.agents/explorer_1/raw_audit_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("Audit run finished successfully!")

if __name__ == "__main__":
    asyncio.run(run_audit())
