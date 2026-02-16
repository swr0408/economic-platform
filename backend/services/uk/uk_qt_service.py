"""
UK QT（量的引締め）サービス
Bank of England IADB APIからAPFギルト保有残高データを取得

指標:
- APF Gilt Holdings (initial purchase proceeds, GBP millions)
- Series: YWWB9T9

データソース:
- BOE Statistical Interactive Database (IADB)
- https://www.bankofengland.co.uk/boeapps/database/

発表スケジュール:
- 週次（毎週木曜 15:00 London時間）
- APFオペレーション実施後またはギルト満期後に更新

キャッシュ方式: 木曜15:00 London時間ベース判定
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
DATA_CACHE_FILE = CACHE_DIR / "uk_qt_cache.json"


class UKQTService:
    """UK QT（APFギルト保有残高）サービス"""

    DATA_CACHE_KEY = "uk:uk_qt:data"

    # BOE Statistical Database API
    BOE_API_URL = "https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp"
    # APF gilt holdings series code (weekly, GBP millions, initial purchase proceeds)
    SERIES_CODE = "YWWB9T9"

    def __init__(self):
        pass

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """UK QTデータを取得"""
        next_release = self._calculate_next_release()

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
                        "metadata": file_cache.get("metadata", {}),
                        "next_release": next_release,
                        "cached": True,
                        "source": "file",
                        "last_updated": last_updated_str,
                    }

        # BOE APIから取得
        api_result = self._fetch_from_boe()

        if api_result:
            cache_payload = {
                "data": api_result.get("data", []),
                "latest": api_result.get("latest"),
                "metadata": {
                    "source": "Bank of England",
                    "indicator": "APF Gilt Holdings",
                    "series_code": self.SERIES_CODE,
                    "unit": "GBP millions",
                    "frequency": "Weekly",
                    "description": "Asset Purchase Facility gilt holdings (initial purchase proceeds)",
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

    def _fetch_from_boe(self) -> Optional[Dict[str, Any]]:
        """BOE IADBからAPFギルト保有残高データを取得"""
        try:
            print(f"[UK QT] Fetching from BOE database (series: {self.SERIES_CODE})")

            params = {
                'csv.x': 'yes',
                'Datefrom': '01/Jan/2009',
                'Dateto': 'now',
                'SeriesCodes': self.SERIES_CODE,
                'UsingCodes': 'Y',
                'CSVF': 'TT',
                'VPD': 'Y',
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

            print(f"[UK QT] Received {len(response.text)} bytes")

            return self._process_boe_csv(response.text)

        except requests.exceptions.RequestException as e:
            print(f"[UK QT] Request error: {e}")
            return None
        except Exception as e:
            print(f"[UK QT] Error fetching from BOE: {e}")
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
                print("[UK QT] Could not find data section in CSV")
                return None

            # データセクションをパース
            data_csv = '\n'.join(lines[data_start_idx:])
            df = pd.read_csv(StringIO(data_csv))

            print(f"[UK QT] Parsed CSV: {len(df)} rows")

            # 日付と値を処理
            df['DATE'] = pd.to_datetime(df['DATE'], format='%d %b %Y', errors='coerce')
            df[self.SERIES_CODE] = pd.to_numeric(df[self.SERIES_CODE], errors='coerce')

            # 無効なデータを除去
            df = df.dropna(subset=['DATE', self.SERIES_CODE])

            # 日付でソート
            df = df.sort_values('DATE')

            # リスト形式に変換（GBP millions → GBP billions）
            series_data = []
            for _, row in df.iterrows():
                try:
                    date_str = row['DATE'].strftime('%Y-%m-%d')
                    value_millions = float(row[self.SERIES_CODE])
                    value_billions = round(value_millions / 1000, 2)

                    series_data.append({
                        "date": date_str,
                        "value": value_billions,
                    })
                except Exception as e:
                    print(f"[UK QT] Error processing row: {e}")
                    continue

            if not series_data:
                print("[UK QT] No valid data points")
                return None

            latest = series_data[-1] if series_data else None

            print(f"[UK QT] Processed {len(series_data)} data points, latest: {latest}")

            return {
                "data": series_data,
                "latest": latest,
            }

        except Exception as e:
            print(f"[UK QT] Error processing CSV: {e}")
            return None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """
        キャッシュを更新すべきかどうかを判定

        木曜15:00 London時間以降で、前回更新が木曜15:00以前なら更新
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)
            now_london = now.astimezone(LONDON)

            # 直近の木曜15:00 Londonを計算
            days_since_thursday = (now_london.weekday() - 3) % 7
            last_thursday = now_london - timedelta(days=days_since_thursday)
            last_thursday_3pm = last_thursday.replace(hour=15, minute=0, second=0, microsecond=0)

            # 今が木曜15:00以降で、last_updatedが木曜15:00以前なら更新
            if now_london >= last_thursday_3pm:
                last_updated_london = last_updated.astimezone(LONDON)
                if last_updated_london < last_thursday_3pm:
                    print("[UK QT] Weekly refresh needed (after Thursday 15:00 London)")
                    return True

            # 7日以上経過なら更新
            if (now - last_updated).total_seconds() > 604800:
                return True

            return False

        except Exception:
            return True

    def _calculate_next_release(self) -> Optional[Dict[str, Any]]:
        """次回発表日（次の木曜15:00 London）を計算"""
        try:
            now = datetime.now(LONDON)

            # 今日の木曜15:00
            today_3pm = now.replace(hour=15, minute=0, second=0, microsecond=0)

            # 今日が木曜で15:00前なら今日
            if now.weekday() == 3 and now < today_3pm:
                next_thursday = now
            else:
                # 次の木曜を計算
                days_until_thursday = (3 - now.weekday()) % 7
                if days_until_thursday == 0:
                    days_until_thursday = 7  # 今日が木曜15:00以降なら来週
                next_thursday = now + timedelta(days=days_until_thursday)

            next_release = next_thursday.replace(hour=15, minute=0, second=0, microsecond=0)
            next_release_jst = next_release.astimezone(JST)

            return {
                "date": next_release.strftime("%Y-%m-%d"),
                "time_london": "15:00",
                "time_jst": next_release_jst.strftime("%H:%M"),
                "datetime_jst": next_release_jst.isoformat(),
            }

        except Exception as e:
            print(f"[UK QT] Error calculating next release: {e}")
            return None

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[UK QT] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[UK QT] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "UK QT (APF Gilt Holdings)",
            "source": "Bank of England IADB",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": self._calculate_next_release(),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
uk_qt_service = UKQTService()
