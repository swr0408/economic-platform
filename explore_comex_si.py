# explore_comex_si.py
import asyncio, json

async def main():
    from playwright.async_api import async_playwright
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        async def on_response(response):
            url = response.url
            if "/api/comex/" not in url:
                return
            if response.status != 200:
                return
            try:
                body = await response.text()
                data = json.loads(body)
                path = url.split("metalcharts.org")[1]
                items = data.get("data", [])
                
                print(f"\n=== {path} ===")
                print(f"  success={data.get('success')}, range={data.get('range','?')}")
                
                if isinstance(items, list) and items:
                    print(f"  count={len(items)}")
                    print(f"  first: {json.dumps(items[0], indent=2)}")
                    if len(items) > 1:
                        print(f"  last:  {json.dumps(items[-1], indent=2)}")
                elif isinstance(items, dict):
                    print(f"  data: {json.dumps(items, indent=2)[:1000]}")
                elif isinstance(items, list) and not items:
                    # Check other keys
                    for k, v in data.items():
                        if k not in ("success", "symbol", "range"):
                            print(f"  {k}: {json.dumps(v, indent=2)[:500]}")
            except:
                pass
        
        page.on("response", on_response)
        
        print("Loading COMEX Silver...")
        await page.goto("https://metalcharts.org/comex/silver", wait_until="networkidle")
        await page.wait_for_timeout(3000)
        
        # Click ALL
        buttons = await page.query_selector_all("button")
        for btn in buttons:
            text = (await btn.inner_text()).strip().upper()
            if text == "ALL":
                visible = await btn.is_visible()
                if visible:
                    print("\nClicking ALL...")
                    await btn.click()
                    await page.wait_for_timeout(5000)
                    break
        
        await page.close()
        await browser.close()

asyncio.run(main())
