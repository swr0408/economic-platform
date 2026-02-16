"""
EU政府債務残高対GDP比サービス
Eurostat APIからユーロ圏（国別）の政府債務残高対GDP比データを取得

指標:
- gov_10q_ggdebt: Quarterly government debt (% of GDP)
- unit=PC_GDP, na_item=GD, sector=S13

データソース:
- Eurostat Statistics API (JSON-stat 2.0)
- https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/gov_10q_ggdebt

国別: EA20(ユーロ圏), DE(ドイツ), FR(フランス), IT(イタリア),
      ES(スペイン), EL(ギリシャ)

発表スケジュール:
- 四半期（Q+約113日後）
- API extension.annotation の DISSEMINATION_TIMESTAMP_PLANNED から次回発表日を取得

キャッシュ方式: Redis + ファイルキャッシュ（7日更新）
"""
import json
import requests
from datetime import datetime
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client

# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
CET = ZoneInfo("Europe/Berlin")

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "eurozone" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "eu_government_debt_to_gdp_ratio_cache.json"

# 取得対象の国コード（Eurostat geo codes）
# 注意: ギリシャは "EL"（"GR" ではない）
GEO_CODES = {
    "ea20": {"code": "EA20", "label": "ユーロ圏"},
    "de": {"code": "DE", "label": "ドイツ"},
    "fr": {"code": "FR", "label": "フランス"},
    "it": {"code": "IT", "label": "イタリア"},
    "es": {"code": "ES", "label": "スペイン"},
    "el": {"code": "EL", "label": "ギリシャ"},
}

# 四半期→月番号マッピング（四半期末の月）
QUARTER_MONTH_MAP = {"Q1": 3, "Q2": 6, "Q3": 9, "Q4": 12}


class EUGovernmentDebtToGdpRatioService:
    """EU政府債務残高対GDP比サービス"""

    EUROSTAT_API_BASE = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"
    DATASET = "gov_10q_ggdebt"

    DATA_CACHE_KEY = "economy:eu_government_debt_to_gdp_ratio:data"

    def __init__(self):
        pass

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """EU政府債務残高対GDP比データを取得"""
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return self._build_response(cached_data, cached=True, source="redis")

        # ファイルキャッシュチェック
        if not force_refresh:
            file_cache = self._load_file_cache()
            if file_cache:
                last_updated_str = file_cache.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    redis_client.set(self.DATA_CACHE_KEY, file_cache, expire=0)
                    return self._build_response(file_cache, cached=True, source="file")

        # Eurostat APIからデータを取得
        api_result = self._fetch_from_eurostat()

        if api_result:
            cache_payload = {
                **api_result,
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return self._build_response(cache_payload, cached=False, source="eurostat_api")

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return self._build_response(file_cache, cached=True, source="file (fallback)")

        return {
            "countries": {},
            "ea20": [],
            "latest": None,
            "metadata": {},
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _build_response(self, data: Dict, cached: bool, source: str) -> Dict[str, Any]:
        """レスポンスを構築"""
        return {
            "countries": data.get("countries", {}),
            "ea20": data.get("ea20", []),
            "latest": data.get("latest"),
            "metadata": data.get("metadata", {}),
            "next_release": data.get("next_release"),
            "cached": cached,
            "source": source,
            "last_updated": data.get("last_updated"),
        }

    def _fetch_from_eurostat(self) -> Optional[Dict[str, Any]]:
        """Eurostat Statistics APIからデータを取得"""
        try:
            url = f"{self.EUROSTAT_API_BASE}/{self.DATASET}"

            # 全対象国のgeoパラメータを構築
            geo_values = [info["code"] for info in GEO_CODES.values()]

            params = {
                "format": "JSON",
                "lang": "en",
                "unit": "PC_GDP",
                "na_item": "GD",
                "sector": "S13",
                "sinceTimePeriod": "2000-Q1",
            }

            # geoは複数指定（requestsでlistを渡すと自動的に &geo=EA20&geo=DE&... になる）
            params_list = list(params.items()) + [("geo", g) for g in geo_values]

            print(f"[EU Govt Debt/GDP] Fetching from Eurostat API: {url}")
            response = requests.get(url, params=params_list, timeout=30)
            response.raise_for_status()

            data = response.json()
            print(f"[EU Govt Debt/GDP] Received JSON-stat data")

            return self._parse_jsonstat_multi_geo(data)

        except requests.exceptions.RequestException as e:
            print(f"[EU Govt Debt/GDP] Request error: {e}")
            return None
        except Exception as e:
            print(f"[EU Govt Debt/GDP] Error fetching from Eurostat: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _parse_jsonstat_multi_geo(self, data: Dict) -> Optional[Dict[str, Any]]:
        """JSON-stat形式のマルチgeoデータをパース"""
        try:
            dimension_ids = data.get("id", [])
            dimension_sizes = data.get("size", [])
            values = data.get("value", {})

            # geo次元とtime次元のインデックスを取得
            geo_dim = data.get("dimension", {}).get("geo", {})
            time_dim = data.get("dimension", {}).get("time", {})

            geo_index = geo_dim.get("category", {}).get("index", {})
            geo_labels = geo_dim.get("category", {}).get("label", {})
            time_index = time_dim.get("category", {}).get("index", {})

            if not geo_index or not time_index:
                print("[EU Govt Debt/GDP] Missing geo or time dimension")
                return None

            num_times = len(time_index)

            # geo_idxとtime_idxからflat indexを計算
            # dimensions: [freq, na_item, sector, unit, geo, time]
            # sizes: [1, 1, 1, 1, num_geos, num_times]
            # flat_index = geo_idx * num_times + time_idx

            # 国別にデータを格納
            countries = {}
            for geo_key, geo_idx in geo_index.items():
                geo_key_lower = geo_key.lower()

                # GEO_CODESに含まれる国のみ処理
                matching_key = None
                for key, info in GEO_CODES.items():
                    if info["code"] == geo_key:
                        matching_key = key
                        break
                if matching_key is None:
                    continue

                country_data = []
                for time_key, time_idx in time_index.items():
                    flat_idx = str(geo_idx * num_times + time_idx)
                    if flat_idx in values:
                        value = values[flat_idx]
                        if value is not None:
                            # YYYY-QN → YYYY-MM-01 に変換
                            date_str = self._quarter_to_date(time_key)
                            if date_str:
                                country_data.append({
                                    "date": date_str,
                                    "value": round(float(value), 1),
                                    "quarter": time_key,
                                })

                country_data.sort(key=lambda x: x["date"])
                countries[matching_key] = country_data

            # EA20のデータをメインデータとして使用
            ea20_data = countries.get("ea20", [])

            # QoQ変化幅（ユーロ圏全体）
            qoq_change_data = []
            for i in range(1, len(ea20_data)):
                current = ea20_data[i]
                prev = ea20_data[i - 1]
                change = round(current["value"] - prev["value"], 1)
                qoq_change_data.append({
                    "date": current["date"],
                    "value": change,
                    "quarter": current.get("quarter", ""),
                })

            latest = ea20_data[-1] if ea20_data else None

            # メタデータ
            metadata = {
                "title": data.get("label", "Quarterly government debt (% of GDP)"),
                "source": "Eurostat",
                "dataset": self.DATASET,
                "unit": "% of GDP",
                "description": "General government consolidated gross debt as a percentage of GDP",
                "updated": data.get("updated", ""),
            }

            # 次回発表日をannotationから取得
            next_release = self._extract_next_release(data)

            print(f"[EU Govt Debt/GDP] Processed {len(countries)} countries, EA20: {len(ea20_data)} quarters, latest: {latest}")

            return {
                "countries": countries,
                "ea20": ea20_data,
                "qoq_change": qoq_change_data,
                "latest": latest,
                "metadata": metadata,
                "next_release": next_release,
            }

        except Exception as e:
            print(f"[EU Govt Debt/GDP] Error parsing JSON-stat: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _quarter_to_date(self, quarter_str: str) -> Optional[str]:
        """四半期文字列をYYYY-MM-01形式に変換 (例: '2025-Q3' → '2025-09-01')"""
        try:
            parts = quarter_str.split("-")
            if len(parts) != 2:
                return None
            year = int(parts[0])
            quarter = parts[1].upper()
            month = QUARTER_MONTH_MAP.get(quarter)
            if not month:
                return None
            return f"{year}-{month:02d}-01"
        except (ValueError, IndexError):
            return None

    def _extract_next_release(self, data: Dict) -> Optional[Dict[str, Any]]:
        """API extensionのannotationから次回発表日を取得"""
        try:
            annotations = data.get("extension", {}).get("annotation", [])
            for ann in annotations:
                if ann.get("type") == "DISSEMINATION_TIMESTAMP_PLANNED":
                    date_str = ann.get("date", "")
                    if date_str:
                        # "2026-01-22T11:00:00+0100" 形式をパース
                        # Python 3.7+のfromisoformatは+0100形式非対応の場合があるので手動パース
                        release_dt = self._parse_eurostat_datetime(date_str)
                        if release_dt:
                            release_jst = release_dt.astimezone(JST)
                            return {
                                "date": release_dt.strftime("%Y-%m-%d"),
                                "datetime_jst": release_jst.isoformat(),
                                "time_jst": release_jst.strftime("%H:%M"),
                                "label": f"Eurostat Govt Debt ({release_dt.strftime('%b %Y')})",
                            }
        except Exception as e:
            print(f"[EU Govt Debt/GDP] Error extracting next release: {e}")

        return None

    def _parse_eurostat_datetime(self, date_str: str) -> Optional[datetime]:
        """Eurostatのdatetime文字列をパース（+0100形式対応）"""
        try:
            # "2026-01-22T11:00:00+0100" → datetime
            # fromisoformatは +01:00 は受け付けるが +0100 は受け付けない場合がある
            if len(date_str) > 19 and date_str[-5] in ('+', '-') and ':' not in date_str[-5:]:
                # +0100 → +01:00 に変換
                date_str = date_str[:-2] + ":" + date_str[-2:]
            return datetime.fromisoformat(date_str)
        except Exception:
            try:
                # フォールバック: タイムゾーンなしでパースしてCETを付与
                dt = datetime.fromisoformat(date_str[:19])
                return dt.replace(tzinfo=CET)
            except Exception:
                return None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)
            hours_since_update = (now - last_updated).total_seconds() / 3600

            # 7日以上経過していれば更新
            if hours_since_update >= 24 * 7:
                return True

            return False

        except Exception as e:
            print(f"[EU Govt Debt/GDP] Error in should_refresh: {e}")
            return True

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[EU Govt Debt/GDP] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[EU Govt Debt/GDP] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "EU Government Debt to GDP Ratio",
            "source": "Eurostat (gov_10q_ggdebt)",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("ea20", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
eu_government_debt_to_gdp_ratio_service = EUGovernmentDebtToGdpRatioService()
