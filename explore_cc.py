# explore_cc.py
import requests, re, json

url = "https://commoditieschart.net/metals/copper/shfe-copper-stocks"
r = requests.get(url, timeout=15, headers={
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
})
print(f"Status: {r.status_code}, Size: {len(r.text)}")

if r.status_code != 200:
    print("Trying Playwright...")
    import asyncio
    async def main():
        from playwright.async_api import async_playwright
        captured = {}
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            async def on_resp(resp):
                u = resp.url
                if resp.status == 200 and ("api" in u or "data" in u or "stock" in u or "shfe" in u):
                    try:
                        body = await resp.text()
                        if len(body) > 500:
                            captured[u] = body
                            print(f"  CAPTURED: {len(body):>8} bytes | {u[:100]}")
                    except: pass
            page.on("response", on_resp)
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(5000)
            
            # Check for ALL button
            for btn in await page.query_selector_all("button"):
                t = (await btn.inner_text()).strip().upper()
                if t in ("ALL", "MAX", "10Y"):
                    if await btn.is_visible():
                        print(f"  Clicking {t}...")
                        await btn.click()
                        await page.wait_for_timeout(5000)
                        break
            
            # Print captured data summaries
            for u, body in captured.items():
                try:
                    d = json.loads(body)
                    if isinstance(d, list) and d:
                        print(f"\n  {u[:80]}")
                        print(f"  Array: {len(d)} items, first={json.dumps(d[0])[:200]}")
                        print(f"  last={json.dumps(d[-1])[:200]}")
                    elif isinstance(d, dict):
                        for k, v in d.items():
                            if isinstance(v, list) and len(v) > 10:
                                print(f"\n  {u[:80]}")
                                print(f"  key='{k}': {len(v)} items")
                                print(f"  first={json.dumps(v[0])[:200]}")
                                print(f"  last={json.dumps(v[-1])[:200]}")
                except: pass
            
            await browser.close()
    asyncio.run(main())
else:
    text = r.text
    # Look for embedded data
    dates = re.findall(r'20[012]\d-\d{2}-\d{2}', text)
    print(f"Dates found: {len(dates)}, first={dates[:3] if dates else 'none'}")
    scripts = re.findall(r'<script[^>]*>(.+?)</script>', text, re.DOTALL)
    for i, s in enumerate(scripts):
        if len(s) > 3000:
            print(f"Script #{i}: {len(s)} chars")
            if any(x in s for x in ['date', 'stock', 'shfe', '2024', '2025']):
                print(s[:500])