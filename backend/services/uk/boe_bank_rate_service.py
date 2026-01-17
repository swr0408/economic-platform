"""
BOE Bank Rate (政策金利) サービス
Bank of England公式データベースからBank Rateデータを取得

指標:
- Official Bank Rate (IUDBEDR)

データソース:
- BOE Statistical Database
- https://www.bankofengland.co.uk/boeapps/database/

発表スケジュール:
- MPC（金融政策委員会）発表日（年8回程度）
- 発表時刻: 12:00 ロンドン時間

キャッシュ方式: 週次更新（7日TTL）+ MPC発表日は頻繁更新
"""
import json
import requests
import pandas as pd
from io import StringIO
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client


JST = ZoneInfo("Asia/Tokyo")
LONDON = ZoneInfo("Europe/London")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "uk" / "monetary_policy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "boe_bank_rate_cache.json"


class BOEBankRateService:
    """BOE Bank Rate サービス"""

    DATA_CACHE_KEY = "uk:boe_bank_rate:data"

    # BOE Statistical Database API
    BOE_API_URL = "https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp"
    # Official Bank Rate series code
    SERIES_CODE = "IUDBEDR"

    def __init__(self):
        pass

    def get_boe_bank_rate_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """BOE Bank Rateデータを取得"""
        # 次回発表日を取得
        next_release = self._get_next_release()

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

        # BOE公式データベースから取得
        api_result = self._fetch_from_boe()

        if api_result:
            cache_payload = {
                "data": api_result.get("data", []),
                "latest": api_result.get("latest"),
                "metadata": {
                    "source": "Bank of England",
                    "indicator": "Official Bank Rate",
                    "series_code": self.SERIES_CODE,
                    "description": "BOE政策金利（Bank Rate）",
                },
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": api_result.get("data", []),
                "latest": api_result.get("latest"),
                "metadata": cache_payload["metadata"],
                "next_release": next_release,
                "cached": False,
                "source": "boe_api",
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
            "error": "No data available",
        }

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """次回発表日を取得"""
        try:
            from services.uk.fmp_next_release_utils import get_next_release_by_pattern
            # BOE Interest Rate Decision を検索
            return get_next_release_by_pattern("Interest Rate Decision", country="GB")
        except Exception as e:
            print(f"[BOEBankRate] Error getting next release: {e}")
            return None

    def _fetch_from_boe(self) -> Optional[Dict[str, Any]]:
        """BOE公式データベースからデータを取得"""
        try:
            print(f"[BOEBankRate] Fetching from BOE database (series: {self.SERIES_CODE})")

            params = {
                'csv.x': 'yes',
                'Datefrom': '01/Jan/2000',
                'Dateto': 'now',
                'SeriesCodes': self.SERIES_CODE,
                'UsingCodes': 'Y',
                'CSVF': 'TT'
            }

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }

            response = requests.get(
                self.BOE_API_URL,
                params=params,
                headers=headers,
                timeout=60
            )
            response.raise_for_status()

            print(f"[BOEBankRate] Received {len(response.text)} bytes")

            return self._process_boe_csv(response.text)

        except requests.exceptions.RequestException as e:
            print(f"[BOEBankRate] Request error: {e}")
            return None
        except Exception as e:
            print(f"[BOEBankRate] Error fetching from BOE: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _process_boe_csv(self, csv_text: str) -> Optional[Dict[str, Any]]:
        """BOE CSVレスポンスを処理"""
        try:
            lines = csv_text.strip().split('\n')

            # データセクションを探す (DATE, で始まる行)
            data_start_idx = 0
            for i, line in enumerate(lines):
                if line.startswith('DATE,'):
                    data_start_idx = i
                    break

            if data_start_idx == 0:
                print("[BOEBankRate] Could not find data section in CSV")
                return None

            # データセクションをパース
            data_csv = '\n'.join(lines[data_start_idx:])
            df = pd.read_csv(StringIO(data_csv))

            print(f"[BOEBankRate] Parsed CSV: {len(df)} rows")

            # 日付と値を処理
            df['DATE'] = pd.to_datetime(df['DATE'], format='%d %b %Y', errors='coerce')
            df[self.SERIES_CODE] = pd.to_numeric(df[self.SERIES_CODE], errors='coerce')

            # 無効なデータを除去
            df = df.dropna(subset=['DATE', self.SERIES_CODE])

            # 日付でソート
            df = df.sort_values('DATE')

            # リスト形式に変換
            series_data = []
            for _, row in df.iterrows():
                try:
                    date_str = row['DATE'].strftime('%Y-%m-%d')
                    value = float(row[self.SERIES_CODE])

                    series_data.append({
                        "date": date_str,
                        "value": value
                    })
                except Exception as e:
                    print(f"[BOEBankRate] Error processing row: {e}")
                    continue

            if not series_data:
                print("[BOEBankRate] No valid data points")
                return None

            latest = series_data[-1] if series_data else None

            print(f"[BOEBankRate] Processed {len(series_data)} data points, latest: {latest}")

            return {
                "data": series_data,
                "latest": latest,
            }

        except Exception as e:
            print(f"[BOEBankRate] Error processing CSV: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """
        キャッシュを更新すべきかどうかを判定

        ロジック:
        - 7日以上経過していれば更新
        - MPC発表日付近（12-20日）の12:00-13:00 UTCは5分ごとにチェック
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)
            hours_since_update = (now - last_updated).total_seconds() / 3600

            # 7日以上経過していれば更新
            if hours_since_update >= 24 * 7:
                return True

            # MPC発表日付近のチェック（12-20日）
            now_london = now.astimezone(LONDON)
            if 12 <= now_london.day <= 20:
                # 12:00-13:00 ロンドン時間
                if 12 <= now_london.hour <= 13:
                    # 5分以上経過していれば更新
                    if (now - last_updated).total_seconds() >= 300:
                        print("[BOEBankRate] MPC announcement window, checking for update")
                        return True

            return False

        except Exception as e:
            print(f"[BOEBankRate] Error in should_refresh: {e}")
            return True

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[BOEBankRate] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[BOEBankRate] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "BOE Bank Rate",
            "source": "Bank of England",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
boe_bank_rate_service = BOEBankRateService()
