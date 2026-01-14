"""
e-Stat API 家計調査サービス
総務省統計局の家計調査データをe-Stat APIから取得

データ:
- 消費支出（二人以上世帯、全国）
- 前年比・前月比を計算

統計表ID: 0003343671 (品目分類 2020年改定)
"""
import os
import requests
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")

# e-Stat API設定
ESTAT_API_KEY = os.getenv('ESTAT_API_KEY', os.getenv('ESTAT_APPID'))
ESTAT_BASE_URL = 'https://api.e-stat.go.jp/rest/3.0/app/json'

# 統計表ID
STATS_DATA_ID = '0003343671'  # 品目分類（2020年改定）

# カテゴリコード
CATEGORY_CODES = {
    'consumption_expenditure': '001100000',  # 消費支出
}


class EstatHouseholdSurveyService:
    """e-Stat 家計調査サービス"""

    def __init__(self):
        if not ESTAT_API_KEY:
            raise ValueError("ESTAT_API_KEY or ESTAT_APPID environment variable is required")

    def fetch_consumption_expenditure(
        self,
        from_year: int = 2015,
        to_year: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        消費支出データを取得

        Args:
            from_year: 開始年
            to_year: 終了年（Noneの場合は現在年）

        Returns:
            [
                {
                    "date": "YYYY-MM-01",
                    "value": float,  # 消費支出（円）
                },
                ...
            ]
        """
        if to_year is None:
            to_year = datetime.now(JST).year

        url = f'{ESTAT_BASE_URL}/getStatsData'
        params = {
            'appId': ESTAT_API_KEY,
            'statsDataId': STATS_DATA_ID,
            'cdCat01': CATEGORY_CODES['consumption_expenditure'],
            'cdCat02': '03',      # 二人以上の世帯
            'cdArea': '00000',    # 全国
            'cdTimeFrom': f'{from_year}000101',
            'cdTimeTo': f'{to_year}001212',
            'limit': 500
        }

        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        if 'GET_STATS_DATA' not in data:
            print(f"e-Stat API error: {data}")
            return []

        values = data['GET_STATS_DATA']['STATISTICAL_DATA'].get('DATA_INF', {}).get('VALUE', [])
        if isinstance(values, dict):
            values = [values]

        result = []
        for v in values:
            time_code = v.get('@time', '')
            value_str = v.get('$', '')

            if not time_code or not value_str:
                continue

            # time_codeから年月を抽出（例: 2018000101 → 2018-01-01）
            year = time_code[:4]
            month = time_code[8:10]

            try:
                value = float(value_str)
                result.append({
                    'date': f'{year}-{month}-01',
                    'value': value
                })
            except ValueError:
                continue

        # 日付順にソート
        result.sort(key=lambda x: x['date'])

        print(f"Fetched {len(result)} consumption expenditure records from e-Stat")
        return result

    def calculate_yoy_mom(
        self,
        data: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        前年比（YoY）と前月比（MoM）を計算

        Args:
            data: fetch_consumption_expenditure()の戻り値

        Returns:
            {
                "yoy": [{"date": "YYYY-MM-01", "value": float}, ...],
                "mom": [{"date": "YYYY-MM-01", "value": float}, ...]
            }
        """
        # 日付をキーにしたマップを作成
        date_map = {d['date']: d['value'] for d in data}

        yoy_data = []
        mom_data = []

        for item in data:
            date_str = item['date']
            current_value = item['value']

            # 日付をパース
            date = datetime.strptime(date_str, '%Y-%m-%d')

            # 前年同月の日付
            prev_year_date = f'{date.year - 1}-{date.month:02d}-01'

            # 前月の日付
            if date.month == 1:
                prev_month_date = f'{date.year - 1}-12-01'
            else:
                prev_month_date = f'{date.year}-{date.month - 1:02d}-01'

            # YoY計算
            if prev_year_date in date_map:
                prev_year_value = date_map[prev_year_date]
                if prev_year_value != 0:
                    yoy = ((current_value - prev_year_value) / prev_year_value) * 100
                    yoy_data.append({
                        'date': date_str,
                        'value': round(yoy, 1)
                    })

            # MoM計算
            if prev_month_date in date_map:
                prev_month_value = date_map[prev_month_date]
                if prev_month_value != 0:
                    mom = ((current_value - prev_month_value) / prev_month_value) * 100
                    mom_data.append({
                        'date': date_str,
                        'value': round(mom, 1)
                    })

        return {
            'yoy': yoy_data,
            'mom': mom_data
        }

    def get_historical_data(
        self,
        from_year: int = 2015
    ) -> Dict[str, Any]:
        """
        過去データを取得し、YoY/MoMを計算

        Returns:
            {
                "yoy": {"data": [...], "latest": {...}},
                "mom": {"data": [...], "latest": {...}},
                "source": "e-Stat",
                "fetched_at": str
            }
        """
        # 生データを取得
        raw_data = self.fetch_consumption_expenditure(from_year=from_year)

        if not raw_data:
            return {
                'yoy': None,
                'mom': None,
                'source': 'e-Stat',
                'error': 'No data available'
            }

        # YoY/MoMを計算
        calculated = self.calculate_yoy_mom(raw_data)

        yoy_data = calculated['yoy']
        mom_data = calculated['mom']

        return {
            'yoy': {
                'data': yoy_data,
                'latest': yoy_data[-1] if yoy_data else None
            },
            'mom': {
                'data': mom_data,
                'latest': mom_data[-1] if mom_data else None
            },
            'raw_data': raw_data,
            'source': 'e-Stat',
            'fetched_at': datetime.now(JST).isoformat()
        }


# シングルトンインスタンス
estat_household_survey_service = EstatHouseholdSurveyService()


if __name__ == '__main__':
    # テスト実行
    service = EstatHouseholdSurveyService()
    result = service.get_historical_data(from_year=2018)

    print("\n=== YoY Data (最新10件) ===")
    for item in result['yoy']['data'][-10:]:
        print(f"  {item['date']}: {item['value']:+.1f}%")

    print("\n=== MoM Data (最新10件) ===")
    for item in result['mom']['data'][-10:]:
        print(f"  {item['date']}: {item['value']:+.1f}%")
