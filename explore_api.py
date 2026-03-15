# explore_api3.py
# pip install playwright && python -m playwright install chromium
import asyncio

async def main():
    from playwright.async_api import async_playwright
    
    captured = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Intercept API responses
        async def handle_response(response):
            url = response.url
            if "/api/shfe/" in url:
                status = response.status
                body = ""
                try:
                    body = await response.text()
                except:
                    pass
                captured.append({"url": url, "status": status, "size": len(body)})
                print(f"  CAPTURED: {status} | {len(body):>7} bytes | {url}")
                if len(body) > 100:
                    print(f"  PREVIEW: {body[:500]}")
                    print()
        
        page.on("response", handle_response)
        
        print("Loading https://metalcharts.org/shfe/copper ...")
        await page.goto("https://metalcharts.org/shfe/copper", wait_until="networkidle")
        print(f"\nPage loaded. Captured {len(captured)} API calls.")
        
        # Wait a bit more for lazy-loaded data
        await page.wait_for_timeout(3000)
        print(f"After wait: {len(captured)} API calls total.")
        
        await browser.close()

asyncio.run(main())