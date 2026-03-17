"""
フィルタ済み一覧ページの構造確認 v2
ウォームアップなし、motir.go.kr に直接アクセス
"""
import asyncio
from playwright.async_api import async_playwright

async def check():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(locale="ko-KR", user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0")
        page = await ctx.new_page()

        # motir.go.kr に直接アクセス（ウォームアップなし）
        url = "https://www.motir.go.kr/kor/article/ATCL3f49a5a8c?searchCondition=1&searchKeyword=%EC%88%98%EC%B6%9C%EC%9E%85+%EB%8F%99%ED%96%A5"
        print(f"=== Trying: {url}")
        
        for strategy in ["networkidle", "domcontentloaded", "load"]:
            try:
                print(f"  Strategy: {strategy}...")
                await page.goto(url, wait_until=strategy, timeout=20000)
                print(f"  OK! Final URL: {page.url}")
                break
            except Exception as e:
                print(f"  Failed: {str(e)[:100]}")
        
        await asyncio.sleep(2)
        title = await page.title()
        print(f"  Title: {title}")

        rows = await page.query_selector_all("table tbody tr")
        print(f"\n=== Table rows: {len(rows)} ===")
        for i, row in enumerate(rows[:10]):
            link = await row.query_selector("a")
            href = await link.get_attribute("href") if link else "NO_LINK"
            title = (await link.inner_text()).strip() if link else "NO_TITLE"
            print(f"  [{i}] title={title[:80]}")
            print(f"       href={href}")

        await browser.close()

asyncio.run(check())
