# explore_all.py
import asyncio, json

async def main():
    from playwright.async_api import async_playwright
    
    captured = {}
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        async def on_response(response):
            url = response.url
            if "/api/shfe/" in url or "/api/comex/" in url:
                try:
                    body = await response.text()
                    data = json.loads(body)
                    count = len(data.get("data", []))
                    rng = data.get("range", "?")
                    first = data["data"][0]["date"] if count > 0 else "?"
                    last = data["data"][-1]["date"] if count > 0 else "?"
                    key = url.split("metalcharts.org")[1]
                    captured[key] = count
                    print(f"  API: {key}")
                    print(f"       range={rng}, count={count}, {first} ~ {last}")
                except:
                    pass
        
        page.on("response", on_response)
        
        # Load SHFE copper page
        print("=== Loading SHFE Copper ===")
        await page.goto("https://metalcharts.org/shfe/copper", wait_until="networkidle")
        await page.wait_for_timeout(3000)
        
        # Find and list all buttons
        print("\n=== Available buttons ===")
        buttons = await page.query_selector_all("button")
        for btn in buttons:
            text = (await btn.inner_text()).strip()
            if text and len(text) < 20:
                visible = await btn.is_visible()
                print(f"  Button: '{text}' (visible={visible})")
        
        # Click ALL button and wait for new API calls
        print("\n=== Clicking ALL button ===")
        clicked = False
        for btn in buttons:
            text = (await btn.inner_text()).strip()
            if text.upper() == "ALL":
                visible = await btn.is_visible()
                if visible:
                    print(f"  Clicking '{text}'...")
                    await btn.click()
                    clicked = True
                    await page.wait_for_timeout(5000)
                    break
        
        if not clicked:
            print("  ALL button not found, trying other selectors...")
            try:
                await page.click("text=ALL", timeout=5000)
                await page.wait_for_timeout(5000)
            except:
                print("  Could not click ALL")
        
        # Also try COMEX copper page
        print("\n=== Loading COMEX Copper ===")
        page2 = await browser.new_page()
        page2.on("response", on_response)
        await page2.goto("https://metalcharts.org/comex/copper", wait_until="networkidle")
        await page2.wait_for_timeout(3000)
        
        # Click ALL on COMEX page
        buttons2 = await page2.query_selector_all("button")
        for btn in buttons2:
            text = (await btn.inner_text()).strip()
            if text.upper() == "ALL":
                visible = await btn.is_visible()
                if visible:
                    print(f"  Clicking ALL on COMEX page...")
                    await btn.click()
                    await page2.wait_for_timeout(5000)
                    break
        
        await page2.close()
        await page.close()
        await browser.close()
    
    print(f"\n=== Summary: {len(captured)} API calls ===")
    for url, count in sorted(captured.items()):
        print(f"  {count:>6} records | {url}")

asyncio.run(main())