"""
ISM非製造業景況指数サービス
Investing.comからスクレイピングでISM非製造業PMIデータを取得

データソース:
- Investing.com: https://jp.investing.com/economic-calendar/ism-non-manufacturing-pmi-176

発表スケジュール:
- 毎月第3営業日付近（製造業より2日遅い）
- Investing.comページから次回発表日を取得

キャッシュ方式: last_updated判定方式
- Investing.comから取得した次回発表日で判定
- 発表日を過ぎたらキャッシュを無効化して再取得
"""
import re
import calendar
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from core.redis_client import redis_client
from services.usa.fmp_next_release_utils import (
    get_next_release_from_fmp,
    should_refresh_by_fmp_schedule,
)


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")

# データソースURL
INVESTING_URL = "https://jp.investing.com/economic-calendar/ism-non-manufacturing-pmi-176"


class ISMNonManufacturingService:
    """ISM非製造業景況指数サービス"""

    CACHE_KEY = "investing:ism_non_manufacturing"
    ECONALPHA_ID = "ism_non_manufacturing"  # FMPマッピング用ID

    def __init__(self):
        pass

    def get_ism_non_manufacturing_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        ISM非製造業PMIデータを取得

        Args:
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "data": [{"date": "YYYY-MM-DD", "value": float, "forecast": float|null, "previous": float|null}, ...],
                "latest": {"date": "YYYY-MM-DD", "value": float, ...},
                "next_release": None,
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        # キャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.CACHE_KEY)
            if cached_data:
                # last_updated判定: 次の発表日を過ぎていたらキャッシュ無効
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not should_refresh_by_fmp_schedule(self.ECONALPHA_ID, last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "next_release": cached_data.get("next_release"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # 優先順位: 1. DB(FMP蓄積) → 2. スクレイピング（フォールバック）
        db_result = self._load_from_db()
        if db_result:
            # 次回発表日をFMPから取得
            next_release = self._get_next_release_from_fmp()

            cache_payload = {
                "data": db_result,
                "latest": db_result[-1] if db_result else None,
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.CACHE_KEY, cache_payload, expire=0)

            return {
                "data": db_result,
                "latest": db_result[-1] if db_result else None,
                "next_release": next_release,
                "cached": False,
                "source": "database",
                "last_updated": datetime.now(JST).isoformat()
            }

        # DBにデータがない場合はスクレイピングで取得（フォールバック）
        scraped_result = self._scrape_investing_data()

        if scraped_result and scraped_result.get("data"):
            scraped_data = scraped_result["data"]

            # 日付でソート（昇順）
            scraped_data.sort(key=lambda x: x["date"])

            # 最新値を取得
            latest = scraped_data[-1] if scraped_data else None

            cache_payload = {
                "data": scraped_data,
                "latest": latest,
                "next_release": None,
                "last_updated": datetime.now(JST).isoformat()
            }
            # last_updated方式: TTL=0（無期限、発表日判定で無効化）
            redis_client.set(self.CACHE_KEY, cache_payload, expire=0)

            return {
                "data": scraped_data,
                "latest": latest,
                "next_release": None,
                "cached": False,
                "source": "scraping",
                "last_updated": datetime.now(JST).isoformat()
            }

        return {
            "data": [],
            "latest": None,
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _load_from_db(self) -> List[Dict[str, Any]]:
        """DBから履歴データを取得"""
        try:
            from core.database import SessionLocal
            from sqlalchemy import text

            with SessionLocal() as session:
                query = text("""
                    SELECT datetime_utc, actual, estimate, previous
                    FROM economic_calendar_events
                    WHERE country = 'US'
                      AND (event ILIKE '%ISM Non-Manufacturing PMI%' OR event ILIKE '%ISM Services PMI%')
                      AND actual IS NOT NULL
                    ORDER BY datetime_utc ASC
                """)
                rows = session.execute(query).fetchall()

                result = []
                seen_dates = set()

                for row in rows:
                    dt_utc, actual, estimate, previous = row
                    if dt_utc:
                        # 月初日に正規化
                        date_str = dt_utc.strftime("%Y-%m-01")
                        if date_str in seen_dates:
                            continue
                        seen_dates.add(date_str)

                        result.append({
                            "date": date_str,
                            "value": float(actual) if actual else None,
                            "forecast": float(estimate) if estimate else None,
                            "previous": float(previous) if previous else None,
                        })

                print(f"Loaded {len(result)} ISM Non-Manufacturing records from DB")
                return result

        except Exception as e:
            print(f"Error loading from DB: {e}")
            return []

    def _get_next_release_from_fmp(self) -> Optional[Dict[str, Any]]:
        """FMP APIから次回発表日を取得"""
        try:
            from services.calendar.fmp_service import fmp_service

            today = date.today()
            # FMP APIからイベントを取得
            events = fmp_service.fetch_calendar(
                today,
                today + timedelta(days=60),
                country="US"
            )

            # 対象イベントを収集（USのみ）
            candidates = []
            for event in events:
                # USイベントのみ
                if event.get("country") != "US":
                    continue
                event_name = event.get("event", "")
                event_lower = event_name.lower()
                # ISM Services PMI または ISM Non-Manufacturing にマッチするイベントのみ
                if "ism services pmi" not in event_lower and "ism non-manufacturing" not in event_lower:
                    continue
                # 将来のイベント（actual が None）
                if event.get("actual") is None:
                    dt_utc, _ = fmp_service.parse_datetime(event.get("date", ""))
                    if dt_utc and dt_utc.date() >= today:
                        candidates.append({
                            "date": dt_utc.strftime("%Y-%m-%d"),
                            "datetime_utc": dt_utc.isoformat(),
                            "label": event_name,
                            "estimate": event.get("estimate"),
                            "_dt": dt_utc,
                        })

            # 日付順でソートして最も近いイベントを返す
            if candidates:
                candidates.sort(key=lambda x: x["_dt"])
                result = candidates[0]
                del result["_dt"]
                return result

            return None

        except Exception as e:
            print(f"Error fetching next release from FMP: {e}")
            return None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（FMP 3分方式）"""
        return should_refresh_by_fmp_schedule(self.ECONALPHA_ID, last_updated_str)

    def _scrape_investing_data(self) -> Optional[Dict[str, Any]]:
        """Playwrightを使用してInvesting.comからISM非製造業PMIデータをスクレイピング"""
        try:
            from playwright.sync_api import sync_playwright

            print("Scraping ISM Non-Manufacturing PMI from Investing.com...")

            with sync_playwright() as p:
                # Chromiumで試行、失敗したらFirefoxにフォールバック
                browser = None
                for browser_type in ['chromium', 'firefox']:
                    try:
                        if browser_type == 'firefox':
                            browser = p.firefox.launch(headless=True)
                        else:
                            browser = p.chromium.launch(
                                headless=True,
                                args=[
                                    '--no-sandbox',
                                    '--disable-setuid-sandbox',
                                    '--disable-dev-shm-usage',
                                    '--disable-gpu',
                                ]
                            )
                        break
                    except Exception as e:
                        print(f"Failed to launch {browser_type}: {e}")
                        continue

                if not browser:
                    print("Could not launch any browser")
                    return None

                context = browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    locale='ja-JP',
                )

                page = context.new_page()

                # ページにアクセス
                page.goto(INVESTING_URL, wait_until='domcontentloaded', timeout=60000)

                # ページ読み込み待機
                page.wait_for_timeout(5000)

                # Cookie同意バナーを閉じる
                try:
                    cookie_btn = page.locator('button:has-text("同意"), button:has-text("Accept"), [id*="onetrust-accept"]').first
                    if cookie_btn.is_visible(timeout=3000):
                        cookie_btn.click()
                        page.wait_for_timeout(1000)
                except Exception:
                    pass

                # 履歴テーブルが表示されるまで待機
                page.wait_for_timeout(3000)

                # 「更に表示する」ボタンをクリックして過去データを取得
                # 1クリックで6件追加、5回で約30件（約2.5年分）
                for i in range(5):
                    try:
                        show_more_btn = page.locator('text=更に表示する').first
                        if show_more_btn.is_visible(timeout=2000):
                            show_more_btn.click()
                            page.wait_for_timeout(2000)
                        else:
                            break
                    except Exception:
                        break

                # HTMLを取得
                html = page.content()
                browser.close()

                # パース
                return self._parse_html(html)

        except ImportError:
            print("Playwright not installed")
            return None
        except Exception as e:
            print(f"Error scraping ISM Non-Manufacturing PMI: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _parse_html(self, html: str) -> Optional[Dict[str, Any]]:
        """HTMLをパースしてデータを抽出"""
        try:
            soup = BeautifulSoup(html, "html.parser")

            result = {
                "data": [],
                "next_release": None
            }

            # 次回発表日は期間チェック方式のため不要（スクレイピング削減）
            # next_releaseはキャッシュに保存しない

            # 履歴テーブルを取得（ISM非製造業のテーブルID: eventHistoryTable176）
            table = soup.find("table", {"id": "eventHistoryTable176"})
            if not table:
                # 別のセレクタで試す
                table = soup.find("table", {"class": lambda x: x and "history" in x.lower()})

            if not table:
                print("Could not find history table")
                return result

            tbody = table.find("tbody")
            if not tbody:
                print("Could not find tbody")
                return result

            rows = tbody.find_all("tr")
            data = self._extract_rows(rows)

            if data:
                result["data"] = data
                print(f"Scraped {len(data)} ISM Non-Manufacturing PMI records")

            return result

        except Exception as e:
            print(f"Error parsing HTML: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _extract_next_release(self, soup: BeautifulSoup) -> Optional[Dict[str, str]]:
        """次回発表日を抽出"""
        try:
            # パターン1: 特定のクラスや属性で探す
            next_release_selectors = [
                '[data-test="next-event-date"]',
                '.nextEvent',
                '[class*="next-release"]',
                '[class*="nextRelease"]',
            ]

            for selector in next_release_selectors:
                element = soup.select_one(selector)
                if element:
                    date_text = element.get_text(strip=True)
                    parsed = self._parse_next_release_date(date_text)
                    if parsed:
                        return parsed

            # パターン2: テキストで「次回発表」を探す
            for text in soup.find_all(string=re.compile(r'次回発表|次回|Next')):
                parent = text.find_parent()
                if parent:
                    date_text = parent.get_text(strip=True)
                    parsed = self._parse_next_release_date(date_text)
                    if parsed:
                        return parsed

            # パターン3: ページ上部のイベント情報を探す
            event_info = soup.find("div", {"class": lambda x: x and "event" in x.lower()})
            if event_info:
                date_elements = event_info.find_all(string=re.compile(r'\d{4}年\d{1,2}月\d{1,2}日|\d{1,2}/\d{1,2}/\d{4}'))
                for date_el in date_elements:
                    parsed = self._parse_next_release_date(str(date_el))
                    if parsed:
                        return parsed

            return None

        except Exception as e:
            print(f"Error extracting next release: {e}")
            return None

    def _parse_next_release_date(self, text: str) -> Optional[Dict[str, str]]:
        """次回発表日テキストをパース"""
        try:
            # パターン: YYYY年MM月DD日
            match = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', text)
            if match:
                year = int(match.group(1))
                month = int(match.group(2))
                day = int(match.group(3))
                date_str = f"{year:04d}-{month:02d}-{day:02d}"
                return {
                    "date": date_str,
                    "label": f"ISM非製造業景況指数（{year}年{month}月発表）"
                }

            # パターン: MM/DD/YYYY
            match = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})', text)
            if match:
                month = int(match.group(1))
                day = int(match.group(2))
                year = int(match.group(3))
                date_str = f"{year:04d}-{month:02d}-{day:02d}"
                return {
                    "date": date_str,
                    "label": f"ISM非製造業景況指数（{year}年{month}月発表）"
                }

            return None
        except Exception:
            return None

    def _extract_rows(self, rows) -> List[Dict[str, Any]]:
        """テーブル行からデータを抽出

        Investing.comテーブル構造:
        - Cell 0: 日付（例: "2025年12月02日  (11月)"）← 発表日と対象月
        - Cell 1: 時刻（例: "00:00"）
        - Cell 2: 実績値（結果）
        - Cell 3: 予想値
        - Cell 4: 前回値

        取得ロジック（修正値反映のため）:
        - 1行目: 結果列→最新月データ、前回列→前月データ
        - 2行目以降: 前回列→その行の前月データ
        """
        result = []

        for idx, row in enumerate(rows):
            try:
                cells = row.find_all("td")
                if len(cells) < 5:
                    continue

                # 日付と対象月を取得（例: "2025年12月02日  (11月)"）
                date_text = cells[0].get_text(strip=True)

                # 対象月を抽出（括弧内の月）
                target_month = self._extract_target_month(date_text)
                if not target_month:
                    continue

                if idx == 0:
                    # 1行目: 結果列から最新月、前回列から前月を取得

                    # 最新月データ（結果列）
                    value_text = cells[2].get_text(strip=True) if len(cells) > 2 else ""
                    value = self._parse_value(value_text)
                    if value is not None:
                        # 予想値も取得
                        forecast_text = cells[3].get_text(strip=True) if len(cells) > 3 else ""
                        forecast = self._parse_value(forecast_text)

                        # 前回値
                        previous_text = cells[4].get_text(strip=True) if len(cells) > 4 else ""
                        previous = self._parse_value(previous_text)

                        result.append({
                            "date": target_month,
                            "value": value,
                            "forecast": forecast,
                            "previous": previous
                        })

                    # 前月データ（前回列）
                    previous_value_text = cells[4].get_text(strip=True) if len(cells) > 4 else ""
                    previous_value = self._parse_value(previous_value_text)
                    if previous_value is not None:
                        # 前月の日付を計算
                        previous_month = self._get_previous_month(target_month)
                        if previous_month:
                            result.append({
                                "date": previous_month,
                                "value": previous_value,
                                "forecast": None,
                                "previous": None
                            })
                else:
                    # 2行目以降: 前回列からその行の前月データを取得
                    previous_value_text = cells[4].get_text(strip=True) if len(cells) > 4 else ""
                    previous_value = self._parse_value(previous_value_text)
                    if previous_value is None:
                        continue

                    # この行の対象月の前月
                    previous_month = self._get_previous_month(target_month)
                    if previous_month:
                        result.append({
                            "date": previous_month,
                            "value": previous_value,
                            "forecast": None,
                            "previous": None
                        })

            except Exception as e:
                print(f"Error parsing row: {e}")
                continue

        return result

    def _get_previous_month(self, date_str: str) -> Optional[str]:
        """前月の日付を取得

        例: "2025-11-01" → "2025-10-01"
        """
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            # 前月を計算
            if dt.month == 1:
                prev_dt = dt.replace(year=dt.year - 1, month=12)
            else:
                prev_dt = dt.replace(month=dt.month - 1)
            return prev_dt.strftime("%Y-%m-%d")
        except Exception:
            return None

    def _extract_target_month(self, date_text: str) -> Optional[str]:
        """対象月を抽出して月初日付に変換

        例: "2025年12月02日  (11月)" → "2025-11-01"
        """
        try:
            # 発表年を取得
            year_match = re.search(r"(\d{4})年", date_text)
            if not year_match:
                return None
            release_year = int(year_match.group(1))

            # 対象月を括弧内から取得
            month_match = re.search(r"\((\d{1,2})月\)", date_text)
            if not month_match:
                return None
            target_month = int(month_match.group(1))

            # 対象月が12月で発表が1月の場合、年を1つ前にする
            release_month_match = re.search(r"年(\d{1,2})月", date_text)
            if release_month_match:
                release_month = int(release_month_match.group(1))
                if target_month == 12 and release_month == 1:
                    release_year -= 1

            return f"{release_year:04d}-{target_month:02d}-01"
        except Exception:
            return None

    def _parse_value(self, text: str) -> Optional[float]:
        """数値テキストをパース"""
        try:
            if not text or text == "-" or text == "" or text == "nbsp":
                return None
            # カンマや空白を除去
            cleaned = text.replace(",", "").replace(" ", "").replace("\xa0", "").strip()
            if not cleaned:
                return None
            return round(float(cleaned), 1)
        except (ValueError, TypeError):
            return None

    def get_next_release_date(self) -> Optional[Dict[str, str]]:
        """キャッシュから次回発表日を取得"""
        cached_data = redis_client.get(self.CACHE_KEY)
        if cached_data:
            return cached_data.get("next_release")
        return None

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        cache_exists = redis_client.exists(self.CACHE_KEY)
        cached_data = redis_client.get(self.CACHE_KEY) if cache_exists else None

        return {
            "cache_key": self.CACHE_KEY,
            "exists": cache_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID)
        }


# シングルトンインスタンス
ism_non_manufacturing_service = ISMNonManufacturingService()
