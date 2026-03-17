"""
日銀当座預金残高サービス

BOJ時系列統計データ検索サイトAPI（DB=MD08）から
業態別の日銀当座預金残高（末残・合計）を月次取得

系列コード: MACAB2201 = 合計(総)(F+G) / 末残
単位: 億円

発表スケジュール:
- tkohyos.xlsx（年2回更新）から「業態別の日銀当座預金残高」の時系列掲載日を取得
- BOJデータ検索サイトへの掲載は公表日の数営業日後（8:50頃）

データソース: 日本銀行 時系列統計データ検索サイト
キャッシュ方式: 24時間固定TTL
"""
import io
import json
import requests
import pandas as pd
from datetime import datetime, timedelta, date
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client


JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "japan" / "policy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_FILE = CACHE_DIR / "boj_current_account_balance_cache.json"
SCHEDULE_CACHE_FILE = CACHE_DIR / "boj_current_account_balance_schedule.json"

# BOJ 時系列統計データ検索サイト API
# MACAB2201 = 日銀当座預金 / 合計(総)(F+G) / 末残
BOJ_API_URL = (
    "https://www.stat-search.boj.or.jp/api/v1/getDataCode"
    "?FORMAT=JSON&LANG=JP&DB=MD08&CODE=MACAB2201"
    "&STARTDATE=200501&ENDDATE=203012"
)

# 発表スケジュール Excel
SCHEDULE_URL = "https://www.boj.or.jp/statistics/outline/tkohyos.xlsx"

# スケジュールRedisキー
SCHEDULE_CACHE_KEY = "japan:boj_current_account_balance:schedule"


class BojCurrentAccountBalanceService:
    """日銀当座預金残高サービス"""

    CACHE_KEY = "japan:boj_current_account_balance:data"

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """日銀当座預金残高データを取得"""
        next_release = self._get_next_release()

        if not force_refresh:
            cached = redis_client.get(self.CACHE_KEY)
            if cached:
                last_updated_str = cached.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached.get("data", []),
                        "latest": cached.get("latest"),
                        "metadata": cached.get("metadata", {}),
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

            # ファイルキャッシュ
            file_cache = self._load_file_cache()
            if file_cache:
                last_updated_str = file_cache.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    redis_client.set(self.CACHE_KEY, file_cache, expire=0)
                    return {
                        "data": file_cache.get("data", []),
                        "latest": file_cache.get("latest"),
                        "metadata": file_cache.get("metadata", {}),
                        "next_release": next_release,
                        "cached": True,
                        "source": "file",
                        "last_updated": last_updated_str,
                    }

        api_result = self._fetch_from_boj()
        if api_result:
            latest = api_result[-1] if api_result else None
            metadata = {
                "source": "日本銀行 時系列統計データ検索サイト",
                "indicator": "業態別の日銀当座預金残高（末残・合計）",
                "unit": "億円",
                "display_unit": "兆円",
                "frequency": "Monthly",
                "series_code": "MACAB2201",
            }

            cache_payload = {
                "data": api_result,
                "latest": latest,
                "metadata": metadata,
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": api_result,
                "latest": latest,
                "metadata": metadata,
                "next_release": next_release,
                "cached": False,
                "source": "boj_api",
                "last_updated": datetime.now(JST).isoformat(),
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
        }

    def _fetch_from_boj(self) -> Optional[List[Dict[str, Any]]]:
        """BOJ APIからデータを取得"""
        try:
            print("[BOJ Current Account] Fetching from BOJ API...")
            resp = requests.get(
                BOJ_API_URL,
                timeout=60,
                headers={"User-Agent": "Mozilla/5.0 (economic-platform)"},
            )
            resp.raise_for_status()
            raw = resp.json()

            return self._parse_response(raw)

        except requests.exceptions.RequestException as e:
            print(f"[BOJ Current Account] Request error: {e}")
            return None
        except Exception as e:
            print(f"[BOJ Current Account] Parse error: {e}")
            return None

    def _parse_response(self, raw_data: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """APIレスポンスをパース"""
        try:
            resultset = raw_data.get("RESULTSET", [])
            if not resultset:
                print("[BOJ Current Account] No RESULTSET in response")
                return None

            item = resultset[0]
            values_obj = item.get("VALUES", {})
            dates = values_obj.get("SURVEY_DATES", [])
            values = values_obj.get("VALUES", [])

            if not dates or not values or len(dates) != len(values):
                print(f"[BOJ Current Account] Data mismatch: dates={len(dates)}, values={len(values)}")
                return None

            result = []
            for date_int, value in zip(dates, values):
                if value is None:
                    continue

                # YYYYMM → YYYY-MM-01
                date_str = str(date_int)
                if len(date_str) != 6:
                    continue
                year = date_str[:4]
                month = date_str[4:6]
                date_formatted = f"{year}-{month}-01"

                value_float = float(value)
                result.append({
                    "date": date_formatted,
                    "value": value_float,
                    "value_trillion": round(value_float / 10000, 2),
                })

            result.sort(key=lambda x: x["date"])
            print(f"[BOJ Current Account] Parsed {len(result)} monthly records")
            return result

        except Exception as e:
            print(f"[BOJ Current Account] Error parsing response: {e}")
            return None

    # ========== スケジュール ==========

    def _get_next_release(self) -> Optional[Dict[str, str]]:
        """次回発表日を取得（tkohyos.xlsx からパース）"""
        try:
            schedule = self._get_schedule()
            if not schedule:
                return None

            today = date.today()
            for release_date_str in schedule:
                release_date = date.fromisoformat(release_date_str)
                if release_date >= today:
                    return {
                        "date": release_date_str,
                        "time": "08:50",
                        "label": "業態別の日銀当座預金残高（時系列掲載）",
                    }

            return None
        except Exception as e:
            print(f"[BOJ Current Account] Error getting next release: {e}")
            return None

    def _get_schedule(self) -> Optional[List[str]]:
        """発表スケジュールを取得（キャッシュ付き）"""
        # Redisキャッシュ
        cached = redis_client.get(SCHEDULE_CACHE_KEY)
        if cached and isinstance(cached, dict):
            dates = cached.get("dates", [])
            fetched_at = cached.get("fetched_at", "")
            # 30日間有効（年2回更新なので十分）
            if fetched_at and dates:
                try:
                    fetched_dt = datetime.fromisoformat(fetched_at)
                    if fetched_dt.tzinfo is None:
                        fetched_dt = fetched_dt.replace(tzinfo=JST)
                    if (datetime.now(JST) - fetched_dt) < timedelta(days=30):
                        return dates
                except Exception:
                    pass

        # ファイルキャッシュ
        file_schedule = self._load_schedule_file_cache()
        if file_schedule:
            dates = file_schedule.get("dates", [])
            fetched_at = file_schedule.get("fetched_at", "")
            if fetched_at and dates:
                try:
                    fetched_dt = datetime.fromisoformat(fetched_at)
                    if fetched_dt.tzinfo is None:
                        fetched_dt = fetched_dt.replace(tzinfo=JST)
                    if (datetime.now(JST) - fetched_dt) < timedelta(days=30):
                        redis_client.set(SCHEDULE_CACHE_KEY, file_schedule, expire=0)
                        return dates
                except Exception:
                    pass

        # Excel取得
        dates = self._fetch_schedule_from_excel()
        if dates:
            payload = {
                "dates": dates,
                "fetched_at": datetime.now(JST).isoformat(),
            }
            redis_client.set(SCHEDULE_CACHE_KEY, payload, expire=0)
            self._save_schedule_file_cache(payload)
            return dates

        # ファイルフォールバック（期限切れでも使う）
        if file_schedule and file_schedule.get("dates"):
            return file_schedule["dates"]

        return None

    def _fetch_schedule_from_excel(self) -> Optional[List[str]]:
        """tkohyos.xlsx から業態別の日銀当座預金残高の時系列掲載日を取得"""
        try:
            print("[BOJ Current Account] Fetching schedule from tkohyos.xlsx...")
            resp = requests.get(
                SCHEDULE_URL,
                timeout=30,
                headers={"User-Agent": "Mozilla/5.0 (economic-platform)"},
            )
            resp.raise_for_status()

            df = pd.read_excel(
                io.BytesIO(resp.content),
                sheet_name=1,  # 統計データシート
                header=None,
                engine="openpyxl",
            )

            # 「業態別の日銀当座預金残高」の行を探す
            # col1 = 統計名, col2 = 掲載箇所, col3 = 公表時刻
            # 時系列の日付行を取得（掲載箇所が「時系列」で頻度が「(月次)」の行）
            target_dates: List[str] = []

            for i in range(len(df)):
                stat_name = str(df.iloc[i, 1]) if pd.notna(df.iloc[i, 1]) else ""
                posting = str(df.iloc[i, 2]) if pd.notna(df.iloc[i, 2]) else ""
                time_freq = str(df.iloc[i, 3]) if pd.notna(df.iloc[i, 3]) else ""

                # 「業態別の日銀当座預金残高」+「時系列」+「(月次)」の日付行
                if "業態別の日銀当座預金残高" in stat_name and "時系列" in posting and "(月次)" in time_freq:
                    # この行のcol4〜col15 (1月〜12月) に日付が入っている
                    for col_idx in range(4, min(16, df.shape[1])):
                        cell = df.iloc[i, col_idx]
                        if pd.notna(cell):
                            if isinstance(cell, datetime):
                                target_dates.append(cell.strftime("%Y-%m-%d"))
                            elif isinstance(cell, str) and len(cell) >= 10:
                                target_dates.append(cell[:10])

            if target_dates:
                target_dates.sort()
                print(f"[BOJ Current Account] Found {len(target_dates)} schedule dates: {target_dates[:3]}...")
                return target_dates

            print("[BOJ Current Account] No schedule dates found in Excel")
            return None

        except Exception as e:
            print(f"[BOJ Current Account] Error fetching schedule: {e}")
            return None

    def _load_schedule_file_cache(self) -> Optional[Dict[str, Any]]:
        try:
            if not SCHEDULE_CACHE_FILE.exists():
                return None
            with open(SCHEDULE_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def _save_schedule_file_cache(self, data: Dict[str, Any]) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(SCHEDULE_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[BOJ Current Account] Failed to save schedule cache: {e}")

    # ========== キャッシュ ==========

    def _should_refresh(self, last_updated_str: str) -> bool:
        """24時間経過またはJST 9:00を過ぎた新しい日なら更新"""
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)

            if (now - last_updated) > timedelta(hours=24):
                return True

            if last_updated.date() < now.date() and now.hour >= 9:
                return True

            return False
        except Exception:
            return True

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        try:
            if not CACHE_FILE.exists():
                return None
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[BOJ Current Account] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[BOJ Current Account] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        return redis_client.delete(self.CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        exists = redis_client.exists(self.CACHE_KEY)
        cached = redis_client.get(self.CACHE_KEY) if exists else None
        next_release = self._get_next_release()
        return {
            "indicator": "日銀当座預金残高（末残・合計）",
            "source": "BOJ 時系列統計データ検索サイト API",
            "cache_key": self.CACHE_KEY,
            "exists": exists,
            "last_updated": cached.get("last_updated") if cached else None,
            "data_count": len(cached.get("data", [])) if cached else 0,
            "next_release": next_release,
        }


# シングルトンインスタンス
boj_current_account_balance_service = BojCurrentAccountBalanceService()
