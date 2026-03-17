"""
欠損月のICTレポート記事を探す
日付フィルタ付き一覧ページからICT記事をクリックしてデータ取得
"""
import asyncio
import re
from playwright.async_api import async_playwright

# 欠損月 → 公開月の日付フィルタ
MISSING_MONTHS = [
    {"target": "2024-06", "filter_start": "2024-07-01", "filter_end": "2024-07-31"},
    {"target": "2025-02", "filter_start": "2025-03-01", "filter_end": "2025-03-31"},
    {"target": "2025-06", "filter_start": "2025-07-01", "filter_end": "2025-07-31"},
]

BASE_LIST = (
    "https://www.motir.go.kr/kor/article/ATCL3f49a5a8c"
    "?searchCondition=1&searchKeyword=%EC%88%98%EC%B6%9C%EC%9E%85+%EB%8F%99%ED%96%A5"
)


async def find_and_fetch():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            locale="ko-KR",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0",
        )
        page = await ctx.new_page()

        results = []

        for info in MISSING_MONTHS:
            target = info["target"]
            list_url = f"{BASE_LIST}&startDtD={info['filter_start']}&endDtD={info['filter_end']}"

            print(f"\n{'='*60}")
            print(f"Searching for {target} data")
            print(f"{'='*60}")

            # 一覧ページにアクセス（リトライ付き）
            for attempt in range(3):
                try:
                    await page.goto(list_url, wait_until="domcontentloaded", timeout=30000)
                    break
                except Exception as e:
                    print(f"  List attempt {attempt+1} failed: {str(e)[:80]}")
                    await asyncio.sleep(2)

            await asyncio.sleep(2)

            # ICT記事を探す
            rows = await page.query_selector_all("table tbody tr")
            print(f"  Found {len(rows)} rows")

            ict_row_idx = None
            for i, row in enumerate(rows):
                link = await row.query_selector("a")
                if not link:
                    continue
                title = (await link.inner_text()).strip()
                print(f"  [{i}] {title}")
                if ("ICT" in title or "정보통신" in title) and "수출입" in title:
                    ict_row_idx = i
                    print(f"  >>> ICT article found at [{i}]")
                    break

            if ict_row_idx is None:
                print(f"  No ICT article found for {target}")
                continue

            # クリックして記事ページへ
            rows = await page.query_selector_all("table tbody tr")
            link = await rows[ict_row_idx].query_selector("a")
            await link.click()
            await page.wait_for_load_state("domcontentloaded", timeout=30000)
            await asyncio.sleep(2)

            article_url = page.url
            title = await page.title()
            print(f"  Navigated: {title}")

            # 本文取得
            text = ""
            el = await page.query_selector("article")
            if el:
                text = await el.inner_text()
            else:
                text = await page.inner_text("body")

            # 半導体データ抽出
            main = re.search(
                r"\(반도체\s*:\s*(\d+(?:\.\d+)?)\s*억\s*(?:달러|불)\s*[,，]\s*(\d+(?:\.\d+)?)\s*%\s*([↑↓])\)",
                text,
            )
            if main:
                val = float(main.group(1))
                yoy = float(main.group(2)) * (-1 if main.group(3) == "↓" else 1)
                print(f"\n  ★ 반도체: {val}億ドル = ${val/10:.2f}B (YoY {yoy:+.1f}%)")
                results.append({
                    "ref_month": target,
                    "value_usd_billion": round(val / 10, 2),
                    "yoy_pct": yoy,
                    "source_url": article_url,
                    "raw_text": main.group(0),
                })

            # インライン推移
            trend = re.findall(
                r"\(['\u2018\u2019\u0027]?(\d{2})\.(\d{1,2})월\)\s*(\d+(?:\.\d+)?)\s*\((\d+(?:\.\d+)?)\s*([↑↓])\)",
                text,
            )
            if trend:
                print(f"\n  === インライン推移 ({len(trend)}件) ===")
                for yy, mm, val, yoy, d in trend:
                    year = 2000 + int(yy)
                    v = float(val)
                    y = float(yoy) * (-1 if d == "↓" else 1)
                    print(f"  {year}-{int(mm):02d}: ${v/10:.2f}B (YoY {y:+.1f}%)")

            # 반도체関連行
            for line in text.split("\n"):
                if "반도체" in line and ("억" in line) and ("%" in line or "↑" in line or "↓" in line):
                    print(f"  [반도체] {line.strip()[:150]}")

        # サマリー
        print(f"\n{'='*60}")
        print("SUMMARY - kr_semiconductor_history.json に追記するデータ")
        print(f"{'='*60}")
        if results:
            for r in results:
                print(f'  {{"ref_month": "{r["ref_month"]}", "value_usd_billion": {r["value_usd_billion"]}, "yoy_pct": {r["yoy_pct"]}, "source_report": "ICT", "raw_text": "{r["raw_text"]}"}}')
        else:
            print("  データが見つかりませんでした")

        # 2023-12 も出力（既に確認済み）
        print(f"\n  ※ 2023-12 は既に確認済み:")
        print(f'  {{"ref_month": "2023-12", "value_usd_billion": 11.07, "yoy_pct": 19.3, "source_report": "ICT", "raw_text": "(반도체 : 110.7억불, 19.3%↑)"}}')

        await browser.close()

asyncio.run(find_and_fetch())
