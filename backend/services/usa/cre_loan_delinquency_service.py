"""
CREローン延滞率サービス（Commercial Real Estate Loan Delinquency Rate）
FRED APIからCRE延滞率データを取得

シリーズID:
- DRCRELEXFACBS: Delinquency Rate on Commercial Real Estate Loans (Excluding Farmland),
                 Booked in Domestic Offices, All Commercial Banks
                 (四半期、季節調整済み、パーセント)
- DRCRELEXFT100S: Same, Banks Ranked 1st to 100th Largest
- DRCRELEXFOBS: Same, Banks Not Among the 100 Largest

データソース:
- FRB Charge-Off and Delinquency Rates on Loans and Leases at Commercial Banks
- https://www.federalreserve.gov/releases/chargeoff/

発表スケジュール:
- 四半期末60日後に発表（2月・5月・8月・11月）
- 発表時刻: 約10:00 ET

キャッシュ方式: 発表日時ベース判定方式
"""
import os
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests

from core.redis_client import redis_client


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
ET = ZoneInfo("America/New_York")

# FREDシリーズID
SERIES_IDS = {
    "all_banks": "DRCRELEXFACBS",      # All Commercial Banks
    "top_100": "DRCRELEXFT100S",       # Top 100 Banks
    "other_banks": "DRCRELEXFOBS",     # Banks Not Among Top 100
}

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "usa" / "monetary_policy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "cre_loan_delinquency_cache.json"


class CRELoanDelinquencyService:
    """CREローン延滞率サービス"""

    BASE_URL = "https://api.stlouisfed.org/fred"
    DATA_CACHE_KEY = "usa:cre_loan_delinquency:data"

    # 発表月（四半期末60日後）
    RELEASE_MONTHS = [2, 5, 8, 11]  # 2月・5月・8月・11月
    RELEASE_DAY_APPROX = 21  # 大体21日前後

    def __init__(self):
        self.api_key = os.environ.get("FRED_API_KEY", "")

    def get_cre_delinquency_data(
        self,
        start_date: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        CREローン延滞率データを取得

        Args:
            start_date: 開始日 (YYYY-MM-DD)
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "data": [{"date": "YYYY-MM-DD", "all_banks": float, "top_100": float, "other_banks": float}, ...],
                "latest": {...},
                "metadata": {...},
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
                if last_updated_str and not self._should_refresh(last_updated_str, cached_data):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": self._get_next_release(),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # ファイルキャッシュチェック
        if not force_refresh:
            file_cache = self._load_file_cache()
            if file_cache:
                last_updated_str = file_cache.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str, file_cache):
                    # Redisにも保存
                    redis_client.set(self.DATA_CACHE_KEY, file_cache, expire=0)

                    return {
                        "data": file_cache.get("data", []),
                        "latest": file_cache.get("latest"),
                        "metadata": file_cache.get("metadata", {}),
                        "next_release": self._get_next_release(),
                        "cached": True,
                        "source": "file",
                        "last_updated": last_updated_str
                    }

        # 外部APIから取得
        api_data = self._fetch_from_api(start_date)

        if api_data:
            latest = api_data[-1] if api_data else None

            metadata = {
                "source": "Federal Reserve Board",
                "description": "Delinquency Rate on Commercial Real Estate Loans (Excluding Farmland)",
                "unit": "%",
                "frequency": "Quarterly",
                "series": {
                    "all_banks": "DRCRELEXFACBS - All Commercial Banks",
                    "top_100": "DRCRELEXFT100S - Top 100 Banks",
                    "other_banks": "DRCRELEXFOBS - Banks Not Among Top 100"
                }
            }

            cache_payload = {
                "data": api_data,
                "latest": latest,
                "metadata": metadata,
                "last_updated": datetime.now(JST).isoformat()
            }
            # TTLなし（発表日時ベース判定方式）
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            # ファイルにも保存
            self._save_file_cache(cache_payload)

            return {
                "data": api_data,
                "latest": latest,
                "metadata": metadata,
                "next_release": self._get_next_release(),
                "cached": False,
                "source": "api",
                "last_updated": datetime.now(JST).isoformat()
            }

        # 取得失敗時はファイルキャッシュから返す
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "metadata": file_cache.get("metadata", {}),
                "next_release": self._get_next_release(),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": [],
            "latest": None,
            "metadata": {},
            "next_release": self._get_next_release(),
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _fetch_from_api(
        self,
        start_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """FRED APIからCRE延滞率データを取得（複数シリーズ）"""
        try:
            if not self.api_key:
                print("FRED_API_KEY not set")
                return []

            print("Fetching CRE Loan Delinquency Rate from FRED...")

            # デフォルト期間（1991年から - データ開始時点）
            if not start_date:
                start_date = "1991-01-01"

            # 各シリーズのデータを取得
            series_data = {}
            for key, series_id in SERIES_IDS.items():
                url = f"{self.BASE_URL}/series/observations"
                params = {
                    "series_id": series_id,
                    "api_key": self.api_key,
                    "file_type": "json",
                    "observation_start": start_date,
                    "sort_order": "asc"
                }

                response = requests.get(url, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()

                series_data[key] = {}
                for obs in data.get("observations", []):
                    if obs.get("value") and obs["value"] != ".":
                        try:
                            series_data[key][obs["date"]] = round(float(obs["value"]), 2)
                        except (ValueError, TypeError):
                            continue

            # 日付をマージ
            all_dates = set()
            for key in series_data:
                all_dates.update(series_data[key].keys())

            result = []
            for date_str in sorted(all_dates):
                entry = {
                    "date": date_str,
                    "all_banks": series_data["all_banks"].get(date_str),
                    "top_100": series_data["top_100"].get(date_str),
                    "other_banks": series_data["other_banks"].get(date_str),
                }
                # all_banksがない場合はスキップ
                if entry["all_banks"] is not None:
                    result.append(entry)

            print(f"Fetched {len(result)} quarterly records from FRED (CRE Loan Delinquency)")
            if result:
                latest = result[-1]
                print(f"Latest: {latest['date']} - All Banks: {latest['all_banks']}%")

            return result

        except Exception as e:
            print(f"Error fetching CRE Loan Delinquency: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _should_refresh(self, last_updated_str: str, cached_data: dict = None) -> bool:
        """
        キャッシュを更新すべきかどうかを判定

        以下の条件で更新:
        1. 発表月（2月・5月・8月・11月）の15日以降で、最終更新から24時間以上経過
        2. 最新データの四半期より現在の四半期が進んでいる場合（発表後の更新漏れ対策）

        Args:
            last_updated_str: 最終更新日時（ISO形式）
            cached_data: キャッシュされたデータ（latest情報を含む）
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)
            now_et = now.astimezone(ET)

            # 条件1: 発表月の15日以降かチェック
            if now_et.month in self.RELEASE_MONTHS and now_et.day >= 15:
                # 最終更新から24時間以上経過していれば更新
                hours_since_update = (now - last_updated).total_seconds() / 3600
                if hours_since_update >= 24:
                    return True

            # 条件2: 最新データの四半期と現在を比較（発表後の更新漏れ対策）
            if cached_data and cached_data.get("latest"):
                latest_date_str = cached_data["latest"].get("date")
                if latest_date_str:
                    latest_date = datetime.strptime(latest_date_str, "%Y-%m-%d")
                    # 最新データの四半期を計算
                    latest_quarter = (latest_date.month - 1) // 3 + 1
                    latest_year = latest_date.year

                    # 現在の四半期を計算（発表は四半期末の約60日後）
                    # 2月発表 = Q4データ、5月発表 = Q1データ、8月発表 = Q2データ、11月発表 = Q3データ
                    current_month = now_et.month
                    current_year = now_et.year

                    # 発表済みの最新四半期を推定
                    # 2月15日以降: Q4(前年)データが利用可能
                    # 5月15日以降: Q1データが利用可能
                    # 8月15日以降: Q2データが利用可能
                    # 11月15日以降: Q3データが利用可能
                    expected_quarter = None
                    expected_year = None

                    if current_month >= 11 and now_et.day >= 15:
                        expected_quarter = 3
                        expected_year = current_year
                    elif current_month >= 8 and now_et.day >= 15:
                        expected_quarter = 2
                        expected_year = current_year
                    elif current_month >= 5 and now_et.day >= 15:
                        expected_quarter = 1
                        expected_year = current_year
                    elif current_month >= 2 and now_et.day >= 15:
                        expected_quarter = 4
                        expected_year = current_year - 1

                    if expected_quarter and expected_year:
                        # 期待される四半期が最新データより新しい場合は更新
                        expected_date = datetime(expected_year, expected_quarter * 3, 1)
                        latest_quarter_date = datetime(latest_year, latest_quarter * 3, 1)
                        if expected_date > latest_quarter_date:
                            print(f"[CRE] Stale data detected: latest={latest_year}Q{latest_quarter}, expected={expected_year}Q{expected_quarter}")
                            return True

            return False

        except Exception as e:
            print(f"Error in _should_refresh: {e}")
            return True

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """
        次回発表日を推定

        四半期末60日後（2月・5月・8月・11月の21日頃）
        """
        try:
            now = datetime.now(ET)

            # 次の発表月を見つける
            for month in self.RELEASE_MONTHS:
                if month > now.month or (month == now.month and now.day < self.RELEASE_DAY_APPROX):
                    next_date = datetime(now.year, month, self.RELEASE_DAY_APPROX, tzinfo=ET)
                    quarter_map = {2: "Q4", 5: "Q1", 8: "Q2", 11: "Q3"}
                    quarter = quarter_map.get(month, "")
                    year = now.year if month != 2 else now.year - 1
                    return {
                        "date": next_date.strftime("%Y-%m-%d"),
                        "label": f"CRE Loan Delinquency Rate ({quarter} {year})"
                    }

            # 来年の2月
            next_date = datetime(now.year + 1, 2, self.RELEASE_DAY_APPROX, tzinfo=ET)
            return {
                "date": next_date.strftime("%Y-%m-%d"),
                "label": f"CRE Loan Delinquency Rate (Q4 {now.year})"
            }

        except Exception as e:
            print(f"Error getting next release: {e}")
            return None

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
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "series_ids": SERIES_IDS,
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": self._get_next_release(),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
cre_loan_delinquency_service = CRELoanDelinquencyService()
