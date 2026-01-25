"""
SONIA（Sterling Overnight Index Average）サービス
Bank of England公式データベースからSONIAデータを取得

指標:
- SONIA金利 (IUDSOIA)
- 英国のオーバーナイト金利ベンチマーク

データソース:
- BOE Statistical Database
- https://www.bankofengland.co.uk/boeapps/database/

発表スケジュール:
- 日次
- ロンドン9:00（夏時間: 17:00 JST、冬時間: 18:00 JST）

キャッシュ方式: 日次更新（翌営業日9:00ロンドン時間でリフレッシュ）
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
DATA_CACHE_FILE = CACHE_DIR / "sonia_cache.json"


class SONIAService:
    """SONIA（Sterling Overnight Index Average）サービス"""

    DATA_CACHE_KEY = "uk:sonia:data"

    # BOE Statistical Database API
    BOE_API_URL = "https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp"
    # SONIA series code
    SERIES_CODE = "IUDSOIA"

    def __init__(self):
        pass

    def get_sonia_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """SONIAデータを取得"""
        # 次回発表日を計算
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

        # BOE公式データベースから取得
        api_result = self._fetch_from_boe()

        if api_result:
            cache_payload = {
                "data": api_result.get("data", []),
                "latest": api_result.get("latest"),
                "metadata": {
                    "source": "Bank of England",
                    "indicator": "SONIA",
                    "series_code": self.SERIES_CODE,
                    "description": "Sterling Overnight Index Average - 英国のオーバーナイト金利ベンチマーク",
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
        """BOE公式データベースからデータを取得"""
        try:
            print(f"[SONIA] Fetching from BOE database (series: {self.SERIES_CODE})")

            params = {
                'csv.x': 'yes',
                'Datefrom': '01/Jan/2018',  # SONIA改革後から
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

            print(f"[SONIA] Received {len(response.text)} bytes")

            return self._process_boe_csv(response.text)

        except requests.exceptions.RequestException as e:
            print(f"[SONIA] Request error: {e}")
            return None
        except Exception as e:
            print(f"[SONIA] Error fetching from BOE: {e}")
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
                print("[SONIA] Could not find data section in CSV")
                return None

            # データセクションをパース
            data_csv = '\n'.join(lines[data_start_idx:])
            df = pd.read_csv(StringIO(data_csv))

            print(f"[SONIA] Parsed CSV: {len(df)} rows")

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
                    print(f"[SONIA] Error processing row: {e}")
                    continue

            if not series_data:
                print("[SONIA] No valid data points")
                return None

            latest = series_data[-1] if series_data else None

            print(f"[SONIA] Processed {len(series_data)} data points, latest: {latest}")

            return {
                "data": series_data,
                "latest": latest,
            }

        except Exception as e:
            print(f"[SONIA] Error processing CSV: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """
        キャッシュを更新すべきかどうかを判定

        ロジック:
        - ロンドン9:00以降で、前回更新が前日以前なら更新
        - 日次データなので、毎日9:00（ロンドン時間）以降にリフレッシュ
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)
            now_london = now.astimezone(LONDON)

            # 今日のロンドン9:00を計算
            today_9am_london = now_london.replace(hour=9, minute=0, second=0, microsecond=0)

            # 現在ロンドン9:00以降か
            if now_london >= today_9am_london:
                # 最終更新がロンドン9:00以前なら更新
                last_updated_london = last_updated.astimezone(LONDON)
                if last_updated_london < today_9am_london:
                    print("[SONIA] Daily refresh needed (after 9:00 London time)")
                    return True

            # 24時間以上経過していれば更新
            hours_since_update = (now - last_updated).total_seconds() / 3600
            if hours_since_update >= 24:
                return True

            return False

        except Exception as e:
            print(f"[SONIA] Error in should_refresh: {e}")
            return True

    def _calculate_next_release(self) -> Optional[Dict[str, Any]]:
        """次回発表日を計算"""
        try:
            now = datetime.now(LONDON)

            # 今日のロンドン9:00
            today_9am = now.replace(hour=9, minute=0, second=0, microsecond=0)

            # 現在9:00以降なら翌営業日、そうでなければ今日
            if now >= today_9am:
                next_date = now + timedelta(days=1)
            else:
                next_date = now

            # 週末をスキップ
            while next_date.weekday() >= 5:  # 土曜=5, 日曜=6
                next_date += timedelta(days=1)

            next_release = next_date.replace(hour=9, minute=0, second=0, microsecond=0)

            # 夏時間かどうかで日本時間を調整
            next_release_jst = next_release.astimezone(JST)

            return {
                "date": next_release.strftime("%Y-%m-%d"),
                "time_london": "09:00",
                "time_jst": next_release_jst.strftime("%H:%M"),
                "datetime_jst": next_release_jst.isoformat()
            }

        except Exception as e:
            print(f"[SONIA] Error calculating next release: {e}")
            return None

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[SONIA] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[SONIA] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "SONIA",
            "source": "Bank of England",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": self._calculate_next_release(),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
sonia_service = SONIAService()
