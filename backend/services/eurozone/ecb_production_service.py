"""
ユーロ圏鉱工業生産サービス
Eurostat APIからユーロ圏鉱工業生産データを取得

指標:
- 鉱工業生産指数（季節調整なし）: MoM計算用
- 鉱工業生産指数（営業日調整）: チャート表示用

Eurostatデータセット: sts_inpr_m (Short-term business statistics - Industrial production)
- EA = Euro Area (19/20 countries)
- I = Index
- SCA = Seasonally and calendar adjusted
- NSA = Not seasonally adjusted
- B-D = Industry (except construction)

発表スケジュール:
- 毎月12日〜20日頃

キャッシュ方式: 日次更新
"""
import json
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
CET = ZoneInfo("Europe/Berlin")

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "eurozone" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ecb_production_cache.json"


class ECBProductionService:
    """ユーロ圏鉱工業生産サービス（Eurostat API使用）"""

    # Eurostat API
    EUROSTAT_API_BASE = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"
    DATASET = "sts_inpr_m"

    DATA_CACHE_KEY = "economy:ecb_production:data"

    def __init__(self):
        pass

    def _fetch_eurostat_data(self, s_adj: str, start_date: str = "2015-01") -> Optional[List[Dict]]:
        """
        Eurostat APIから鉱工業生産データを取得

        Args:
            s_adj: 季節調整 ("SCA" = 季節・営業日調整, "NSA" = 調整なし)
            start_date: データ開始年月 (YYYY-MM形式)
        """
        url = f"{self.EUROSTAT_API_BASE}/{self.DATASET}"

        params = {
            "format": "JSON",
            "lang": "en",
            "geo": "EA20",         # Euro Area (20 countries)
            "unit": "I21",         # Index, 2021=100
            "s_adj": s_adj,        # Seasonal adjustment
            "nace_r2": "B-D",      # Industry (except construction)
            "sinceTimePeriod": start_date
        }

        try:
            print(f"[Eurostat Production] Fetching: {url} with s_adj={s_adj}")
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            # JSON-stat形式をパース
            result = self._parse_jsonstat(data)
            print(f"[Eurostat Production] Fetched {len(result)} data points for s_adj={s_adj}")
            return result

        except requests.exceptions.RequestException as e:
            print(f"[Eurostat Production] Request error: {e}")
            return None
        except (KeyError, ValueError, IndexError) as e:
            print(f"[Eurostat Production] Parse error: {e}")
            return None

    def _parse_jsonstat(self, data: Dict) -> List[Dict]:
        """JSON-stat形式のデータをパース"""
        result = []

        try:
            # 時間次元のインデックスを取得
            time_dimension = data.get("dimension", {}).get("time", {})
            time_category = time_dimension.get("category", {})
            time_index = time_category.get("index", {})
            time_labels = time_category.get("label", {})

            # 値の配列を取得
            values = data.get("value", {})

            # サイズ情報を取得（次元の順序を確認）
            dimension_ids = data.get("id", [])
            dimension_sizes = data.get("size", [])

            # time次元のインデックス位置を特定
            time_dim_pos = dimension_ids.index("time") if "time" in dimension_ids else -1
            if time_dim_pos == -1:
                print("[Eurostat Production] Time dimension not found")
                return []

            # 各次元のサイズを取得して、time以外は0（単一値）と仮定
            # 値のインデックス計算用
            multiplier = 1
            for i in range(len(dimension_sizes) - 1, time_dim_pos, -1):
                multiplier *= dimension_sizes[i]

            # 時間ごとにデータを抽出
            for time_key, time_idx in time_index.items():
                # 値のインデックスを計算
                value_idx = str(time_idx)
                if value_idx in values:
                    value = values[value_idx]
                    if value is not None:
                        # YYYY-MM形式を維持
                        result.append({
                            "date": time_key,
                            "value": float(value)
                        })

            # 日付でソート
            result.sort(key=lambda x: x["date"])

        except Exception as e:
            print(f"[Eurostat Production] JSON-stat parse error: {e}")
            import traceback
            traceback.print_exc()

        return result

    def _calculate_mom_change(self, data: List[Dict]) -> List[Dict]:
        """前月比を計算"""
        if not data or len(data) < 2:
            return []

        result = []
        for i in range(1, len(data)):
            current = data[i]
            previous = data[i - 1]

            if current['value'] is not None and previous['value'] is not None and previous['value'] != 0:
                mom_change = ((current['value'] - previous['value']) / previous['value']) * 100
                result.append({
                    'date': current['date'],
                    'value': round(mom_change, 2),
                    'current_index': round(current['value'], 2),
                    'previous_index': round(previous['value'], 2)
                })

        return result

    def _calculate_yoy_change(self, data: List[Dict]) -> List[Dict]:
        """前年比を計算"""
        if not data or len(data) < 13:
            return []

        result = []
        for i in range(12, len(data)):
            current = data[i]
            previous_year = data[i - 12]

            if current['value'] is not None and previous_year['value'] is not None and previous_year['value'] != 0:
                yoy_change = ((current['value'] - previous_year['value']) / previous_year['value']) * 100
                result.append({
                    'date': current['date'],
                    'value': round(yoy_change, 2)
                })

        return result

    def get_ecb_production_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """鉱工業生産データを取得"""
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "production_wda": cached_data.get("production_wda", []),
                        "mom_change": cached_data.get("mom_change", []),
                        "yoy_change": cached_data.get("yoy_change", []),
                        "metadata": cached_data.get("metadata", {}),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # Eurostat APIからデータ取得
        # SCA = Seasonally and Calendar Adjusted（チャート表示・変化率計算用）
        # Note: EA20のNSAデータは利用不可のため、SCAを使用
        production_sca = self._fetch_eurostat_data("SCA") or []

        # 変化率を計算（季節調整済みデータを使用）
        mom_change = self._calculate_mom_change(production_sca)
        yoy_change = self._calculate_yoy_change(production_sca)

        has_data = len(production_sca) > 0 or len(mom_change) > 0 or len(yoy_change) > 0

        if has_data:
            metadata = {
                "last_updated": datetime.now(JST).isoformat(),
                "source": "Eurostat - Short-term business statistics",
                "dataset": self.DATASET,
                "data_start": "2015-01",
                "unit_index": "Index 2021=100",
                "unit_mom": "Month-on-month change (%)",
                "unit_yoy": "Year-on-year change (%)",
                "frequency": "Monthly",
                "adjustment_nsa": "Not seasonally adjusted",
                "adjustment_sca": "Seasonally and calendar adjusted"
            }

            cache_payload = {
                "production_wda": production_sca,  # 互換性のためproduction_wdaを維持
                "mom_change": mom_change,
                "yoy_change": yoy_change,
                "metadata": metadata,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "production_wda": production_sca,
                "mom_change": mom_change,
                "yoy_change": yoy_change,
                "metadata": metadata,
                "cached": False,
                "source": "eurostat_api",
                "last_updated": datetime.now(JST).isoformat()
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "production_wda": file_cache.get("production_wda", []),
                "mom_change": file_cache.get("mom_change", []),
                "yoy_change": file_cache.get("yoy_change", []),
                "metadata": file_cache.get("metadata", {}),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "production_wda": [],
            "mom_change": [],
            "yoy_change": [],
            "metadata": {},
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)

            # 24時間以上経過していれば更新
            if (now - last_updated) > timedelta(hours=24):
                return True

            return False
        except Exception:
            return True

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
            "indicator": "ECB Production",
            "source": "Eurostat API",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "production_wda_count": len(cached_data.get("production_wda", [])) if cached_data else 0,
            "mom_change_count": len(cached_data.get("mom_change", [])) if cached_data else 0,
            "yoy_change_count": len(cached_data.get("yoy_change", [])) if cached_data else 0,
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
ecb_production_service = ECBProductionService()
