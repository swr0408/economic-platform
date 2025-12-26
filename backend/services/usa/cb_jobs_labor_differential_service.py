"""
CB雇用機会業況判断（Jobs Plentiful / Hard to Get）サービス

Conference Boardの公式ページから雇用機会業況判断データを取得。
ローカルCSVをキャッシュとして使用し、毎月最終火曜日の発表後のみスクレイピング実行。

指標:
- Jobs Plentiful: 仕事が「豊富」と回答した割合 (%)
- Jobs Hard to Get: 仕事が「見つけにくい」と回答した割合 (%)
- Differential: 差分（Plentiful - Hard）

データソース:
- 公式: https://www.conference-board.org/topics/consumer-confidence/
- フォールバック: PR Newswire検索
- ローカルCSV: CB雇用機会業況判断.csv

発表スケジュール:
- 毎月最終火曜日 10:00 ET

キャッシュ方式: 発表日時ベース判定方式 + CSVファイルバックアップ
"""
import re
import json
import shutil
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests
from bs4 import BeautifulSoup
import pandas as pd

from core.redis_client import redis_client


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
ET = ZoneInfo("America/New_York")

# Conference Board 公式ページ（固定URL）
CB_OFFICIAL_URL = "https://www.conference-board.org/topics/consumer-confidence/"

# PR Newswire 検索URL（フォールバック用）
PR_NEWSWIRE_SEARCH_URL = "https://www.prnewswire.com/search/news/?keyword=Conference+Board+Consumer+Confidence&pagesize=1&sortby=Date"

# CSVファイルパス（データディレクトリに格納）
CSV_FILE_PATH = Path(__file__).parent.parent.parent / "data" / "usa" / "consumer" / "cb_jobs_labor_differential.csv"

# キャッシュディレクトリ（雇用カテゴリ）
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "cb_jobs_labor_differential_cache.json"
SCHEDULE_CACHE_FILE = CACHE_DIR / "cb_jobs_labor_schedule_cache.json"

# 正規表現パターン
RE_SOURCE = re.compile(r"Source:\s*([A-Za-z]+)\s+(\d{4})\s+Consumer Confidence Survey", re.I)
RE_PLENTIFUL = re.compile(r'(\d+(?:\.\d+)?)\s*%.*?jobs\s+were\s+["""]plentiful', re.I | re.DOTALL)
RE_PLENTIFUL_ALT = re.compile(r'jobs\s+were\s+["""]plentiful["""].*?(\d+(?:\.\d+)?)\s*%', re.I | re.DOTALL)
RE_HARD = re.compile(r'(\d+(?:\.\d+)?)\s*%.*?jobs\s+were\s+["""]hard\s+to\s+get', re.I | re.DOTALL)
RE_HARD_ALT = re.compile(r'jobs\s+were\s+["""]hard\s+to\s+get["""].*?(\d+(?:\.\d+)?)\s*%', re.I | re.DOTALL)
RE_NEXT_RELEASE = re.compile(r'next\s+release\s+is\s+(\w+),\s+(\w+)\s+(\d+)', re.I)

# 月名マッピング
MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12
}

# Investing.com JSONエンドポイント（次回発表日取得用）
INVESTING_CB_URL = "https://sbcharts.investing.com/events_charts/us/48.json"


class CBJobsLaborDifferentialService:
    """CB雇用機会業況判断サービス"""

    DATA_CACHE_KEY = "cb:jobs_labor_differential:data"
    SCHEDULE_CACHE_KEY = "cb:jobs_labor_differential:schedule"

    # 発表時刻設定（ET）- 10:00 ET
    RELEASE_HOUR_ET = 10
    RELEASE_MINUTE_ET = 0

    def __init__(self):
        pass

    def get_jobs_labor_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        CB雇用機会業況判断データを取得

        Args:
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "data": [{"date": "YYYY-MM", "plentiful": float, "hard": float, "differential": float}, ...],
                "latest": {...},
                "next_release": {"date": "YYYY-MM-DD", "label": str} | null,
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    next_release = self._get_next_release()
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # ファイルキャッシュチェック
        if not force_refresh:
            file_cache = self._load_file_cache()
            if file_cache:
                last_updated_str = file_cache.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    data = file_cache.get("data", [])
                    next_release = self._get_next_release()

                    # Redisにも保存
                    redis_client.set(self.DATA_CACHE_KEY, file_cache, expire=0)

                    return {
                        "data": data,
                        "latest": file_cache.get("latest"),
                        "next_release": next_release,
                        "cached": True,
                        "source": "file",
                        "last_updated": last_updated_str
                    }

        # CSVを読み込み、必要に応じて最新データを取得・追記
        csv_data = self._load_csv_data()
        next_release = self._get_next_release()

        # 発表後なら最新データをスクレイピング
        if self._is_after_release():
            new_row = self._fetch_latest_from_web()
            if new_row:
                csv_data = self._append_if_new(csv_data, new_row)

        if csv_data:
            latest = csv_data[-1] if csv_data else None

            cache_payload = {
                "data": csv_data,
                "latest": latest,
                "latest_data_date": latest["date"] if latest else None,
                "last_updated": datetime.now(JST).isoformat()
            }
            # TTLなし（発表日時ベース判定方式）
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            # ファイルにも保存
            self._save_file_cache(cache_payload)

            return {
                "data": csv_data,
                "latest": latest,
                "next_release": next_release,
                "cached": False,
                "source": "csv",
                "last_updated": datetime.now(JST).isoformat()
            }

        return {
            "data": [],
            "latest": None,
            "next_release": next_release,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _load_csv_data(self) -> List[Dict[str, Any]]:
        """CSVファイルからデータを読み込み"""
        try:
            if not CSV_FILE_PATH.exists():
                print(f"CSV file not found: {CSV_FILE_PATH}")
                return []

            df = pd.read_csv(CSV_FILE_PATH)

            result = []
            for _, row in df.iterrows():
                date_str = str(row["年月"])
                result.append({
                    "date": date_str,
                    "plentiful": float(row["豊富 (Jobs Plentiful)"]),
                    "hard": float(row["困難 (Jobs Hard to get)"]),
                    "differential": float(row["差分 (Differential)"])
                })

            # 日付順にソート
            result.sort(key=lambda x: x["date"])
            print(f"Loaded {len(result)} records from CSV")
            return result

        except Exception as e:
            print(f"Error loading CSV: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _is_after_release(self) -> bool:
        """発表日時を過ぎているかどうかを判定"""
        try:
            now = datetime.now(ET)
            today = now.date()

            # 今月の最終火曜日を計算
            last_tuesday = self._get_last_tuesday_of_month(today.year, today.month)

            # 発表時刻
            release_time = datetime(
                last_tuesday.year, last_tuesday.month, last_tuesday.day,
                self.RELEASE_HOUR_ET, self.RELEASE_MINUTE_ET,
                tzinfo=ET
            )

            return now >= release_time

        except Exception as e:
            print(f"Error checking release time: {e}")
            return False

    def _fetch_latest_from_web(self) -> Optional[Dict[str, Any]]:
        """
        公式ページから最新データをスクレイピング
        失敗時はPR Newswireにフォールバック
        """
        # 1. 公式ページから取得を試行
        result = self._fetch_from_official()
        if result:
            return result

        # 2. PR Newswireからフォールバック
        print("Official page failed, trying PR Newswire fallback...")
        result = self._fetch_from_prnewswire()
        if result:
            return result

        print("Both sources failed")
        return None

    def _fetch_from_official(self) -> Optional[Dict[str, Any]]:
        """Conference Board公式ページからデータを取得"""
        try:
            print(f"Fetching from official page: {CB_OFFICIAL_URL}")

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }

            response = requests.get(CB_OFFICIAL_URL, headers=headers, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            text = soup.get_text("\n")
            text = re.sub(r"\n{2,}", "\n", text)

            # Source: [Month] [Year] Consumer Confidence Survey を探す
            m = RE_SOURCE.search(text)
            if not m:
                print("Source pattern not found")
                return None

            month_name = m.group(1).strip().lower()
            year = int(m.group(2))
            month = MONTH_MAP.get(month_name)
            if not month:
                print(f"Unknown month: {month_name}")
                return None

            yyyymm = f"{year:04d}-{month:02d}"

            # Jobs Plentiful パーセンテージを探す
            p = RE_PLENTIFUL.search(text)
            if not p:
                p = RE_PLENTIFUL_ALT.search(text)
            if not p:
                print("Plentiful percentage not found")
                return None

            # Jobs Hard to Get パーセンテージを探す
            h = RE_HARD.search(text)
            if not h:
                h = RE_HARD_ALT.search(text)
            if not h:
                print("Hard to get percentage not found")
                return None

            plentiful = float(p.group(1))
            hard = float(h.group(1))
            diff = round(plentiful - hard, 1)

            print(f"Extracted: {yyyymm}, Plentiful: {plentiful}%, Hard: {hard}%, Diff: {diff}")

            return {
                "date": yyyymm,
                "plentiful": plentiful,
                "hard": hard,
                "differential": diff
            }

        except Exception as e:
            print(f"Error fetching from official page: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _fetch_from_prnewswire(self) -> Optional[Dict[str, Any]]:
        """PR Newswireからフォールバック取得"""
        try:
            print(f"Fetching from PR Newswire: {PR_NEWSWIRE_SEARCH_URL}")

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }

            # 検索結果ページを取得
            response = requests.get(PR_NEWSWIRE_SEARCH_URL, headers=headers, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # 最新記事のリンクを探す
            article_link = None
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if "/news-releases/" in href and "consumer-confidence" in href.lower():
                    article_link = href
                    break

            if not article_link:
                print("No article link found on PR Newswire")
                return None

            # 相対URLの場合は絶対URLに変換
            if not article_link.startswith("http"):
                article_link = "https://www.prnewswire.com" + article_link

            print(f"Found article: {article_link}")

            # 記事ページを取得
            response = requests.get(article_link, headers=headers, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            text = soup.get_text("\n")

            # 同じパターンで抽出
            m = RE_SOURCE.search(text)
            if not m:
                print("Source pattern not found in PR Newswire article")
                return None

            month_name = m.group(1).strip().lower()
            year = int(m.group(2))
            month = MONTH_MAP.get(month_name)
            if not month:
                return None

            yyyymm = f"{year:04d}-{month:02d}"

            p = RE_PLENTIFUL.search(text) or RE_PLENTIFUL_ALT.search(text)
            h = RE_HARD.search(text) or RE_HARD_ALT.search(text)

            if not p or not h:
                print("Could not extract percentages from PR Newswire")
                return None

            plentiful = float(p.group(1))
            hard = float(h.group(1))
            diff = round(plentiful - hard, 1)

            print(f"Extracted from PR Newswire: {yyyymm}, Plentiful: {plentiful}%, Hard: {hard}%, Diff: {diff}")

            return {
                "date": yyyymm,
                "plentiful": plentiful,
                "hard": hard,
                "differential": diff
            }

        except Exception as e:
            print(f"Error fetching from PR Newswire: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _append_if_new(
        self,
        csv_data: List[Dict[str, Any]],
        new_row: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        新しいデータをCSVに追記（既存データにない場合のみ）
        """
        try:
            # 既に存在するかチェック
            existing_dates = {item["date"] for item in csv_data}
            if new_row["date"] in existing_dates:
                print(f"Date {new_row['date']} already exists, skipping")
                return csv_data

            # バックアップを作成
            if CSV_FILE_PATH.exists():
                backup_path = str(CSV_FILE_PATH) + ".bak"
                shutil.copyfile(CSV_FILE_PATH, backup_path)

            # CSVに追記
            csv_data.append(new_row)
            csv_data.sort(key=lambda x: x["date"])

            # CSVを保存
            df = pd.DataFrame(csv_data)
            df = df.rename(columns={
                "date": "年月",
                "plentiful": "豊富 (Jobs Plentiful)",
                "hard": "困難 (Jobs Hard to get)",
                "differential": "差分 (Differential)"
            })
            df.to_csv(CSV_FILE_PATH, index=False, encoding="utf-8-sig")

            print(f"Appended new data: {new_row}")
            return csv_data

        except Exception as e:
            print(f"Error appending to CSV: {e}")
            import traceback
            traceback.print_exc()
            return csv_data

    def _should_refresh(self, last_updated_str: str) -> bool:
        """
        キャッシュを更新すべきかどうかを判定

        判定ロジック:
        - 次回発表日時（最終火曜日 10:00 ET）を過ぎており、かつ最終更新が発表日時より前なら更新
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)

            # 今月の発表日時を計算
            now_et = datetime.now(ET)
            today = now_et.date()
            last_tuesday = self._get_last_tuesday_of_month(today.year, today.month)

            # 発表時刻（10:00 ET）をJSTに変換
            release_et = datetime(
                last_tuesday.year, last_tuesday.month, last_tuesday.day,
                self.RELEASE_HOUR_ET, self.RELEASE_MINUTE_ET,
                tzinfo=ET
            )
            release_jst = release_et.astimezone(JST)

            # 発表日時を過ぎており、かつ最終更新が発表日時より前なら更新が必要
            if now >= release_jst and last_updated < release_jst:
                return True

            return False

        except Exception as e:
            print(f"Error checking refresh status: {e}")
            return False

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """
        次回発表日を計算

        1. キャッシュをチェック（未来の日付があればそのまま返す）
        2. キャッシュ内の日付が過去でも48時間以内ならスクレイピングしない
        3. Investing.comから次回発表日を取得
        """
        try:
            today = date.today()

            # キャッシュをチェック
            cached = redis_client.get(self.SCHEDULE_CACHE_KEY)
            if cached:
                next_date_str = cached.get("next_release_date")
                if next_date_str:
                    next_date = datetime.strptime(next_date_str, "%Y-%m-%d").date()
                    if next_date >= today:
                        return {
                            "date": next_date_str,
                            "label": cached.get("label", f"CB Consumer Confidence - {next_date_str}")
                        }

                # キャッシュ内の日付が過去 → 再取得が必要かチェック
                # ただし、48時間以内にスクレイピングしていたら再取得しない（過剰アクセス防止）
                cached_at = cached.get("cached_at")
                if cached_at:
                    try:
                        cached_dt = datetime.fromisoformat(cached_at)
                        if cached_dt.tzinfo is None:
                            cached_dt = cached_dt.replace(tzinfo=JST)
                        hours_since_cache = (datetime.now(JST) - cached_dt).total_seconds() / 3600
                        if hours_since_cache < 48:
                            # 48時間以内にスクレイピング済み → Noneを返す
                            return None
                    except Exception:
                        pass

            # Investing.comから取得を試行
            investing_result = self._fetch_next_release_from_investing()
            if investing_result:
                # キャッシュに保存
                cache_payload = {
                    "next_release_date": investing_result["date"],
                    "label": investing_result["label"],
                    "cached_at": datetime.now(JST).isoformat()
                }
                redis_client.set(self.SCHEDULE_CACHE_KEY, cache_payload, expire=30 * 24 * 60 * 60)
                return investing_result

            # Investing.comから取得できなかった場合もキャッシュに記録（再スクレイピング防止）
            cache_payload = {
                "next_release_date": None,
                "label": None,
                "fetch_failed": True,
                "cached_at": datetime.now(JST).isoformat()
            }
            redis_client.set(self.SCHEDULE_CACHE_KEY, cache_payload, expire=30 * 24 * 60 * 60)
            print("次回発表日: Investing.comから取得できませんでした")
            return None

        except Exception as e:
            print(f"Error getting next release: {e}")
            return None

    def _fetch_next_release_from_investing(self) -> Optional[Dict[str, Any]]:
        """Investing.comから次回発表日を取得"""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
                "Referer": "https://jp.investing.com/"
            }

            response = requests.get(INVESTING_CB_URL, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            # 次回発表日を取得
            next_event = data.get("next_event")
            if next_event:
                timestamp = next_event.get("timestamp")
                if timestamp:
                    dt = datetime.fromtimestamp(timestamp / 1000, tz=ET)
                    date_str = dt.strftime("%Y-%m-%d")
                    return {
                        "date": date_str,
                        "label": f"CB Consumer Confidence - {date_str} (火) 10:00 ET"
                    }

            return None

        except Exception as e:
            print(f"Error fetching from Investing.com: {e}")
            return None

    def _calculate_next_release(self) -> Optional[Dict[str, Any]]:
        """
        次回発表日を計算（最終火曜日ロジック）
        """
        try:
            now = datetime.now(ET)
            today = now.date()

            # 今月の最終火曜日を計算
            last_tuesday_this_month = self._get_last_tuesday_of_month(today.year, today.month)

            # 発表時刻
            release_time = datetime(
                last_tuesday_this_month.year, last_tuesday_this_month.month, last_tuesday_this_month.day,
                self.RELEASE_HOUR_ET, self.RELEASE_MINUTE_ET,
                tzinfo=ET
            )

            # 今月の発表日時を過ぎていれば来月の最終火曜日
            if now >= release_time:
                if today.month == 12:
                    next_year = today.year + 1
                    next_month = 1
                else:
                    next_year = today.year
                    next_month = today.month + 1

                next_release_date = self._get_last_tuesday_of_month(next_year, next_month)
            else:
                next_release_date = last_tuesday_this_month

            return {
                "date": next_release_date.strftime("%Y-%m-%d"),
                "label": f"CB Consumer Confidence - {next_release_date.strftime('%Y/%m/%d')} (火) 10:00 ET"
            }

        except Exception as e:
            print(f"Error calculating next release: {e}")
            return None

    def _get_last_tuesday_of_month(self, year: int, month: int) -> date:
        """
        指定した年月の最終火曜日を取得
        """
        # 月末を計算
        if month == 12:
            next_month = date(year + 1, 1, 1)
        else:
            next_month = date(year, month + 1, 1)

        last_day = next_month - timedelta(days=1)

        # 最終火曜日を探す（火曜日=1）
        days_since_tuesday = (last_day.weekday() - 1) % 7
        last_tuesday = last_day - timedelta(days=days_since_tuesday)

        return last_tuesday

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込み"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None

            with open(DATA_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Cache saved to {DATA_CACHE_FILE}")
        except Exception as e:
            print(f"Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        redis_client.delete(self.SCHEDULE_CACHE_KEY)
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "CB Jobs Labor Differential",
            "source": "Conference Board",
            "url": CB_OFFICIAL_URL,
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": self._get_next_release(),
            "csv_file_exists": CSV_FILE_PATH.exists(),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
cb_jobs_labor_differential_service = CBJobsLaborDifferentialService()
