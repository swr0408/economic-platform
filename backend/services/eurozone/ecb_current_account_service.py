"""
ECB 経常収支サービス
ECB SDWからユーロ圏経常収支データを取得（XLSダウンロード方式）

指標:
- Current Account Balance (経常収支)

データソース:
- ECB Statistical Data Warehouse (SDW) - XLSダウンロード
  - BPS.M.I9.N.CA.H.X1.T.N.EUR._Z._T._X._X.N.ALL
  - Balance of Payments (BPS)
  - M = Monthly
  - I9 = Euro area (changing composition)
  - N = Net
  - CA = Current account
  - H = EUR (millions)
  - X1 = Not working day and seasonally adjusted
  - N = NSA
- FMP（次回発表日時のみ）

発表スケジュール:
- FMPカレンダーから取得（Current Accountイベント）

キャッシュ方式: FMP発表日時ベース判定方式
"""
import json
import requests
import io
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client
from services.eurozone.fmp_next_release_utils import (
    get_next_release_from_fmp,
    should_refresh_by_fmp_schedule,
)


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
CET = ZoneInfo("Europe/Berlin")

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "eurozone" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ecb_current_account_cache.json"


class ECBCurrentAccountService:
    """ECB 経常収支サービス（XLSダウンロード方式）"""

    # ECB SDW XLSダウンロードURL
    # BPS.M.I9.N.CA.H.X1.T.N.EUR._Z._T._X._X.N.ALL
    ECB_SDW_XLS_URL = "https://sdw.ecb.europa.eu/quickviewexport.do"
    SERIES_KEY = "BPS.M.I9.N.CA.H.X1.T.N.EUR._Z._T._X._X.N.ALL"

    DATA_CACHE_KEY = "economy:ecb_current_account:data"
    ECONALPHA_ID = "eu_current_account_balance"

    def __init__(self):
        pass

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """経常収支データを取得"""
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    next_release = get_next_release_from_fmp(self.ECONALPHA_ID)
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

            # ファイルキャッシュもチェック
            file_cache = self._load_file_cache()
            if file_cache:
                last_updated_str = file_cache.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    next_release = get_next_release_from_fmp(self.ECONALPHA_ID)
                    return {
                        "data": file_cache.get("data", []),
                        "latest": file_cache.get("latest"),
                        "metadata": file_cache.get("metadata", {}),
                        "next_release": next_release,
                        "cached": True,
                        "source": "file",
                        "last_updated": last_updated_str,
                    }

        # ECB SDW XLSから取得
        current_account_data = self._fetch_from_xls() or []

        if current_account_data:
            latest = current_account_data[-1] if current_account_data else None
            next_release = get_next_release_from_fmp(self.ECONALPHA_ID)

            cache_payload = {
                "data": current_account_data,
                "latest": latest,
                "metadata": {
                    "source": "European Central Bank (ECB) - Balance of Payments",
                    "dataset": "BPS",
                    "area": "Euro area (changing composition)",
                    "unit": "Billions of euro",
                    "frequency": "Monthly",
                    "description": "Current account balance (経常収支)",
                },
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": current_account_data,
                "latest": latest,
                "metadata": cache_payload["metadata"],
                "next_release": next_release,
                "cached": False,
                "source": "ecb_sdw_xls",
                "last_updated": datetime.now(JST).isoformat(),
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            next_release = get_next_release_from_fmp(self.ECONALPHA_ID)
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
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _fetch_from_xls(self, start_date: str = "2015-01-01") -> Optional[List[Dict]]:
        """ECB SDWからXLSをダウンロードしてデータを取得"""
        try:
            import pandas as pd

            params = {
                "SERIES_KEY": self.SERIES_KEY,
                "type": "xls"
            }

            print(f"[ECB CurrentAccount] Fetching XLS from ECB SDW: {self.ECB_SDW_XLS_URL}")
            response = requests.get(self.ECB_SDW_XLS_URL, params=params, timeout=60)
            response.raise_for_status()

            # XLSをパース
            df = pd.read_excel(io.BytesIO(response.content), engine='xlrd')

            print(f"[ECB CurrentAccount] XLS shape: {df.shape}")
            print(f"[ECB CurrentAccount] XLS columns: {df.columns.tolist()}")

            # ECB SDW XLSの構造:
            # 通常、最初の列が日付（YYYY-MM または期間）、2列目以降がデータ
            # ヘッダー行を確認してデータを抽出

            result = []

            # カラム名を確認
            cols = df.columns.tolist()

            # 日付列とデータ列を特定
            date_col = None
            value_col = None

            for col in cols:
                col_str = str(col).lower()
                if 'date' in col_str or 'period' in col_str or 'time' in col_str:
                    date_col = col
                elif date_col is None and isinstance(col, str) and not col.startswith('Unnamed'):
                    # 最初の非空カラムを日付として扱う
                    date_col = col

            # value列は日付列の次の列、または特定のパターン
            if date_col is not None:
                date_col_idx = cols.index(date_col)
                if date_col_idx + 1 < len(cols):
                    value_col = cols[date_col_idx + 1]

            # 日付列が見つからない場合、最初の2列を使用
            if date_col is None:
                date_col = cols[0] if len(cols) > 0 else None
                value_col = cols[1] if len(cols) > 1 else None

            print(f"[ECB CurrentAccount] Using date_col={date_col}, value_col={value_col}")

            if date_col is None or value_col is None:
                print("[ECB CurrentAccount] Could not identify date and value columns")
                return self._fetch_from_api_fallback(start_date)

            # データ行を処理
            for idx, row in df.iterrows():
                try:
                    date_val = row[date_col]
                    value_val = row[value_col]

                    if pd.isna(date_val) or pd.isna(value_val):
                        continue

                    # 日付をパース
                    date_str = None
                    if isinstance(date_val, datetime):
                        date_str = date_val.strftime("%Y-%m-01")
                    elif isinstance(date_val, str):
                        # YYYY-MM形式
                        date_val = date_val.strip()
                        if len(date_val) == 7 and '-' in date_val:
                            date_str = f"{date_val}-01"
                        elif len(date_val) >= 10:
                            date_str = f"{date_val[:7]}-01"

                    if not date_str:
                        continue

                    # 期間フィルタリング
                    if date_str < start_date:
                        continue

                    # 値をパース（百万ユーロ → 10億ユーロ）
                    try:
                        value = float(value_val)
                        result.append({
                            "date": date_str,
                            "value": round(value / 1000, 2)  # 百万ユーロ→10億ユーロ
                        })
                    except (ValueError, TypeError):
                        continue

                except Exception as row_error:
                    print(f"[ECB CurrentAccount] Error processing row {idx}: {row_error}")
                    continue

            result.sort(key=lambda x: x["date"])
            print(f"[ECB CurrentAccount] Fetched {len(result)} data points from XLS")

            if len(result) == 0:
                print("[ECB CurrentAccount] No data from XLS, trying API fallback")
                return self._fetch_from_api_fallback(start_date)

            return result

        except Exception as e:
            print(f"[ECB CurrentAccount] Error fetching XLS: {e}")
            import traceback
            traceback.print_exc()
            return self._fetch_from_api_fallback(start_date)

    def _fetch_from_api_fallback(self, start_date: str = "2015-01-01") -> Optional[List[Dict]]:
        """ECB Data APIからデータを取得（フォールバック）

        注: 旧 SDW ホスト sdw.ecb.europa.eu は廃止 (DNS解決不可) のため、
        実質このAPIフォールバックが主経路。新 Data Portal の BPS dataflow は
        次元順が変わっており (FREQ.ADJUSTMENT.REF_AREA.COUNTERPART_AREA.
        REF_SECTOR.COUNTERPART_SECTOR.FLOW_STOCK_ENTRY.ACCOUNTING_ENTRY.
        INT_ACC_ITEM. ... )、ユーロ圏(I9)・経常収支(CA)・残高(B)・月次(M)・
        非調整(N) の正しいキーは下記。旧キー (M.I9.N.CA.H.X1...) は 400 を返す。
        """
        # ECB Data Portal (新) のシリーズキー: 経常収支 残高 ユーロ圏 月次
        legacy_key = "M.N.I9.W1.S1.S1.T.B.CA._Z._Z._Z.EUR._T._X.N.ALL"
        url = f"https://data-api.ecb.europa.eu/service/data/BPS/{legacy_key}"
        params = {
            "startPeriod": start_date[:7],  # YYYY-MM形式
            "format": "jsondata"
        }

        try:
            print(f"[ECB CurrentAccount] Fetching (API fallback): {url}")
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            if "dataSets" not in data or len(data["dataSets"]) == 0:
                print(f"[ECB CurrentAccount] No data sets found")
                return None

            dataset = data["dataSets"][0]
            if "series" not in dataset:
                print(f"[ECB CurrentAccount] No series found")
                return None

            series_data = list(dataset["series"].values())[0]
            observations = series_data.get("observations", {})

            dimensions = data.get("structure", {}).get("dimensions", {}).get("observation", [])
            time_dimension = None
            for dim in dimensions:
                if dim.get("id") == "TIME_PERIOD":
                    time_dimension = dim
                    break

            if not time_dimension:
                print(f"[ECB CurrentAccount] No time dimension found")
                return None

            time_values = time_dimension.get("values", [])

            result = []
            for obs_key, obs_value in observations.items():
                time_index = int(obs_key)
                if time_index < len(time_values):
                    date_id = time_values[time_index].get("id")
                    value = obs_value[0] if isinstance(obs_value, list) and len(obs_value) > 0 else obs_value

                    if value is not None and date_id:
                        # YYYY-MM形式を YYYY-MM-01形式に変換
                        date_str = f"{date_id}-01" if len(date_id) == 7 else date_id
                        result.append({
                            "date": date_str,
                            "value": round(float(value) / 1000, 2)  # 百万ユーロ→10億ユーロ
                        })

            result.sort(key=lambda x: x["date"])
            print(f"[ECB CurrentAccount] Fetched {len(result)} data points (API fallback)")
            return result

        except requests.exceptions.RequestException as e:
            print(f"[ECB CurrentAccount] API fallback request error: {e}")
            return None
        except (KeyError, ValueError, IndexError) as e:
            print(f"[ECB CurrentAccount] API fallback parse error: {e}")
            return None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（FMP発表日時ベース）"""
        return should_refresh_by_fmp_schedule(self.ECONALPHA_ID, last_updated_str, max_age_hours=72)

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
            "indicator": "ECB Current Account Balance",
            "source": "ECB SDW (XLS)",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
ecb_current_account_service = ECBCurrentAccountService()
