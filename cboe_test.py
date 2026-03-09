#!/usr/bin/env python3
"""
CBOEページの構造を確認するテストスクリプト。
1日分だけ取得してHTMLとテキストをダンプする。

pip install playwright
playwright install chromium
python cboe_test.py
"""
import asyncio
import re
from playwright.async_api import async_playwright


async def main():
    test_date = "2025-03-07"  # 直近の金曜日
    url = f"https://www.cboe.com/us/options/market_statistics/daily/?dt={test_date}"

    print(f"Testing: {url}")
    print("=" * 60)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto(url, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(5000)  # JS描画を十分待つ

        text = await page.inner_text("body")

        # テキスト全体を保存
        with open("cboe_page_text.txt", "w", encoding="utf-8") as f:
            f.write(text)
        print("📄 Full text saved → cboe_page_text.txt")

        # HTML も保存
        html = await page.content()
        with open("cboe_page_html.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("📄 Full HTML saved → cboe_page_html.html")

        # PUT/CALL RATIO を探す
        print("\n🔍 Searching for PUT/CALL patterns...")
        for pattern in [
            r"(?i)put.?call.?ratio",
            r"(?i)total.*ratio",
            r"(?i)index.*ratio",
            r"(?i)equity.*ratio",
            r"(?i)etp.*ratio",
            r"(?i)P/C\s+Ratio",
        ]:
            matches = re.findall(rf"(.{{0,60}}{pattern}.{{0,60}})", text)
            for m in matches[:3]:
                print(f"  ✅ {m.strip()}")

        # 数値パターンも探す
        print("\n🔍 Searching for ratio values...")
        for pattern in [
            r"(?i)TOTAL\s+PUT/CALL\s+RATIO\s+([\d.]+)",
            r"(?i)INDEX\s+PUT/CALL\s+RATIO\s+([\d.]+)",
            r"(?i)EQUITY\s+PUT/CALL\s+RATIO\s+([\d.]+)",
            r"(?i)(?:ETP|EXCHANGE.TRADED)\s+PUT/CALL\s+RATIO\s+([\d.]+)",
            r"(?i)PUT/CALL\s+RATIO\s+([\d.]+)",
            r"(?i)P/C\s+RATIO\s+([\d.]+)",
        ]:
            m = re.search(pattern, text)
            if m:
                print(f"  ✅ Found: {m.group(0)}")

        if not re.search(r"(?i)put.?call", text):
            print("\n⚠️  'put/call' がテキスト中に見つかりません。")
            print("  ページが正しくレンダリングされていない可能性があります。")
            print(f"\n  テキスト先頭500文字:\n  {text[:500]}")

        await browser.close()

    print("\n✅ Done. cboe_page_text.txt を確認してください。")


if __name__ == "__main__":
    asyncio.run(main())
