"""
スイス求人情報サービス
arbeit.swissから求人件数データを取得

指標:
- Job Vacancies（求人件数）
- スイスの月次求人件数データ

データソース:
- arbeit.swiss (SECO - State Secretariat for Economic Affairs)
- https://www.arbeit.swiss/secoalv/de/home/menue/institutionen-medien/statistiken.html
- 毎月のPDFレポートから「Offene Stellen seit」のデータを抽出

発表スケジュール:
- 毎月（失業率と同じタイミング、FMPカレンダーから取得）

キャッシュ方式: FMP発表日時ベース判定方式
"""
import json
import io
import re
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests

from core.redis_client import redis_client
from services.switzerland.fmp_next_release_utils import (
    get_next_release_by_pattern,
    should_refresh_by_pattern,
)


JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "switzerland" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ch_job_vacancies_cache.json"


class CHJobVacanciesService:
    """スイス求人情報サービス"""

    DATA_CACHE_KEY = "switzerland:ch_job_vacancies:data"
    ECONALPHA_ID = "ch_job_vacancies"
    FMP_COUNTRY = "CH"
    # 失業率と同じタイミングで発表される
    FMP_EVENT_PATTERN = "Unemployment Rate"

    # arbeit.swiss レポートページ
    BASE_URL = "https://www.arbeit.swiss/secoalv/de/home/menue/institutionen-medien/statistiken.html"

    # ドイツ語の月名マッピング
    GERMAN_MONTHS = {
        'Januar': 1, 'Februar': 2, 'März': 3, 'April': 4,
        'Mai': 5, 'Juni': 6, 'Juli': 7, 'August': 8,
        'September': 9, 'Oktober': 10, 'November': 11, 'Dezember': 12
    }

    def __init__(self):
        pass

    def get_job_vacancies_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """スイス求人情報データを取得"""
        # 次回発表日を取得（失業率と同じタイミング）
        next_release = get_next_release_by_pattern(self.FMP_EVENT_PATTERN, country=self.FMP_COUNTRY)

        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # PDFからデータ取得
        pdf_result = self._load_from_pdf()
        if pdf_result:
            # 最新値を取得
            latest = pdf_result[-1] if pdf_result else None

            from services.usa.fmp_next_release_utils import guarded_last_updated
            now_str = datetime.now(JST).isoformat()
            last_updated = guarded_last_updated(
                self.DATA_CACHE_KEY, latest.get("date") if latest else None, now_str
            )
            cache_payload = {
                "data": pdf_result,
                "latest": latest,
                "metadata": {
                    "source": "arbeit.swiss",
                    "indicator": "Job Vacancies",
                    "description": "スイス求人件数",
                    "unit": "件（千）",
                },
                "last_updated": last_updated,
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": pdf_result,
                "latest": latest,
                "metadata": cache_payload["metadata"],
                "next_release": next_release,
                "cached": False,
                "source": "pdf",
                "last_updated": last_updated,
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "metadata": file_cache.get("metadata", {}),
                "next_release": next_release,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "data": [],
            "latest": None,
            "metadata": {},
            "next_release": next_release,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _load_from_pdf(self) -> List[Dict[str, Any]]:
        """arbeit.swiss 最新PDFの「Offene Stellen seit 2004」テーブルから時系列データを取得"""
        try:
            import pdfplumber

            print(f"[CHJobVacancies] Fetching data from arbeit.swiss PDF (seit 2004 table)")

            # 最新のPDF URLを取得
            pdf_url = self._get_latest_pdf_url()
            if not pdf_url:
                print("[CHJobVacancies] Could not find PDF URL")
                return []

            print(f"[CHJobVacancies] PDF URL: {pdf_url}")

            resp = requests.get(pdf_url, timeout=60)
            resp.raise_for_status()

            result = []
            with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
                # 「Offene Stellen seit 2004」テーブルを含むページを探す
                for page in pdf.pages:
                    text = page.extract_text()
                    if not text:
                        continue

                    # 「Offene Stellen seit」テーブルを探す（部分一致）
                    # テキスト正規化（スペース除去）で検索
                    # 注意: テーブル番号や開始年は変わる可能性があるため、"OffeneStellenseit"で部分一致
                    normalized = text.replace(" ", "").replace("\n", "")
                    if "OffeneStellenseit" in normalized:
                        # テキストからデータを抽出（テーブル形式）
                        parsed = self._parse_seit_2004_table(text)
                        if parsed:
                            result.extend(parsed)
                            break

            # 日付でソートして重複を除去
            result.sort(key=lambda x: x["date"])
            seen_dates = set()
            unique_result = []
            for item in result:
                if item["date"] not in seen_dates:
                    seen_dates.add(item["date"])
                    unique_result.append(item)

            print(f"[CHJobVacancies] Loaded {len(unique_result)} records from PDF")
            if unique_result:
                print(f"[CHJobVacancies] Date range: {unique_result[0]['date']} to {unique_result[-1]['date']}")
                print(f"[CHJobVacancies] Latest: value={unique_result[-1].get('value')}")

            return unique_result

        except ImportError:
            print("[CHJobVacancies] pdfplumber not installed")
            return []
        except Exception as e:
            print(f"[CHJobVacancies] Error loading from PDF: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _parse_seit_2004_table(self, text: str) -> List[Dict[str, Any]]:
        """「Offene Stellen seit 2004」テーブルからデータを抽出"""
        result = []

        # 月の順序（Jan, Feb, Mrz, Apr, Mai, Jun, Jul, Aug, Sep, Okt, Nov, Dez）
        # テーブル形式: 年 Jan Feb Mrz Apr Mai Jun Jul Aug Sep Okt Nov Dez Ø
        lines = text.split('\n')

        # 「Offene Stellen seit」テーブルのデータ部分を見つける
        in_table = False
        for line in lines:
            # テーブルヘッダーを見つけたらデータ開始（部分一致）
            # 注意: テーブル番号や開始年は変わる可能性があるため、"OffeneStellenseit"で部分一致
            if "OffeneStellenseit" in line.replace(" ", ""):
                in_table = True
                continue

            if not in_table:
                continue

            # 年で始まる行を探す（2004, 2005, ...）
            year_match = re.match(r'^(20\d{2})\s+', line)
            if year_match:
                year = int(year_match.group(1))

                # 年以降のデータ部分を取得
                data_part = line[year_match.end():]

                # スペースで分割して各値を抽出
                parts = data_part.split()

                monthly_values = []
                for part in parts:
                    # 数字以外の文字を除去（千区切りの'や特殊文字を削除）
                    clean_num = re.sub(r'[^\d]', '', part)
                    if clean_num:
                        try:
                            value = int(clean_num)
                            # 妥当な範囲（1,000〜100,000 - 単一月のデータ）
                            if 1000 <= value <= 100000:
                                monthly_values.append(value)
                        except ValueError:
                            continue

                # 12個の月次データがあれば追加
                if len(monthly_values) >= 12:
                    for month_idx, value in enumerate(monthly_values[:12]):
                        month = month_idx + 1  # 1-12
                        date_str = f"{year}-{month:02d}-01"
                        result.append({"date": date_str, "value": value})

            # "Quelle:" が来たらテーブル終了
            if "Quelle:" in line:
                break

        return result

    def _get_all_pdf_urls(self) -> List[str]:
        """arbeit.swissからPDF URLを取得（メインページとアーカイブページ両方を検索）"""
        try:
            pdf_urls = []
            seen = set()

            # 検索対象ページ（メインページを先に検索 - 最新PDFがある可能性が高い）
            pages_to_search = [
                "https://www.arbeit.swiss/secoalv/de/home/menue/institutionen-medien/statistiken.html",
                "https://www.arbeit.swiss/secoalv/de/home/menue/institutionen-medien/statistiken/archiv.html",
            ]

            for page_url in pages_to_search:
                try:
                    resp = requests.get(page_url, timeout=30)
                    resp.raise_for_status()

                    # PDF URLを抽出（"die_lage_auf_dem_arbeitsmarkt" を含むPDF）
                    pattern = r'href="([^"]*die_lage_auf_dem_arbeitsmarkt[^"]*\.pdf[^"]*)"'
                    matches = re.findall(pattern, resp.text, re.IGNORECASE)

                    for match in matches:
                        if match.startswith('/'):
                            url = f"https://www.arbeit.swiss{match}"
                        else:
                            url = match
                        if url not in seen:
                            seen.add(url)
                            pdf_urls.append(url)

                except Exception as e:
                    print(f"[CHJobVacancies] Error fetching {page_url}: {e}")
                    continue

            # URLから年月を抽出してソート（最新順）
            def extract_year_month(url: str) -> tuple:
                # パターン: 2025-12 or 2025_12 or 202512
                m = re.search(r'(\d{4})[_-]?(\d{2})', url)
                if m:
                    return (int(m.group(1)), int(m.group(2)))
                return (0, 0)

            pdf_urls.sort(key=extract_year_month, reverse=True)

            print(f"[CHJobVacancies] Found {len(pdf_urls)} PDFs")
            if pdf_urls:
                print(f"[CHJobVacancies] Latest PDF: {pdf_urls[0]}")

            return pdf_urls

        except Exception as e:
            print(f"[CHJobVacancies] Error getting PDF URLs: {e}")
            return []

    def _get_latest_pdf_url(self) -> Optional[str]:
        """arbeit.swissから最新のPDF URLを取得"""
        pdf_urls = self._get_all_pdf_urls()
        return pdf_urls[0] if pdf_urls else None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（FMP発表日ベース）"""
        return should_refresh_by_pattern(
            self.FMP_EVENT_PATTERN,
            last_updated_str,
            country=self.FMP_COUNTRY
        )

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[CHJobVacancies] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CHJobVacancies] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "CH Job Vacancies",
            "source": "arbeit.swiss",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_by_pattern(self.FMP_EVENT_PATTERN, country=self.FMP_COUNTRY),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ch_job_vacancies_service = CHJobVacanciesService()
