"""
GDP構成要素サービス（e-Stat API）
民間最終消費支出・民間企業設備の前期比データを取得

データソース: e-Stat（内閣府）
統計データID: 0003113542（国内総生産・実質季節調整系列・成長率）

キャッシュ方式: FMP発表日時ベース判定方式
"""
import json
import logging
import os
import requests
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

try:
    from core.redis_client import redis_client
    from services.japan.fmp_next_release_utils import (
        get_next_release_from_fmp,
        should_refresh_by_fmp_schedule,
    )
except ImportError:
    from backend.core.redis_client import redis_client
    from backend.services.japan.fmp_next_release_utils import (
        get_next_release_from_fmp,
        should_refresh_by_fmp_schedule,
    )

logger = logging.getLogger(__name__)
JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "japan" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "gdp_components_cache.json"


class GDPComponentsService:
    """GDP構成要素サービス"""

    # e-Stat API設定
    ESTAT_API_URL = "http://api.e-stat.go.jp/rest/3.0/app/json/getStatsData"
    STATS_DATA_ID = "0003113542"  # 国内総生産（実質季節調整系列・成長率）

    # フィルタコード
    TAB_CODE_ZENKI = "14"  # 前期比

    # 構成要素コード
    CAT01_CODE_PRIVATE_CONSUMPTION = "12"  # 民間最終消費支出
    CAT01_CODE_PRIVATE_INVESTMENT = "16"  # 民間企業設備

    DATA_CACHE_KEY = "japan:gdp_components:data"
    ECONALPHA_ID = "japan_gdp_qoq"  # GDP発表と同じタイミング

    def __init__(self):
        self.api_key = os.getenv('ESTAT_API_KEY')
        if not self.api_key:
            logger.warning("ESTAT_API_KEY not found in environment variables")

    def _fetch_component_data(self, component_code: str, component_name: str) -> Optional[List[Dict]]:
        """
        特定のGDP構成要素データを取得

        Args:
            component_code: cat01コード
            component_name: 構成要素名（ログ用）

        Returns:
            データポイントのリスト
        """
        try:
            if not self.api_key:
                logger.error("e-Stat API key not configured")
                return None

            logger.info(f"Fetching {component_name} data from e-Stat API")

            params = {
                "appId": self.api_key,
                "lang": "J",
                "statsDataId": self.STATS_DATA_ID,
                "metaGetFlg": "Y",
                "cntGetFlg": "N",
                "explanationGetFlg": "Y",
                "annotationGetFlg": "Y",
                "sectionHeaderFlg": "1",
                "replaceSpChars": "0",
                "cdTab": self.TAB_CODE_ZENKI,
                "cdCat01": component_code,
            }

            response = requests.get(self.ESTAT_API_URL, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            if 'GET_STATS_DATA' not in data:
                logger.error("Invalid API response structure")
                return None

            stats_data = data['GET_STATS_DATA']

            if 'STATISTICAL_DATA' not in stats_data:
                logger.error("No statistical data in response")
                return None

            stat_data = stats_data['STATISTICAL_DATA']

            if 'DATA_INF' not in stat_data or 'VALUE' not in stat_data['DATA_INF']:
                logger.error("No data values in response")
                return None

            values = stat_data['DATA_INF']['VALUE']
            if not isinstance(values, list):
                values = [values]

            logger.info(f"Found {len(values)} raw data points for {component_name}")

            # 値の処理
            series_data = []
            for val in values:
                try:
                    time_code = val.get('@time', '')
                    if not time_code:
                        continue

                    # 時間コードを四半期形式にパース
                    year = int(time_code[:4])
                    month_range = time_code[4:]

                    # 月範囲を四半期にマッピング
                    if month_range == "000103":
                        quarter = "Q1"
                    elif month_range == "000406":
                        quarter = "Q2"
                    elif month_range == "000709":
                        quarter = "Q3"
                    elif month_range == "001012":
                        quarter = "Q4"
                    else:
                        continue

                    value_str = val.get('$', '')
                    if not value_str or value_str == '-':
                        continue

                    value_str = value_str.replace('%', '').strip()
                    try:
                        value = float(value_str)
                    except ValueError:
                        logger.debug(f"Could not convert value to float: {value_str}")
                        continue

                    date_str = f"{year}-{quarter}"

                    series_data.append({
                        "date": date_str,
                        "value": round(value, 2)
                    })

                except Exception as e:
                    logger.debug(f"Error processing value: {e}")
                    continue

            # 日付でソート
            series_data.sort(key=lambda x: (int(x["date"][:4]), x["date"][5:]))

            # 2000年以降のデータのみ
            if series_data:
                cutoff_date = "2000-Q1"
                series_data = [point for point in series_data if point["date"] >= cutoff_date]

            logger.info(f"Processed {component_name} data: {len(series_data)} data points")
            return series_data

        except requests.RequestException as e:
            logger.error(f"Error fetching {component_name} data from e-Stat API: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in e-Stat API fetch for {component_name}: {e}")
            return None

    def _fetch_gdp_components_data(self) -> Optional[Dict]:
        """e-StatからGDP構成要素データを取得"""
        try:
            private_consumption_data = self._fetch_component_data(
                self.CAT01_CODE_PRIVATE_CONSUMPTION,
                "Private Consumption"
            )

            private_investment_data = self._fetch_component_data(
                self.CAT01_CODE_PRIVATE_INVESTMENT,
                "Private Investment"
            )

            if not private_consumption_data and not private_investment_data:
                logger.error("Failed to fetch any component data")
                return None

            series = []

            if private_consumption_data:
                series.append({
                    "name": "民間最終消費支出",
                    "code": self.CAT01_CODE_PRIVATE_CONSUMPTION,
                    "data": private_consumption_data
                })

            if private_investment_data:
                series.append({
                    "name": "民間企業設備",
                    "code": self.CAT01_CODE_PRIVATE_INVESTMENT,
                    "data": private_investment_data
                })

            # 最新値を取得
            latest = None
            if series:
                latest_data = {}
                for s in series:
                    if s["data"]:
                        latest_point = s["data"][-1]
                        latest_data[s["name"]] = {
                            "date": latest_point["date"],
                            "value": latest_point["value"]
                        }
                if latest_data:
                    # 最初のシリーズの最新日付を基準にする
                    first_series = series[0]
                    if first_series["data"]:
                        latest = {
                            "date": first_series["data"][-1]["date"],
                            "components": latest_data
                        }

            return {
                "series": series,
                "latest": latest,
                "metadata": {
                    "source": "e-Stat (Cabinet Office, Government of Japan)",
                    "indicator": "GDP Components Growth Rate (Quarter-to-Quarter %)",
                    "stats_data_id": self.STATS_DATA_ID
                }
            }

        except Exception as e:
            logger.error(f"Error fetching GDP components data: {e}")
            return None

    def get_gdp_components_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """GDP構成要素データを取得（キャッシュ対応）"""

        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "series": cached_data.get("series", []),
                        "latest": cached_data.get("latest"),
                        "next_release": cached_data.get("next_release"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # e-Statから取得
        fresh_data = self._fetch_gdp_components_data()
        if fresh_data:
            next_release = get_next_release_from_fmp(self.ECONALPHA_ID)

            cache_payload = {
                "series": fresh_data["series"],
                "latest": fresh_data["latest"],
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "series": fresh_data["series"],
                "latest": fresh_data["latest"],
                "next_release": next_release,
                "cached": False,
                "source": "e-stat",
                "last_updated": datetime.now(JST).isoformat()
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "series": file_cache.get("series", []),
                "latest": file_cache.get("latest"),
                "next_release": file_cache.get("next_release"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "series": [],
            "latest": None,
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def get_gdp_components_table_data(self) -> Dict[str, Any]:
        """テーブル表示用データを取得"""
        data = self.get_gdp_components_data()

        series_list = data.get("series", [])

        if not series_list:
            return {"columns": [], "rows": [], "metadata": {}}

        # 日付→各構成要素の値をマッピング
        date_map = {}

        for series in series_list:
            component_name = series.get("name", "")
            series_data = series.get("data", [])

            for point in series_data:
                date = point["date"]
                value = point["value"]

                if date not in date_map:
                    date_map[date] = {"date": date}

                date_map[date][component_name] = value

        # 日付でソート（新しい順）
        rows = sorted(date_map.values(), key=lambda x: x["date"], reverse=True)

        columns = [
            {"key": "date", "label": "四半期", "type": "string"},
            {"key": "民間最終消費支出", "label": "民間最終消費支出 (%)", "type": "number"},
            {"key": "民間企業設備", "label": "民間企業設備 (%)", "type": "number"},
        ]

        return {
            "columns": columns,
            "rows": rows,
            "metadata": {
                "source": "e-Stat (Cabinet Office, Government of Japan)",
                "indicator": "GDP Components Growth Rate (Quarter-to-Quarter %)"
            },
            "last_updated": data.get("last_updated")
        }

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        return should_refresh_by_fmp_schedule(self.ECONALPHA_ID, last_updated_str, max_age_hours=72)

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "GDP Components",
            "source": "e-Stat (Cabinet Office)",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "series_count": len(cached_data.get("series", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
gdp_components_service = GDPComponentsService()
