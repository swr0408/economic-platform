"""
MOTIE サイト構造 診断スクリプト
================================
ローカルで実行して、実際のページHTML/リンク構造を dump する。
結果を Claude に貼り付けて scraper.py を修正する。

使い方:
    python diagnose_motie.py
"""

import asyncio
import json
import re
from playwright.async_api import async_playwright


async def diagnose():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            locale="ko-KR",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()
        page.set_default_timeout(30000)

        results = {}

        # =========================================================
        # Step 1: ドメイン確認
        # =========================================================
        print("=" * 60)
        print("Step 1: Domain check")
        print("=" * 60)

        domains = [
            "https://www.motie.go.kr",
            "https://www.motir.go.kr",
            "https://motie.go.kr",
            "https://motir.go.kr",
        ]

        for domain in domains:
            try:
                resp = await page.goto(domain, wait_until="domcontentloaded", timeout=15000)
                final_url = page.url
                status = resp.status if resp else "N/A"
                title = await page.title()
                print(f"  {domain}")
                print(f"    → status={status}, final_url={final_url}")
                print(f"    → title={title}")
                results["working_domain"] = domain
                results["final_url"] = final_url
                break
            except Exception as e:
                print(f"  {domain} → ERROR: {str(e)[:100]}")

        # =========================================================
        # Step 2: 報道資料ページ確認
        # =========================================================
        print("\n" + "=" * 60)
        print("Step 2: Press release list page")
        print("=" * 60)

        # ユーザーが共有した URL パスを試す
        press_paths = [
            "/kor/article/ATCL3f49a5a8c",
            "/kor/article/ATCL3f49a5a8c?searchCondition=1&searchKeyword=%EC%88%98%EC%B6%9C%EC%9E%85+%EB%8F%99%ED%96%A5",
        ]

        base = results.get("working_domain", "https://www.motie.go.kr")

        for path in press_paths:
            url = f"{base}{path}"
            print(f"\n  Trying: {url}")
            try:
                resp = await page.goto(url, wait_until="networkidle", timeout=20000)
                await asyncio.sleep(2)
                final_url = page.url
                title = await page.title()
                html_len = len(await page.content())
                text = await page.inner_text("body")
                print(f"    → status={resp.status if resp else 'N/A'}")
                print(f"    → final_url={final_url}")
                print(f"    → title={title}")
                print(f"    → html_len={html_len}, text_len={len(text)}")

                if html_len > 1000:
                    results["press_list_url"] = url
                    results["press_list_final"] = final_url

                    # リスト構造を探す
                    print("\n    --- Article list structure ---")
                    
                    # 全リンクからICT/수출입 동향を含むものを抽出
                    links = await page.query_selector_all("a")
                    export_links = []
                    for link in links:
                        try:
                            txt = (await link.inner_text()).strip()
                            href = await link.get_attribute("href") or ""
                            if ("수출입" in txt and "동향" in txt) or ("ICT" in txt and "동향" in txt):
                                export_links.append({"text": txt[:100], "href": href})
                        except:
                            pass

                    print(f"    Found {len(export_links)} export-related links:")
                    for i, el in enumerate(export_links[:15]):
                        print(f"      [{i}] {el['text']}")
                        print(f"          href={el['href']}")

                    results["export_links"] = export_links[:15]

                    # テーブル/リスト構造を探す
                    print("\n    --- DOM structure ---")
                    for sel in [
                        "table", "table.board", "table tbody tr",
                        "ul.board_list", "div.board_list",
                        "div.bbs_list", "div.bbs_list_wrap",
                        "div.list_wrap", "div.list_wrap ul li",
                        "div.board_type01", "div.board_type02",
                        "section.board", "div.content_list",
                    ]:
                        els = await page.query_selector_all(sel)
                        if els:
                            print(f"    {sel}: {len(els)} elements")
                            # 最初の要素の中身を見る
                            try:
                                first_html = await els[0].inner_html()
                                print(f"      first inner_html ({len(first_html)} chars): {first_html[:300]}")
                            except:
                                pass

                    break  # 最初に成功したURLで止める

            except Exception as e:
                print(f"    → ERROR: {str(e)[:200]}")

        # =========================================================
        # Step 3: 個別記事ページ確認
        # =========================================================
        print("\n" + "=" * 60)
        print("Step 3: Individual article page")
        print("=" * 60)

        # export_links から最初の有効なリンクを試す
        article_url = None
        for el in results.get("export_links", []):
            href = el.get("href", "")
            if href and href != "#" and "/view" in href or href.endswith(("view", "View")):
                article_url = href if href.startswith("http") else f"{base}{href}"
                break
            elif href and href != "#" and len(href) > 10:
                article_url = href if href.startswith("http") else f"{base}{href}"
                break

        if not article_url:
            # MOTIE検索ページを試す
            search_url = f"{base}/search/search.do?site=main&kwd=수출입+동향&category=c1"
            print(f"\n  No article link found. Trying search: {search_url}")
            try:
                await page.goto(search_url, wait_until="networkidle", timeout=20000)
                await asyncio.sleep(2)
                
                links = await page.query_selector_all("a")
                for link in links:
                    try:
                        txt = (await link.inner_text()).strip()
                        href = await link.get_attribute("href") or ""
                        if "2026" in txt and "수출입" in txt and "동향" in txt:
                            article_url = href if href.startswith("http") else f"{base}{href}"
                            print(f"    Found via search: {txt[:80]}")
                            print(f"    URL: {article_url}")
                            break
                    except:
                        pass
            except Exception as e:
                print(f"    Search error: {str(e)[:200]}")

        if article_url:
            print(f"\n  Fetching article: {article_url}")
            try:
                resp = await page.goto(article_url, wait_until="networkidle", timeout=20000)
                await asyncio.sleep(2)
                title = await page.title()
                final_url = page.url
                text = await page.inner_text("body")
                print(f"    → title: {title}")
                print(f"    → final_url: {final_url}")
                print(f"    → text_len: {len(text)}")

                # 반도체（半導体）を含む部分を抽出
                for line in text.split("\n"):
                    if "반도체" in line and ("억" in line or "달러" in line or "%" in line):
                        print(f"    [반도체] {line.strip()[:150]}")

                # 本文コンテナのセレクタを探す
                print("\n    --- Content selectors ---")
                for sel in [
                    "div.view_cont", "div.bbs_view_cont", "div.board_view_cont",
                    "div.article_cont", "div.view_content", "article",
                    "div.content_view", "div.detail_cont", "div.detail_content",
                    "div.view_area", "div.view_txt", "div.vw_cont",
                ]:
                    el = await page.query_selector(sel)
                    if el:
                        inner = await el.inner_text()
                        print(f"    {sel}: {len(inner)} chars")
                        if "반도체" in inner:
                            print(f"      ✓ Contains 반도체!")

                # 添付ファイル
                print("\n    --- Attachments ---")
                all_links = await page.query_selector_all("a")
                for link in all_links:
                    try:
                        txt = (await link.inner_text()).strip()
                        href = await link.get_attribute("href") or ""
                        if ".pdf" in txt.lower() or ".pdf" in href.lower() or ".hwp" in txt.lower():
                            print(f"    [{txt[:80]}]")
                            print(f"      href={href}")
                    except:
                        pass

                results["article_url"] = article_url
                results["article_final_url"] = final_url

            except Exception as e:
                print(f"    → ERROR: {str(e)[:200]}")
        else:
            print("  No article URL found to test")

        # =========================================================
        # Step 4: 英語版確認
        # =========================================================
        print("\n" + "=" * 60)
        print("Step 4: English site check")
        print("=" * 60)

        en_urls = [
            "https://english.motir.go.kr/eng/article/EATCLdfa319ada",
            "https://english.motie.go.kr/eng/article/EATCLdfa319ada",
        ]

        for url in en_urls:
            print(f"\n  Trying: {url}")
            try:
                resp = await page.goto(url, wait_until="networkidle", timeout=15000)
                title = await page.title()
                text_len = len(await page.inner_text("body"))
                print(f"    → status={resp.status if resp else 'N/A'}, title={title}, text_len={text_len}")
                
                if text_len > 500:
                    links = await page.query_selector_all("a")
                    for link in links:
                        try:
                            txt = (await link.inner_text()).strip()
                            href = await link.get_attribute("href") or ""
                            if "export" in txt.lower() and ("import" in txt.lower() or "trend" in txt.lower()):
                                print(f"    [{txt[:80]}] → {href}")
                            elif "ICT" in txt and ("export" in txt.lower() or "trend" in txt.lower()):
                                print(f"    [{txt[:80]}] → {href}")
                        except:
                            pass
                    break
            except Exception as e:
                print(f"    → ERROR: {str(e)[:100]}")

        # =========================================================
        # Summary
        # =========================================================
        print("\n" + "=" * 60)
        print("SUMMARY (paste this to Claude)")
        print("=" * 60)
        print(json.dumps(results, ensure_ascii=False, indent=2))

        await browser.close()


if __name__ == "__main__":
    asyncio.run(diagnose())
