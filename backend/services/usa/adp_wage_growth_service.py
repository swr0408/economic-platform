"""
ADP賃金上昇率中央値（ADP Pay Insights）サービス
ADP Pay InsightsからZIPファイルをダウンロードしCSVを解析

指標:
- Job Changer: 転職者の賃金上昇率中央値（%）
- Job Stayer: 在職者の賃金上昇率中央値（%）

データソース:
- ADP Pay Insights: https://adp-ri-nrip-static.adp.com/artifacts/us_wage/

発表スケジュール:
- 毎月第1水曜日 8:15 AM ET（ADP National Employment Reportと同時）
- ADP雇用者数サービスの発表日を参照

キャッシュ方式: 発表日時ベース判定方式
"""
import os
import io
import json
import zipfile
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests
import pandas as pd

from core.redis_client import redis_client
from services.usa.release_schedule_utils import ADP_EMPLOYMENT_CHECKER


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
ET = ZoneInfo("America/New_York")

# ADP Pay Insights データURL（URLのバージョン部分は変動する可能性あり）
# 最新のURLを取得するために複数のパターンを試す
ADP_DATA_URL_BASE = "https://adp-ri-nrip-static.adp.com/artifacts/us_wage/"

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "usa" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "adp_wage_growth_cache.json"


class ADPWageGrowthService:
    """ADP賃金上昇率中央値サービス"""

    DATA_CACHE_KEY = "adp:wage_growth:data"

    # 発表時刻設定（ET）- 8:15 AM ET（ADP雇用者数と同じ）
    RELEASE_HOUR_ET = 8
    RELEASE_MINUTE_ET = 15

    def __init__(self):
        self.schedule_checker = ADP_EMPLOYMENT_CHECKER

    def get_adp_wage_growth_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        ADP賃金上昇率中央値データを取得

        Returns:
            {
                "data": [{"date": str, "job_changer": float, "job_stayer": float}, ...],
                "latest": {...},
                "next_release": None,
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
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "next_release": None,
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
                    redis_client.set(self.DATA_CACHE_KEY, file_cache, expire=0)
                    return {
                        "data": file_cache.get("data", []),
                        "latest": file_cache.get("latest"),
                        "next_release": None,
                        "cached": True,
                        "source": "file",
                        "last_updated": last_updated_str
                    }

        # ADP Pay Insights から取得
        api_data = self._fetch_from_adp()

        if api_data:
            latest = api_data[-1] if api_data else None

            cache_payload = {
                "data": api_data,
                "latest": latest,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": api_data,
                "latest": latest,
                "next_release": None,
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
                "next_release": None,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
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

    def _fetch_from_adp(self) -> Optional[List[Dict[str, Any]]]:
        """ADP Pay Insights からデータを取得"""
        try:
            print("Fetching ADP Wage Growth from ADP Pay Insights...")

            # 現在の日付からURLを構築（最新バージョンを探す）
            now = datetime.now()
            data_url = None

            # 直近数ヶ月のURLパターンを試す
            for months_ago in range(0, 6):
                test_date = now.replace(day=1)
                for _ in range(months_ago):
                    if test_date.month == 1:
                        test_date = test_date.replace(year=test_date.year - 1, month=12)
                    else:
                        test_date = test_date.replace(month=test_date.month - 1)

                version_str = test_date.strftime("%Y%m01")
                test_url = f"{ADP_DATA_URL_BASE}{version_str}/ADP_PAY_history.zip"

                try:
                    response = requests.head(test_url, timeout=10)
                    if response.status_code == 200:
                        data_url = test_url
                        print(f"Found ADP data at: {data_url}")
                        break
                except Exception:
                    continue

            if not data_url:
                # フォールバック: 固定URL
                data_url = "https://adp-ri-nrip-static.adp.com/artifacts/us_wage/20251001/ADP_PAY_history.zip"
                print(f"Using fallback URL: {data_url}")

            # ZIPファイルをダウンロード
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = requests.get(data_url, headers=headers, timeout=60)
            response.raise_for_status()

            # ZIPをメモリ上で解凍
            zip_file = zipfile.ZipFile(io.BytesIO(response.content))

            # CSVファイルを読み込む
            with zip_file.open("ADP_PAY_history.csv") as f:
                df = pd.read_csv(f)

            # Job Changer と Job Stayer のデータを抽出
            job_changer_df = df[(df['agg'] == 'Worker Type') & (df['category'] == 'Job Changer')].copy()
            job_stayer_df = df[(df['agg'] == 'Worker Type') & (df['category'] == 'Job Stayer')].copy()

            # 日付でソート
            job_changer_df = job_changer_df.sort_values('date')
            job_stayer_df = job_stayer_df.sort_values('date')

            # 日付をキーにしてマージ
            stayer_map = {}
            for _, row in job_stayer_df.iterrows():
                date_value = row['date']
                value = row['median pay change']
                if pd.notna(value):
                    stayer_map[date_value] = float(value)

            result_data = []
            for _, changer_row in job_changer_df.iterrows():
                date_value = changer_row['date']
                job_changer_value = changer_row['median pay change']

                if pd.notna(job_changer_value):
                    job_stayer_value = stayer_map.get(date_value)

                    if job_stayer_value is not None:
                        # 日付を YYYY-MM-DD 形式に変換
                        date_obj = pd.to_datetime(date_value)
                        date_str = date_obj.strftime('%Y-%m-%d')

                        result_data.append({
                            "date": date_str,
                            "job_changer": round(float(job_changer_value), 1),
                            "job_stayer": round(float(job_stayer_value), 1)
                        })

            # 日付でソート（昇順）
            result_data.sort(key=lambda x: x['date'])

            print(f"Fetched {len(result_data)} ADP Wage Growth records")
            return result_data

        except Exception as e:
            print(f"Error fetching ADP Wage Growth: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        return self.schedule_checker.should_refresh(last_updated_str)

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
            "indicator": "ADP Wage Growth (Pay Insights)",
            "source": "ADP Pay Insights",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "schedule_status": self.schedule_checker.get_status(),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
adp_wage_growth_service = ADPWageGrowthService()
