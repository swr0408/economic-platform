"""
スイスPMIサービス
procure.ch Purchasing Managers' Index（製造業・サービス業）

指標:
- 製造業PMI (Manufacturing PMI): FMP + DB蓄積方式
- サービス業PMI (Services PMI): Webスクレイピング + DB蓄積方式

データソース:
- 製造業: FMP API / DB (economic_calendar_events)
- サービス業: procure.ch スクレイピング

発表スケジュール:
- 月次（毎月第一営業日）

キャッシュ方式: FMP発表日時ベース判定 + DB蓄積
"""
import json
import re
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from core.database import SessionLocal
from core.redis_client import redis_client
from services.calendar.fmp_service import fmp_service
from sqlalchemy import text


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
UTC = ZoneInfo("UTC")
ZURICH = ZoneInfo("Europe/Zurich")

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "switzerland" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ch_pmi_cache.json"

# CSVデータディレクトリ
CSV_DIR = Path(__file__).parent.parent.parent / "data" / "csv_import"
MANUFACTURING_CSV = CSV_DIR / "procure.chスイス製造業購買担当者景気指数.csv"
SERVICES_CSV = CSV_DIR / "スイス サービスPMI.csv"


class ChPmiService:
    """
    スイスPMIサービス

    製造業PMI: FMP + DB蓄積方式
    サービス業PMI: スクレイピング + DB蓄積方式
    """

    DATA_CACHE_KEY = "switzerland:ch_pmi:data"

    # FMPパターン（製造業PMI）
    FMP_PATTERN = "procure.ch Manufacturing PMI"
    COUNTRY = "CH"

    # スクレイピングURL（サービス業PMI）
    PROCURE_CH_URL = "https://www.procure.ch/magazin/themen/marktdaten"

    def __init__(self):
        pass

    def get_pmi_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        スイスPMIデータを取得

        Returns:
            {
                "manufacturing_data": [...],
                "services_data": [...],
                "latest_manufacturing": {...},
                "latest_services": {...},
                "metadata": {...},
                "next_release": {...},
                "cached": bool,
                "source": str
            }
        """
        # 次回発表日を取得
        next_release = self._get_next_release()

        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str, next_release):
                    return {
                        "manufacturing_data": cached_data.get("manufacturing_data", []),
                        "services_data": cached_data.get("services_data", []),
                        "latest_manufacturing": cached_data.get("latest_manufacturing"),
                        "latest_services": cached_data.get("latest_services"),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # データを取得
        manufacturing_data = self._load_manufacturing_pmi()
        services_data = self._load_services_pmi()

        # 最新値を特定
        latest_manufacturing = manufacturing_data[-1] if manufacturing_data else None
        latest_services = services_data[-1] if services_data else None

        # キャッシュ保存
        cache_payload = {
            "manufacturing_data": manufacturing_data,
            "services_data": services_data,
            "latest_manufacturing": latest_manufacturing,
            "latest_services": latest_services,
            "metadata": {
                "source": "procure.ch",
                "indicator": "Purchasing Managers' Index",
                "description": "スイスPMI（購買担当者景気指数）",
                "unit": "index",
                "frequency": "monthly",
                "threshold": 50,  # 50を超えると拡大、下回ると縮小
            },
            "last_updated": datetime.now(JST).isoformat(),
        }
        redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
        self._save_file_cache(cache_payload)

        return {
            "manufacturing_data": manufacturing_data,
            "services_data": services_data,
            "latest_manufacturing": latest_manufacturing,
            "latest_services": latest_services,
            "metadata": cache_payload["metadata"],
            "next_release": next_release,
            "cached": False,
            "source": "csv+fmp+db",
            "last_updated": datetime.now(JST).isoformat(),
        }

    def _load_from_csv(self, csv_path: Path) -> List[Dict[str, Any]]:
        """
        CSVファイルからPMIデータを読み込む

        CSV形式: 公表日,時刻,結果,予想,前回
        例: 2026/01,,48.8,,
        """
        result = []

        try:
            if not csv_path.exists():
                print(f"[CHPmi] CSV file not found: {csv_path}")
                return result

            import csv
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    date_str = row.get("公表日", "").strip()
                    value_str = row.get("結果", "").strip()
                    forecast_str = row.get("予想", "").strip()
                    previous_str = row.get("前回", "").strip()

                    if not date_str or not value_str:
                        continue

                    # 日付を変換 (2026/01 -> 2026-01-01)
                    try:
                        parts = date_str.split("/")
                        if len(parts) == 2:
                            year, month = parts
                            date_formatted = f"{year}-{int(month):02d}-01"
                        else:
                            continue
                    except ValueError:
                        continue

                    try:
                        value = float(value_str)
                    except ValueError:
                        continue

                    forecast = float(forecast_str) if forecast_str else None
                    previous = float(previous_str) if previous_str else None

                    result.append({
                        "date": date_formatted,
                        "value": value,
                        "forecast": forecast,
                        "previous": previous,
                    })

            print(f"[CHPmi] Loaded {len(result)} records from CSV: {csv_path.name}")

        except Exception as e:
            print(f"[CHPmi] Error loading from CSV: {e}")
            import traceback
            traceback.print_exc()

        return result

    def _load_manufacturing_pmi(self) -> List[Dict[str, Any]]:
        """
        製造業PMIをCSV + FMP + DBから取得

        優先順位: FMP最新 > DB履歴 > CSV履歴
        """
        result = []
        month_map = {
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
            'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
        }

        try:
            # 1. CSVから履歴データを取得
            csv_data = self._load_from_csv(MANUFACTURING_CSV)
            for item in csv_data:
                result.append(item)

            # 2. DBから履歴データを取得
            db_data = self._load_from_db(self.FMP_PATTERN)
            for item in db_data:
                result.append(item)

            # 3. FMPから最新データを取得
            fmp_data = self._fetch_from_fmp(self.FMP_PATTERN, month_map)
            for item in fmp_data:
                result.append(item)

            # 日付でマージ（後から追加されたものを優先）
            merged = {}
            for item in result:
                merged[item["date"]] = item

            result = sorted(merged.values(), key=lambda x: x["date"])
            print(f"[CHPmi] Loaded {len(result)} manufacturing PMI records (merged)")

        except Exception as e:
            print(f"[CHPmi] Error loading manufacturing PMI: {e}")
            import traceback
            traceback.print_exc()

        return result

    def _load_services_pmi(self) -> List[Dict[str, Any]]:
        """
        サービス業PMIをCSV + スクレイピング + DBから取得

        優先順位: 手動CSV（検証済み）> スクレイピング最新 > DB履歴

        注意: procure.chのサービス業PMIは記事/PDFが月表記に揺れがあり
        （製造業の月を見出しに付けるためサービス値の月ラベルがズレることがある）、
        スクレイピングは脆弱。手動CSVを正本（最優先）とし、スクレイピング/DBは
        CSV未収録の月のみを補完する（将来の自動延伸用）。
        """
        result = []

        try:
            # 1. DBから履歴データ（最下層）
            db_data = self._load_services_from_db()
            for item in db_data:
                result.append(item)

            # 2. スクレイピングから最新データを取得し、DBに保存（CSV未収録月の補完用）
            scraped_data = self._scrape_services_pmi()
            for item in scraped_data:
                result.append(item)
                # DBに保存（DB積み上げ方式）
                self._save_services_to_db(item)

            # 3. 手動CSV（検証済み・正本）を最後に重ねて最優先にする
            csv_data = self._load_from_csv(SERVICES_CSV)
            for item in csv_data:
                result.append(item)

            # 日付でマージ（後から追加されたものを優先 = CSV > scrape > DB）
            merged = {}
            for item in result:
                merged[item["date"]] = item

            result = sorted(merged.values(), key=lambda x: x["date"])
            print(f"[CHPmi] Loaded {len(result)} services PMI records (merged)")

        except Exception as e:
            print(f"[CHPmi] Error loading services PMI: {e}")
            import traceback
            traceback.print_exc()

        return result

    def _load_from_db(self, pattern: str) -> List[Dict[str, Any]]:
        """DBから履歴データを取得（製造業PMI用）"""
        result = []
        month_map = {
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
            'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
        }

        try:
            with SessionLocal() as session:
                query = text("""
                    SELECT
                        datetime_utc,
                        event,
                        event_period,
                        actual,
                        estimate,
                        previous
                    FROM economic_calendar_events
                    WHERE country = :country
                      AND LOWER(event) LIKE LOWER(:pattern)
                      AND actual IS NOT NULL
                    ORDER BY datetime_utc DESC
                    LIMIT 500
                """)

                rows = session.execute(query, {
                    "country": self.COUNTRY,
                    "pattern": f"%{pattern}%"
                }).fetchall()

                for row in rows:
                    dt_utc, event, period, actual, estimate, previous = row

                    if not dt_utc:
                        continue

                    # イベント名から対象月を抽出
                    match = re.search(r'\((\w{3})\)', event) if event else None
                    if match:
                        month_abbr = match.group(1).lower()
                        if month_abbr in month_map:
                            target_month = month_map[month_abbr]
                            target_year = dt_utc.year
                            if target_month > dt_utc.month:
                                target_year -= 1
                            date_str = f"{target_year}-{target_month:02d}-01"
                        else:
                            date_str = dt_utc.strftime("%Y-%m-01")
                    else:
                        date_str = dt_utc.strftime("%Y-%m-01")

                    result.append({
                        "date": date_str,
                        "value": float(actual) if actual else None,
                        "forecast": float(estimate) if estimate else None,
                        "previous": float(previous) if previous else None,
                        "period": period,
                    })

        except Exception as e:
            print(f"[CHPmi] Error loading from DB: {e}")

        return result

    def _load_services_from_db(self) -> List[Dict[str, Any]]:
        """DBからサービス業PMI履歴データを取得"""
        result = []

        try:
            with SessionLocal() as session:
                # ch_pmi_servicesテーブルから取得（存在する場合）
                query = text("""
                    SELECT
                        datetime_utc,
                        event,
                        event_period,
                        actual,
                        estimate,
                        previous
                    FROM economic_calendar_events
                    WHERE country = :country
                      AND (
                          LOWER(event) LIKE LOWER('%Services PMI%')
                          OR LOWER(event) LIKE LOWER('%Dienstleistungs-PMI%')
                          OR LOWER(event) LIKE LOWER('%procure.ch Services PMI%')
                      )
                      AND actual IS NOT NULL
                    ORDER BY datetime_utc DESC
                    LIMIT 500
                """)

                rows = session.execute(query, {"country": self.COUNTRY}).fetchall()

                month_map = {
                    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
                    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
                }

                for row in rows:
                    dt_utc, event, period, actual, estimate, previous = row

                    if not dt_utc:
                        continue

                    match = re.search(r'\((\w{3})\)', event) if event else None
                    if match:
                        month_abbr = match.group(1).lower()
                        if month_abbr in month_map:
                            target_month = month_map[month_abbr]
                            target_year = dt_utc.year
                            if target_month > dt_utc.month:
                                target_year -= 1
                            date_str = f"{target_year}-{target_month:02d}-01"
                        else:
                            date_str = dt_utc.strftime("%Y-%m-01")
                    else:
                        date_str = dt_utc.strftime("%Y-%m-01")

                    result.append({
                        "date": date_str,
                        "value": float(actual) if actual else None,
                        "forecast": float(estimate) if estimate else None,
                        "previous": float(previous) if previous else None,
                        "period": period,
                    })

        except Exception as e:
            print(f"[CHPmi] Error loading services from DB: {e}")

        return result

    def _fetch_from_fmp(self, pattern: str, month_map: dict) -> List[Dict[str, Any]]:
        """FMPから最新データを取得"""
        result = []

        try:
            today = date.today()
            from_date = today - timedelta(days=90)
            to_date = today + timedelta(days=60)

            events = fmp_service.fetch_calendar(from_date, to_date, country=self.COUNTRY)

            for event in events:
                if event.get("country") != self.COUNTRY:
                    continue

                event_name = event.get("event", "")
                if pattern.lower() not in event_name.lower():
                    continue

                dt_utc, _ = fmp_service.parse_datetime(event.get("date", ""))
                if not dt_utc:
                    continue

                actual = event.get("actual")
                if actual is None:
                    continue

                # イベント名から対象月を抽出
                match = re.search(r'\((\w{3})\)', event_name)
                if match:
                    month_abbr = match.group(1).lower()
                    if month_abbr in month_map:
                        target_month = month_map[month_abbr]
                        target_year = dt_utc.year
                        if target_month > dt_utc.month:
                            target_year -= 1
                        date_str = f"{target_year}-{target_month:02d}-01"
                    else:
                        date_str = dt_utc.strftime("%Y-%m-01")
                else:
                    date_str = dt_utc.strftime("%Y-%m-01")

                result.append({
                    "date": date_str,
                    "value": float(actual),
                    "forecast": float(event.get("estimate")) if event.get("estimate") else None,
                    "previous": float(event.get("previous")) if event.get("previous") else None,
                    "period": fmp_service.extract_period_info(event_name),
                })

                # DBにも保存
                self._save_to_db(event)

        except Exception as e:
            print(f"[CHPmi] Error fetching from FMP: {e}")

        return result

    def _scrape_services_pmi(self) -> List[Dict[str, Any]]:
        """
        procure.chからサービス業PMIをスクレイピング

        ページ構造:
        - リストページから個別記事へのリンクを取得
        - 個別記事ページ内に「Dienstleistungs-PMI」の値が含まれる
        - 形式例: "Der Dienstleistungs-PMI notiert bei 48,2 Punkten"
                  "Dienstleistungs-PMI: 52.3"
        """
        result = []

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            resp = requests.get(self.PROCURE_CH_URL, headers=headers, timeout=30)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")

            # 記事リンクを収集（絶対URLに正規化してから重複排除）
            # 注意: 相対hrefのまま重複判定し絶対URLで格納すると、同一記事が
            #       二重登録され article_links[:N] の実効カバー月数が半減する罠
            article_links = []
            for link in soup.find_all("a", href=re.compile(r"/magazin/.*pmi", re.IGNORECASE)):
                href = link.get("href", "")
                if not href:
                    continue
                if href.startswith("/"):
                    href = f"https://www.procure.ch{href}"
                if href not in article_links:
                    article_links.append(href)

            print(f"[CHPmi] Found {len(article_links)} PMI article links")

            # 直近12記事を処理（CSV未収録月の補完が目的）
            for article_url in article_links[:12]:
                try:
                    article_resp = requests.get(article_url, headers=headers, timeout=30)
                    article_resp.raise_for_status()
                    article_soup = BeautifulSoup(article_resp.text, "html.parser")

                    # 記事本文を取得
                    # 注意: ページにより<article>/<main>が本文を含まずナビのみの
                    #       テンプレートがあり取りこぼす→段落<p>結合を本文とし、
                    #       無ければ全文にフォールバック。空白も正規化しておく
                    paragraphs = [p.get_text(" ", strip=True) for p in article_soup.find_all("p")]
                    text_content = " ".join(paragraphs) if paragraphs else article_soup.get_text(" ", strip=True)
                    text_content = re.sub(r"\s+", " ", text_content)

                    # サービス業PMIへの言及があるか
                    if not re.search(r"Dienstleistungs-?PMI|Dienstleistungssektor|Services\s+PMI", text_content, re.IGNORECASE):
                        continue

                    # サービス業PMI固有の値を抽出
                    # 表現ゆれに対応: "bei 57,2" / "mit 54,8 Punkten" / "auf 53,8 Punkte" /
                    #                "Dienstleistungssektor ... bei XX,X"
                    # [^.]{0,80}? で同一文に限定し、製造業の数値や変化量を誤取得しない。
                    # \d{2}[.,]\d で2桁始まりに限定し "2,4 Punkte höher" 等の変化量を除外。
                    value = None
                    patterns = [
                        r'Dienstleistungs-?PMI[^.]{0,80}?(?:bei|mit|auf)\s+(\d{2}[.,]\d)',
                        r'Dienstleistungssektor[^.]{0,80}?(?:bei|mit|auf)\s+(\d{2}[.,]\d)',
                        r'Dienstleistungs-?PMI[:\s]+(\d{2}[.,]\d)',
                        r'Services\s+PMI[^.]{0,80}?(?:bei|mit|auf|at)\s+(\d{2}[.,]\d)',
                    ]

                    for pattern in patterns:
                        match = re.search(pattern, text_content, re.IGNORECASE)
                        if match:
                            value_str = match.group(1).replace(",", ".")
                            value = float(value_str)
                            break

                    if value is None:
                        continue

                    # PMI値の妥当性チェック（通常20-75の範囲）
                    if value < 20 or value > 75:
                        print(f"[CHPmi] Skipping invalid services PMI value: {value}")
                        continue

                    # 日付を抽出
                    date_str = self._extract_date_from_article(article_soup, text_content)

                    if date_str and value:
                        # 重複チェック
                        if not any(r["date"] == date_str for r in result):
                            result.append({
                                "date": date_str,
                                "value": value,
                                "forecast": None,
                                "previous": None,
                            })
                            print(f"[CHPmi] Scraped services PMI: {date_str} = {value}")

                except Exception as e:
                    print(f"[CHPmi] Error scraping article {article_url}: {e}")
                    continue

            print(f"[CHPmi] Scraped {len(result)} services PMI records total")

        except Exception as e:
            print(f"[CHPmi] Error scraping services PMI: {e}")
            import traceback
            traceback.print_exc()

        return result

    def _extract_date_from_article(self, article, text_content: str) -> Optional[str]:
        """
        記事から対象月を抽出

        PMI記事は「PMI Januar 2026」のようにタイトルに対象月が含まれる
        公開日ではなく対象月を優先的に抽出する
        """
        month_patterns = {
            'januar': 1, 'februar': 2, 'märz': 3, 'april': 4, 'mai': 5, 'juni': 6,
            'juli': 7, 'august': 8, 'september': 9, 'oktober': 10, 'november': 11, 'dezember': 12,
            'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
            'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12,
        }

        # 1. タイトルから「PMI {月名} {年}」パターンを優先的に抽出
        title_elem = article.find("h1") or article.find("title")
        if title_elem:
            title_text = title_elem.get_text().lower()
            for month_name, month_num in month_patterns.items():
                # "pmi januar 2026" のようなパターン
                pattern = rf'pmi\s+{month_name}\s+(20\d{{2}})'
                match = re.search(pattern, title_text, re.IGNORECASE)
                if match:
                    year = int(match.group(1))
                    return f"{year}-{month_num:02d}-01"

        # 2. テキスト全体から「PMI {月名} {年}」パターンを探す
        text_lower = text_content.lower()
        for month_name, month_num in month_patterns.items():
            pattern = rf'pmi\s+{month_name}\s+(20\d{{2}})'
            match = re.search(pattern, text_lower, re.IGNORECASE)
            if match:
                year = int(match.group(1))
                return f"{year}-{month_num:02d}-01"

        # 3. 月名と年の組み合わせを探す（フォールバック）
        for month_name, month_num in month_patterns.items():
            if month_name in text_lower:
                year_match = re.search(r'20\d{2}', text_content)
                if year_match:
                    year = int(year_match.group())
                    return f"{year}-{month_num:02d}-01"

        # 4. time要素を使用（最終フォールバック）
        time_elem = article.find("time")
        if time_elem:
            datetime_attr = time_elem.get("datetime")
            if datetime_attr:
                try:
                    dt = datetime.fromisoformat(datetime_attr.replace("Z", "+00:00"))
                    # 公開日の前月を対象月とみなす（PMIは翌月初に発表される）
                    if dt.month == 1:
                        return f"{dt.year - 1}-12-01"
                    else:
                        return f"{dt.year}-{dt.month - 1:02d}-01"
                except ValueError:
                    pass

        return None

    def _save_to_db(self, event: dict) -> None:
        """FMPイベントをDBに保存"""
        try:
            processed = fmp_service.process_event(event)

            with SessionLocal() as session:
                query = text("""
                    INSERT INTO economic_calendar_events (
                        provider, event_key, country, currency, event, event_period,
                        datetime_raw, datetime_utc, has_time, impact,
                        previous, estimate, actual, change, change_pct, unit, raw_json
                    ) VALUES (
                        :provider, :event_key, :country, :currency, :event, :event_period,
                        :datetime_raw, :datetime_utc, :has_time, :impact,
                        :previous, :estimate, :actual, :change, :change_pct, :unit, :raw_json
                    )
                    ON CONFLICT (provider, event_key) DO UPDATE SET
                        previous = EXCLUDED.previous,
                        estimate = EXCLUDED.estimate,
                        actual = EXCLUDED.actual,
                        change = EXCLUDED.change,
                        change_pct = EXCLUDED.change_pct,
                        updated_at = NOW()
                """)

                session.execute(query, {
                    "provider": processed["provider"],
                    "event_key": processed["event_key"],
                    "country": processed["country"],
                    "currency": processed["currency"],
                    "event": processed["event"],
                    "event_period": processed["event_period"],
                    "datetime_raw": processed["datetime_raw"],
                    "datetime_utc": processed["datetime_utc"],
                    "has_time": processed["has_time"],
                    "impact": processed["impact"],
                    "previous": processed["previous"],
                    "estimate": processed["estimate"],
                    "actual": processed["actual"],
                    "change": processed["change"],
                    "change_pct": processed["change_pct"],
                    "unit": processed["unit"],
                    "raw_json": json.dumps(processed["raw_json"]),
                })
                session.commit()

        except Exception as e:
            print(f"[CHPmi] Error saving to DB: {e}")

    def _save_services_to_db(self, item: dict) -> None:
        """サービス業PMIをDBに保存"""
        try:
            with SessionLocal() as session:
                # 対象月から月名を取得
                date_obj = datetime.strptime(item["date"], "%Y-%m-%d")
                month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                               'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
                month_abbr = month_names[date_obj.month - 1]

                event_name = f"procure.ch Services PMI ({month_abbr})"
                event_key = f"procure_services_pmi_{item['date']}"

                query = text("""
                    INSERT INTO economic_calendar_events (
                        provider, event_key, country, currency, event, event_period,
                        datetime_raw, datetime_utc, has_time, impact,
                        previous, estimate, actual, unit, raw_json
                    ) VALUES (
                        :provider, :event_key, :country, :currency, :event, :event_period,
                        :datetime_raw, :datetime_utc, :has_time, :impact,
                        :previous, :estimate, :actual, :unit, :raw_json
                    )
                    ON CONFLICT (provider, event_key) DO UPDATE SET
                        actual = EXCLUDED.actual,
                        updated_at = NOW()
                """)

                session.execute(query, {
                    "provider": "procure.ch",
                    "event_key": event_key,
                    "country": self.COUNTRY,
                    "currency": "CHF",
                    "event": event_name,
                    "event_period": f"{date_obj.year}-{date_obj.month:02d}",
                    "datetime_raw": item["date"],
                    "datetime_utc": date_obj,
                    "has_time": False,
                    "impact": "medium",
                    "previous": item.get("previous"),
                    "estimate": item.get("forecast"),
                    "actual": item["value"],
                    "unit": "index",
                    "raw_json": json.dumps({
                        "date": item["date"],
                        "value": item["value"],
                        "source": "procure.ch scrape",
                    }),
                })
                session.commit()

        except Exception as e:
            print(f"[CHPmi] Error saving services PMI to DB: {e}")

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """次回発表日を取得"""
        try:
            from services.switzerland.fmp_next_release_utils import get_next_release_by_pattern
            return get_next_release_by_pattern(self.FMP_PATTERN, country=self.COUNTRY)
        except Exception as e:
            print(f"[CHPmi] Error getting next release: {e}")
            return None

    def _should_refresh(self, last_updated_str: str, next_release: Optional[Dict]) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)

            # 当日の6時以降で前日以前なら更新
            today_6am = datetime.combine(now.date(), datetime.min.time(), tzinfo=JST).replace(hour=6)
            if now >= today_6am and last_updated < today_6am:
                return True

            # 3日以上経過していたら更新
            if (now - last_updated).days >= 3:
                return True

            return False

        except Exception as e:
            print(f"[CHPmi] Error checking refresh: {e}")
            return True

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[CHPmi] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CHPmi] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None
        next_release = self._get_next_release()

        return {
            "indicator": "Swiss PMI",
            "source": "procure.ch",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "manufacturing_count": len(cached_data.get("manufacturing_data", [])) if cached_data else 0,
            "services_count": len(cached_data.get("services_data", [])) if cached_data else 0,
            "latest_manufacturing": cached_data.get("latest_manufacturing") if cached_data else None,
            "latest_services": cached_data.get("latest_services") if cached_data else None,
            "next_release": next_release,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ch_pmi_service = ChPmiService()
