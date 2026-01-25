"""
機械受注サービス（日本）
e-Stat APIから機械受注データを取得

指標:
- 機械受注（船舶・電力を除く民需）: Core Machinery Orders
- 前年比 (YoY): 原系列から計算
- 前月比 (MoM): 季節調整済みから計算
- 前月比3か月平均

データソース:
- e-Stat API（内閣府経済社会総合研究所）
- https://www.esri.cao.go.jp/jp/stat/juchu/juchu.html

発表スケジュール:
- 月次（毎月10日頃 8:50 JST発表）
- e-Stat Calendar: https://www.e-stat.go.jp/release-calendar/statistics/00100401

キャッシュ方式: ファイルキャッシュ + FMP発表日時ベース判定方式
"""
import json
import logging
import os
import requests
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo

try:
    from backend.core.redis_client import redis_client
    from backend.services.japan.fmp_next_release_utils import (
        get_next_release_from_fmp,
        should_refresh_by_fmp_schedule,
    )
except ImportError:
    from core.redis_client import redis_client
    from services.japan.fmp_next_release_utils import (
        get_next_release_from_fmp,
        should_refresh_by_fmp_schedule,
    )

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "japan" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "machinery_orders_cache.json"


class MachineryOrdersService:
    """機械受注サービス（e-Stat API）"""

    # e-Stat API設定
    STATS_DATA_ID = "0003355222"  # 機械受注統計調査

    # Category codes for filtering "民間需要（船舶・電力を除く）"
    # cat01='160' represents "民間需要(船舶・電力を除く)"
    # cat02='100' represents the seasonally adjusted series (季節調整済み) - for MoM
    # cat02='110' represents the original series (原系列) - for YoY
    TARGET_CAT01 = '160'
    TARGET_CAT02_SA = '100'   # 季節調整済み（前月比用）
    TARGET_CAT02_ORIG = '110'  # 原系列（前年比用）

    DATA_CACHE_KEY = "japan:machinery_orders:data"
    ECONALPHA_ID = "japan_machinery_orders"

    def __init__(self):
        self.api_key = os.getenv('ESTAT_API_KEY')
        if not self.api_key:
            logger.warning("ESTAT_API_KEY environment variable not set")

    def get_machinery_orders_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        機械受注データを取得

        Returns:
            {
                "data": [...],  # MoM/YoY計算済みデータ
                "last_updated": str,
                "source": str,
                "description": str,
                "next_release": {...}
            }
        """
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    logger.info("Returning cached machinery orders data from Redis")
                    return {
                        **cached_data,
                        "cached": True,
                        "source": "redis",
                    }

        # ファイルキャッシュチェック（force_refreshでない場合）
        if not force_refresh:
            file_cache = self._load_file_cache()
            if file_cache:
                last_updated_str = file_cache.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    logger.info("Returning cached machinery orders data from file")
                    # Redisにも保存
                    redis_client.set(self.DATA_CACHE_KEY, file_cache, expire=0)
                    return {
                        **file_cache,
                        "cached": True,
                        "source": "file",
                    }

        # e-Stat APIからデータ取得
        logger.info("Fetching fresh machinery orders data from e-Stat API")
        try:
            raw_data = self._fetch_from_estat()
            # 季節調整済みデータをパース（前月比用）
            sa_data = self._parse_data(raw_data, self.TARGET_CAT02_SA)

            # 原系列データをパース（前年比用）
            orig_data = self._parse_data(raw_data, self.TARGET_CAT02_ORIG)

            # 原系列データが取得できなかった場合、季節調整済みデータから前年比も計算
            if not orig_data:
                logger.warning(f"Original series (cat02={self.TARGET_CAT02_ORIG}) not found, calculating YoY from seasonally adjusted data")
                # 季節調整済みデータから前月比と前年比の両方を計算
                sa_data_with_changes = self._calculate_mom_change(sa_data)
                sa_data_with_yoy = self._calculate_yoy_change(sa_data_with_changes)
                merged_data = self._calculate_mom_3m_average(sa_data_with_yoy)
            else:
                # 前月比を計算（季節調整済みから）
                sa_data_with_mom = self._calculate_mom_change(sa_data)
                # 前月比3か月平均を追加
                sa_data_with_mom_avg = self._calculate_mom_3m_average(sa_data_with_mom)

                # 前年比を計算（原系列から）
                orig_data_with_yoy = self._calculate_yoy_change(orig_data)

                # 両方のデータをマージ
                merged_data = self._merge_sa_and_orig(sa_data_with_mom_avg, orig_data_with_yoy)

            # 次回発表日時取得
            next_release = get_next_release_from_fmp(self.ECONALPHA_ID)

            result = {
                "data": merged_data,
                "last_updated": datetime.now(JST).isoformat(),
                "source": "e-Stat (Cabinet Office)",
                "description": "民間需要（船舶・電力を除く）- 機械受注統計調査",
                "next_release": next_release,
            }

            # キャッシュ保存
            redis_client.set(self.DATA_CACHE_KEY, result, expire=0)
            self._save_file_cache(result)

            return {
                **result,
                "cached": False,
            }

        except Exception as e:
            logger.error(f"Error fetching machinery orders data: {e}")

            # エラー時はファイルキャッシュにフォールバック
            file_cache = self._load_file_cache()
            if file_cache:
                return {
                    **file_cache,
                    "cached": True,
                    "source": "file (fallback)",
                    "error": str(e),
                }

            return {
                "data": [],
                "last_updated": None,
                "source": "none",
                "description": "民間需要（船舶・電力を除く）- 機械受注統計調査",
                "next_release": None,
                "cached": False,
                "error": str(e),
            }

    def _fetch_from_estat(self) -> Dict:
        """e-Stat APIからデータ取得"""
        if not self.api_key:
            raise ValueError("ESTAT_API_KEY environment variable not set")

        url = "http://api.e-stat.go.jp/rest/3.0/app/json/getStatsData"

        params = {
            'appId': self.api_key,
            'lang': 'J',
            'statsDataId': self.STATS_DATA_ID,
            'metaGetFlg': 'Y',
            'cntGetFlg': 'N',
            'explanationGetFlg': 'Y',
            'annotationGetFlg': 'Y',
            'sectionHeaderFlg': '1',
            'replaceSpChars': '0'
        }

        logger.info(f"Fetching machinery orders data from e-Stat API (statsDataId: {self.STATS_DATA_ID})")
        response = requests.get(url, params=params, timeout=60)
        response.raise_for_status()
        data = response.json()

        if 'GET_STATS_DATA' not in data:
            raise ValueError(f"Unexpected response structure: {data}")

        result = data['GET_STATS_DATA']['RESULT']
        if result.get('STATUS') != 0:
            raise ValueError(f"e-Stat API error: {result.get('ERROR_MSG')}")

        logger.info("Successfully fetched machinery orders data from e-Stat")
        return data

    def _parse_data(self, raw_data: Dict, target_cat02: str) -> List[Dict]:
        """
        e-Statの生データをパース
        "民間需要（船舶・電力を除く）" のみ抽出

        Args:
            raw_data: e-Stat APIからの生データ
            target_cat02: 対象のcat02コード（'100'=季節調整済み, '01'=原系列）
        """
        values = raw_data['GET_STATS_DATA']['STATISTICAL_DATA']['DATA_INF']['VALUE']

        if not isinstance(values, list):
            values = [values]

        parsed_data = []
        data_by_month = {}  # 月ごとにユニーク化

        # デバッグ: cat02の値を収集
        cat02_values = set()
        for item in values:
            if item.get('@cat01') == self.TARGET_CAT01:
                cat02_values.add(item.get('@cat02', ''))
        logger.info(f"Available cat02 values for cat01={self.TARGET_CAT01}: {cat02_values}")

        for item in values:
            cat01 = item.get('@cat01', '')
            cat02 = item.get('@cat02', '')
            time_code = item.get('@time', '')
            value_str = item.get('$', '')

            # 対象カテゴリのみ抽出
            if cat01 != self.TARGET_CAT01 or cat02 != target_cat02:
                continue

            if not time_code or not value_str:
                continue

            # 時間コードをパース (format: YYYY + 000 + MM + MM, e.g., 2025000808 = 2025年8月)
            try:
                if len(time_code) == 10:
                    year = int(time_code[:4])
                    # 月は末尾2桁
                    month = int(time_code[8:10])

                    # 無効な月をスキップ
                    if month < 1 or month > 12:
                        logger.warning(f"Invalid month: {month} in time_code: {time_code}")
                        continue

                    date_str = f"{year}-{month:02d}-01"
                else:
                    logger.warning(f"Invalid time_code format: {time_code}")
                    continue
            except (ValueError, IndexError) as e:
                logger.warning(f"Error parsing time_code {time_code}: {e}")
                continue

            try:
                value = float(value_str)

                # 月キーでユニーク化
                month_key = f"{year}-{month:02d}"

                # 各月の最新値のみ保持
                data_by_month[month_key] = {
                    'date': date_str,
                    'value': value,
                    'unit': '百万円',
                    '_year': year,
                    '_month': month
                }
            except ValueError as e:
                logger.warning(f"Error parsing value {value_str}: {e}")
                continue

        # リストに変換して日付順にソート
        parsed_data = list(data_by_month.values())
        parsed_data.sort(key=lambda x: (x['_year'], x['_month']))

        # ソート用の一時フィールドを削除
        for item in parsed_data:
            del item['_year']
            del item['_month']

        logger.info(f"Parsed {len(parsed_data)} data points for 民間需要（船舶・電力を除く）(cat02={target_cat02})")
        return parsed_data

    def _calculate_mom_change(self, data: List[Dict]) -> List[Dict]:
        """前月比を計算"""
        result = []

        for i, item in enumerate(data):
            new_item = item.copy()

            if i > 0:
                prev_value = data[i - 1]['value']
                current_value = item['value']

                if prev_value and prev_value != 0:
                    mom_change = ((current_value - prev_value) / prev_value) * 100
                    new_item['mom_change'] = round(mom_change, 1)
                else:
                    new_item['mom_change'] = None
            else:
                new_item['mom_change'] = None

            result.append(new_item)

        return result

    def _calculate_yoy_change(self, data: List[Dict]) -> List[Dict]:
        """前年比を計算（原系列から）"""
        result = []

        for i, item in enumerate(data):
            new_item = item.copy()

            # 12ヶ月前（1年前）のデータを探す
            if i >= 12:
                prev_year_value = data[i - 12]['value']
                current_value = item['value']

                if prev_year_value and prev_year_value != 0:
                    yoy_change = ((current_value - prev_year_value) / prev_year_value) * 100
                    new_item['yoy_change'] = round(yoy_change, 1)
                else:
                    new_item['yoy_change'] = None
            else:
                new_item['yoy_change'] = None

            result.append(new_item)

        return result

    def _calculate_mom_3m_average(self, data: List[Dict]) -> List[Dict]:
        """前月比の3か月平均を計算"""
        result = []

        for i, item in enumerate(data):
            new_item = item.copy()

            # 直近3か月の前月比の平均を計算
            if i >= 2:
                mom_values = []
                for j in range(3):
                    idx = i - j
                    if idx >= 0 and data[idx].get('mom_change') is not None:
                        mom_values.append(data[idx]['mom_change'])

                if len(mom_values) == 3:
                    new_item['mom_3m_avg'] = round(sum(mom_values) / 3, 1)
                else:
                    new_item['mom_3m_avg'] = None
            else:
                new_item['mom_3m_avg'] = None

            result.append(new_item)

        return result

    def _merge_sa_and_orig(self, sa_data: List[Dict], orig_data: List[Dict]) -> List[Dict]:
        """
        季節調整済みデータと原系列データをマージ
        - value, mom_change, mom_3m_avg: 季節調整済みから
        - yoy_change: 原系列から
        """
        # 原系列データを日付でインデックス化
        orig_by_date = {item['date']: item for item in orig_data}

        result = []
        for sa_item in sa_data:
            merged_item = sa_item.copy()
            date = sa_item['date']

            # 原系列からYoYを取得
            if date in orig_by_date:
                merged_item['yoy_change'] = orig_by_date[date].get('yoy_change')
            else:
                merged_item['yoy_change'] = None

            result.append(merged_item)

        return result

    def get_chart_data(self, force_refresh: bool = False) -> Dict:
        """チャート用データ取得（YoY）"""
        full_data = self.get_machinery_orders_data(force_refresh)

        return {
            'chart_data': full_data.get('data', []),
            'last_updated': full_data.get('last_updated'),
            'data_source': full_data.get('source'),
            'next_release': full_data.get('next_release'),
        }

    def get_table_data(self, force_refresh: bool = False) -> Dict:
        """テーブル用データ取得（MoM、新しい順）"""
        full_data = self.get_machinery_orders_data(force_refresh)

        # 新しい順に並べ替え
        table_data = list(reversed(full_data.get('data', [])))

        return {
            'table_data': table_data,
            'last_updated': full_data.get('last_updated'),
            'data_source': full_data.get('source'),
            'next_release': full_data.get('next_release'),
        }

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（FMP発表日時ベース）"""
        return should_refresh_by_fmp_schedule(self.ECONALPHA_ID, last_updated_str)

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
            "indicator": "Machinery Orders (Japan)",
            "source": "e-Stat API (Cabinet Office)",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
machinery_orders_service = MachineryOrdersService()
