"""
ECBマクロ経済予測サービス
ECB Data API (MPD - Macroeconomic Projection Database)からデータを取得

指標:
- GDP成長率 (YER)
- 失業率 (URX)
- HICP（総合）(HIC)
- コアインフレ（除くエネルギー・食料）(HEF)
- コアインフレ（除くエネルギー・食料・間接税）(HEFT)
- 外需 (FOD)
- 短期金利 (STN)
- 民間消費 (PCR)
- 賃金上昇率 (CEX)

データソース:
- ECB Data API (https://data-api.ecb.europa.eu)
- ECB MPD (Macroeconomic Projection Database)

発表スケジュール:
- 四半期ごと（3月・6月・9月・12月）
- ECB理事会での金融政策決定時に公表
- 発表時刻: 21:15-21:25 CET (冬時間: 22:15-22:25 JST)
             20:15-20:25 CEST (夏時間: 21:15-21:25 JST)

キャッシュ方式: FMP発表日時ベース判定方式
"""
import json
import time
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from core.redis_client import redis_client
from services.eurozone.fmp_next_release_utils import (
    get_next_release_by_pattern,
    should_refresh_by_pattern,
)


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
CET = ZoneInfo("Europe/Berlin")

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "eurozone" / "monetary_policy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ecb_macro_projections_cache.json"


class ECBMacroProjectionsService:
    """ECBマクロ経済予測サービス"""

    # ECB Data API
    ECB_API_BASE = "https://data-api.ecb.europa.eu/service/data"
    DATAFLOW = "MPD"  # Macroeconomic Projection Database

    # 指標コードとメタデータ
    INDICATORS = {
        "gdp": {
            "code": "YER",
            "name_jp": "GDP成長率",
            "name_en": "GDP Growth",
            "unit": "% yoy",
            "aggregation_annual": "A",
            "aggregation_quarterly": "P",
            "annual_frequency": "A",
            "quarterly_frequency": "Q"
        },
        "unemployment": {
            "code": "URX",
            "name_jp": "失業率",
            "name_en": "Unemployment Rate",
            "unit": "%",
            "aggregation": "F",
            "annual_frequency": "A",
            "quarterly_frequency": "Q"
        },
        "hicp": {
            "code": "HIC",
            "name_jp": "HICP（総合）",
            "name_en": "HICP Inflation",
            "unit": "% yoy",
            "aggregation": "A",
            "annual_frequency": "A",
            "quarterly_frequency": "Q"
        },
        "core_inflation": {
            "code": "HEF",
            "name_jp": "コアインフレ（除くエネルギー・食料）",
            "name_en": "Core Inflation (excl. energy & food)",
            "unit": "% yoy",
            "aggregation": "A",
            "annual_frequency": "A",
            "quarterly_frequency": "Q"
        },
        "core_inflation_tax": {
            "code": "HEFT",
            "name_jp": "コアインフレ（除くエネルギー・食料・間接税）",
            "name_en": "Core Inflation (excl. energy, food & indirect taxes)",
            "unit": "% yoy",
            "aggregation": "A",
            "annual_frequency": "A",
            "quarterly_frequency": "Q"
        },
        "foreign_demand": {
            "code": "FOD",
            "name_jp": "外需",
            "name_en": "Foreign Demand",
            "unit": "% change",
            "aggregation_annual": "A",
            "aggregation_quarterly": "P",
            "annual_frequency": "A",
            "quarterly_frequency": "Q"
        },
        "interest_rate": {
            "code": "STN",
            "name_jp": "短期金利",
            "name_en": "Short-term Interest Rates",
            "unit": "% per annum",
            "aggregation": "I",
            "annual_frequency": "A",
            "quarterly_frequency": None
        },
        "private_consumption": {
            "code": "PCR",
            "name_jp": "民間消費",
            "name_en": "Private Consumption",
            "unit": "% yoy",
            "aggregation": "A",
            "annual_frequency": "A",
            "quarterly_frequency": "Q"
        },
        "wages": {
            "code": "CEX",
            "name_jp": "賃金上昇率",
            "name_en": "Compensation per Employee",
            "unit": "% yoy",
            "aggregation": "A",
            "annual_frequency": "A",
            "quarterly_frequency": "Q"
        }
    }

    # 発表月→シーズンコードのマッピング
    # ECBは3月・6月・9月・12月の理事会（各月の初旬〜中旬）で見通しを公表する
    # W=Winter/March, G=Spring/June, S=Summer/September, A=Autumn/December
    SEASON_BY_RELEASE_MONTH = {3: 'W', 6: 'G', 9: 'S', 12: 'A'}

    # ヴィンテージシーズンマッピング（静的フォールバック用）
    # 動的探索（_resolve_available_vintages）が失敗した場合のみ使用する。
    # 各発表月いっぱいは前四半期のヴィンテージを保持する保守的な対応表のため、
    # 通常は動的探索で公開済みの最新ヴィンテージを優先する。
    # W=Winter/March, G=Spring/June, S=Summer/September, A=Autumn/December
    VINTAGE_SEASONS = {
        1: ('A', 'S'),   # 1月: 最新=12月(Autumn), 前回=9月(Summer) - Winterはまだ未発表
        2: ('A', 'S'),   # 2月: 最新=12月(Autumn), 前回=9月(Summer)
        3: ('A', 'S'),   # 3月: 最新=12月(Autumn), 前回=9月(Summer) - Winter発表前
        4: ('W', 'A'),   # 4月: 最新=3月(Winter), 前回=12月(Autumn)
        5: ('W', 'A'),   # 5月: 最新=3月(Winter), 前回=12月(Autumn)
        6: ('W', 'A'),   # 6月: 最新=3月(Winter), 前回=12月(Autumn) - Spring発表前
        7: ('G', 'W'),   # 7月: 最新=6月(Spring), 前回=3月(Winter)
        8: ('G', 'W'),   # 8月: 最新=6月(Spring), 前回=3月(Winter)
        9: ('G', 'W'),   # 9月: 最新=6月(Spring), 前回=3月(Winter) - Summer発表前
        10: ('S', 'G'),  # 10月: 最新=9月(Summer), 前回=6月(Spring)
        11: ('S', 'G'),  # 11月: 最新=9月(Summer), 前回=6月(Spring)
        12: ('S', 'G'),  # 12月: 最新=9月(Summer), 前回=6月(Spring) - Autumn発表前
    }

    DATA_CACHE_KEY = "monetary_policy:ecb_macro_projections:data"
    MAX_RETRIES = 3
    RETRY_DELAY = 5
    RATE_LIMIT_DELAY = 60

    # FMPイベントパターン（ECB政策金利発表に連動）
    # 3月・6月・9月・12月の政策金利発表時にMacro Projectionsも更新される
    FMP_EVENT_PATTERN = "ECB Interest Rate Decision"

    def __init__(self):
        # 解決済みヴィンテージの日次メモ化（API過剰プローブ防止）。キー=(year, month, day)
        self._vintage_cache: Dict[tuple, Dict[str, Any]] = {}

    def _vintage_has_data(self, vintage: str) -> bool:
        """ヴィンテージがECB APIで公開済みかを軽量チェック（リトライなし・短timeout）

        未公開のヴィンテージはECB APIが404を返すため、これで発表済みかを判別できる。
        通常のリトライ付き取得を使うと未公開ヴィンテージで無駄に待機するため専用実装。
        """
        url = f"{self.ECB_API_BASE}/{self.DATAFLOW}/A.U2.YER.A.{vintage}.0000"
        try:
            response = requests.get(
                url,
                params={'format': 'jsondata', 'lastNObservations': 1},
                timeout=15,
            )
            if response.status_code != 200:
                return False
            data = response.json()
            return bool(data.get('dataSets'))
        except Exception:
            return False

    def _candidate_vintages(self, reference_date: datetime) -> List[tuple]:
        """現時点で発表済みの可能性があるヴィンテージを新しい順に列挙

        各発表点（3/6/9/12月）について、参照日がその発表月以降であれば候補に含める。
        発表月の初旬（理事会前）はAPIが未公開＝404のため、最終的な採否はプローブで決める。
        戻り値: (season, year_2digit, vintage) のリスト（新しい順）
        """
        current_year = reference_date.year
        current_month = reference_date.month
        candidates: List[tuple] = []
        # 現在年から過去3年分の発表点を新しい順に生成
        for year in range(current_year, current_year - 3, -1):
            for rel_month in (12, 9, 6, 3):
                if year < current_year or current_month >= rel_month:
                    season = self.SEASON_BY_RELEASE_MONTH[rel_month]
                    year2 = year % 100
                    candidates.append((season, year2, f"{season}{year2:02d}"))
        return candidates

    def _resolve_available_vintages(self, reference_date: datetime) -> List[tuple]:
        """ECB APIで実際に公開済みの最新2ヴィンテージを新しい順に解決"""
        available: List[tuple] = []
        for candidate in self._candidate_vintages(reference_date):
            if self._vintage_has_data(candidate[2]):
                available.append(candidate)
                if len(available) >= 2:
                    break
        return available

    def _get_vintage_codes(self, reference_date: Optional[datetime] = None) -> Dict[str, Any]:
        """利用可能な最新ヴィンテージコードを取得

        ECB APIで実際に公開済みのヴィンテージを動的に解決する。
        ECBは発表月の初旬〜中旬の理事会で見通しを公表するため、固定の月マッピングだと
        発表月いっぱい前四半期の見通しを表示し続けてしまう（凍結に見える）問題を回避する。
        プローブが失敗した場合のみ従来の静的マッピングにフォールバックする。
        """
        if reference_date is None:
            reference_date = datetime.now()

        cache_key = (reference_date.year, reference_date.month, reference_date.day)
        if cache_key in self._vintage_cache:
            return self._vintage_cache[cache_key]

        try:
            available = self._resolve_available_vintages(reference_date)
        except Exception as e:
            print(f"[ECB MPD] Vintage probing failed, using static mapping: {e}")
            available = []

        if len(available) >= 2:
            (latest_season, _, latest_vintage) = available[0]
            (previous_season, _, previous_vintage) = available[1]
            result = {
                'latest_season': latest_season,
                'previous_season': previous_season,
                'latest_vintage': latest_vintage,
                'previous_vintage': previous_vintage,
                'latest_season_name': self._get_season_name(latest_season),
                'previous_season_name': self._get_season_name(previous_season),
            }
            print(
                f"[ECB MPD] Resolved vintages dynamically: latest={latest_vintage}, "
                f"previous={previous_vintage}"
            )
        else:
            print("[ECB MPD] Falling back to static vintage mapping")
            result = self._get_vintage_codes_static(reference_date)

        self._vintage_cache[cache_key] = result
        return result

    def _get_vintage_codes_static(self, reference_date: Optional[datetime] = None) -> Dict[str, Any]:
        """現在の月に基づいてヴィンテージコードを取得（静的フォールバック）"""
        if reference_date is None:
            reference_date = datetime.now()

        current_month = reference_date.month
        current_year = reference_date.year

        latest_season, previous_season = self.VINTAGE_SEASONS[current_month]

        # 年の計算: 1-3月は前年のAutumn(12月)が最新なので、前年を使用
        if current_month <= 3:
            # 1-3月: 最新=前年12月(A), 前回=前年9月(S)
            latest_year = (current_year - 1) % 100
            previous_year = (current_year - 1) % 100
        elif current_month <= 6:
            # 4-6月: 最新=今年3月(W), 前回=前年12月(A)
            latest_year = current_year % 100
            previous_year = (current_year - 1) % 100
        else:
            # 7-12月: 両方今年
            latest_year = current_year % 100
            previous_year = current_year % 100

        return {
            'latest_season': latest_season,
            'previous_season': previous_season,
            'latest_year': latest_year,
            'previous_year': previous_year,
            'latest_vintage': f"{latest_season}{latest_year:02d}",
            'previous_vintage': f"{previous_season}{previous_year:02d}",
            'latest_season_name': self._get_season_name(latest_season),
            'previous_season_name': self._get_season_name(previous_season)
        }

    def _get_season_name(self, season_code: str) -> str:
        """シーズンコードからシーズン名を取得"""
        season_names = {
            'W': 'Winter/March',
            'G': 'Spring/June',
            'S': 'Summer/September',
            'A': 'Autumn/December'
        }
        return season_names.get(season_code, season_code)

    def _make_request_with_retry(self, url: str, params: dict, timeout: int = 30) -> Optional[requests.Response]:
        """リトライロジック付きHTTPリクエスト"""
        for attempt in range(self.MAX_RETRIES):
            try:
                print(f"[ECB MPD] Attempt {attempt + 1}/{self.MAX_RETRIES}: Fetching from {url}")
                response = requests.get(url, params=params, timeout=timeout)

                if response.status_code == 429:
                    if attempt < self.MAX_RETRIES - 1:
                        print(f"[ECB MPD] Rate limited (429). Waiting {self.RATE_LIMIT_DELAY}s...")
                        time.sleep(self.RATE_LIMIT_DELAY)
                        continue
                    else:
                        print(f"[ECB MPD] Rate limited (429) after {self.MAX_RETRIES} attempts")
                        return None

                if response.status_code != 200:
                    print(f"[ECB MPD] HTTP {response.status_code} error on attempt {attempt + 1}")
                    if attempt < self.MAX_RETRIES - 1:
                        time.sleep(self.RETRY_DELAY)
                        continue
                    return None

                return response

            except requests.exceptions.Timeout:
                print(f"[ECB MPD] Request timeout on attempt {attempt + 1}")
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY)
                    continue
                return None

            except requests.exceptions.RequestException as e:
                print(f"[ECB MPD] Request exception on attempt {attempt + 1}: {e}")
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY)
                    continue
                return None

        return None

    def _fetch_projection_data(self, projection_key: str, last_n_observations: int = 20) -> Optional[List[Dict]]:
        """ECB APIから予測データを取得"""
        try:
            url = f"{self.ECB_API_BASE}/{self.DATAFLOW}/{projection_key}"
            params = {
                'format': 'jsondata',
                'lastNObservations': last_n_observations
            }

            response = self._make_request_with_retry(url, params)
            if response is None:
                return None

            result = []
            data = response.json()

            if 'dataSets' in data and len(data['dataSets']) > 0:
                dataset = data['dataSets'][0]
                structure = data.get('structure', {})
                dimensions = structure.get('dimensions', {})

                observation_dims = dimensions.get('observation', [])
                time_values = []

                for dim in observation_dims:
                    if dim.get('id') == 'TIME_PERIOD':
                        time_values = [v.get('id') or v.get('name') for v in dim.get('values', [])]
                        break

                if 'series' in dataset:
                    for series_key, series_data in dataset['series'].items():
                        observations = series_data.get('observations', {})

                        for obs_index, obs_value in observations.items():
                            obs_idx = int(obs_index)
                            if obs_idx < len(time_values):
                                date_str = time_values[obs_idx]
                                value = obs_value[0] if isinstance(obs_value, list) else obs_value

                                if value is not None:
                                    result.append({
                                        'date': date_str,
                                        'value': float(value)
                                    })

            print(f"[ECB MPD] Fetched {len(result)} data points for {projection_key}")
            return result

        except Exception as e:
            print(f"[ECB MPD] Error fetching data for {projection_key}: {e}")
            return None

    def _fetch_indicator_data(self, indicator_key: str) -> Dict:
        """特定の指標のデータを取得（最新と前回のヴィンテージ両方）"""
        vintages = self._get_vintage_codes()
        indicator_info = self.INDICATORS[indicator_key]

        latest_vintage = vintages['latest_vintage']
        previous_vintage = vintages['previous_vintage']
        indicator_code = indicator_info['code']

        # 指標によって aggregation が異なる
        if indicator_key in ["foreign_demand", "gdp"]:
            agg_annual = indicator_info['aggregation_annual']
            agg_quarterly = indicator_info['aggregation_quarterly']
        else:
            agg_annual = indicator_info.get('aggregation', 'A')
            agg_quarterly = indicator_info.get('aggregation', 'A')

        result = {
            "annual_latest": [],
            "annual_previous": [],
            "quarterly_latest": [],
            "quarterly_previous": []
        }

        fetch_tasks = []

        # 年次データ
        if indicator_info['annual_frequency']:
            annual_latest_key = f"{indicator_info['annual_frequency']}.U2.{indicator_code}.{agg_annual}.{latest_vintage}.0000"
            fetch_tasks.append(('annual_latest', annual_latest_key))

            annual_previous_key = f"{indicator_info['annual_frequency']}.U2.{indicator_code}.{agg_annual}.{previous_vintage}.0000"
            fetch_tasks.append(('annual_previous', annual_previous_key))

        # 四半期データ
        if indicator_info.get('quarterly_frequency'):
            quarterly_latest_key = f"{indicator_info['quarterly_frequency']}.U2.{indicator_code}.{agg_quarterly}.{latest_vintage}.0000"
            fetch_tasks.append(('quarterly_latest', quarterly_latest_key))

            quarterly_previous_key = f"{indicator_info['quarterly_frequency']}.U2.{indicator_code}.{agg_quarterly}.{previous_vintage}.0000"
            fetch_tasks.append(('quarterly_previous', quarterly_previous_key))

        # 並列でデータ取得
        with ThreadPoolExecutor(max_workers=4) as executor:
            future_to_key = {
                executor.submit(self._fetch_projection_data, projection_key): (data_key, projection_key)
                for data_key, projection_key in fetch_tasks
            }

            for future in as_completed(future_to_key):
                data_key, projection_key = future_to_key[future]
                try:
                    data = future.result()
                    result[data_key] = data or []
                except Exception as e:
                    print(f"[ECB MPD] Error fetching {projection_key}: {e}")
                    result[data_key] = []

        return result

    def get_ecb_macro_projections_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """ECBマクロ経済予測データを取得"""
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "indicators": cached_data.get("indicators", {}),
                        "metadata": cached_data.get("metadata", {}),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # ECB APIからデータ取得
        api_result = self._fetch_all_projections_data()
        if api_result and any(api_result.get("indicators", {}).values()):
            cache_payload = {
                "indicators": api_result["indicators"],
                "metadata": api_result["metadata"],
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "indicators": api_result["indicators"],
                "metadata": api_result["metadata"],
                "cached": False,
                "source": "ecb_api",
                "last_updated": datetime.now(JST).isoformat()
            }

        # ファイルキャッシュからフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "indicators": file_cache.get("indicators", {}),
                "metadata": file_cache.get("metadata", {}),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "indicators": {},
            "metadata": {},
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _fetch_all_projections_data(self) -> Optional[Dict]:
        """全指標のデータを並列で取得"""
        try:
            vintages = self._get_vintage_codes()
            all_data = {}

            # 並列で全指標を取得
            with ThreadPoolExecutor(max_workers=8) as executor:
                future_to_indicator = {
                    executor.submit(self._fetch_indicator_data, indicator_key): indicator_key
                    for indicator_key in self.INDICATORS.keys()
                }

                for future in as_completed(future_to_indicator):
                    indicator_key = future_to_indicator[future]
                    try:
                        print(f"[ECB MPD] Fetching indicator: {indicator_key}")
                        indicator_data = future.result()
                        all_data[indicator_key] = indicator_data
                        print(f"[ECB MPD] Successfully fetched indicator: {indicator_key}")
                    except Exception as e:
                        print(f"[ECB MPD] Error fetching indicator {indicator_key}: {e}")
                        all_data[indicator_key] = {
                            "annual_latest": [],
                            "annual_previous": [],
                            "quarterly_latest": [],
                            "quarterly_previous": []
                        }

            return {
                "indicators": all_data,
                "metadata": {
                    "last_updated": datetime.now(JST).isoformat(),
                    "source": "European Central Bank (ECB)",
                    "latest_vintage": vintages['latest_vintage'],
                    "previous_vintage": vintages['previous_vintage'],
                    "latest_season_name": vintages['latest_season_name'],
                    "previous_season_name": vintages['previous_season_name']
                }
            }

        except Exception as e:
            print(f"[ECB MPD] Error fetching all projections: {e}")
            return None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """
        キャッシュを更新すべきかどうかを判定（FMPパターン方式）
        ECB政策金利発表（3月・6月・9月・12月）に連動して更新
        """
        return should_refresh_by_pattern(self.FMP_EVENT_PATTERN, last_updated_str, "EU")

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
            "indicator": "ECB Macroeconomic Projections",
            "source": "ECB MPD API",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "metadata": cached_data.get("metadata") if cached_data else None,
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
ecb_macro_projections_service = ECBMacroProjectionsService()
