"""
日本 所定内給与 履歴データインポート

e-Stat APIから賃金指数データを取得し、前年比を計算してDBに格納する

データソース:
- 産業別賃金指数（所定内給与） statsDataId=0003030978
- 調査産業計、5人以上、全国

使用方法:
    docker compose exec backend python scripts/import_scheduled_wage_history.py
"""
import os
import sys
import requests
from datetime import datetime
from typing import Dict, List, Any, Optional

# パス設定
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import SessionLocal
from sqlalchemy import text


def fetch_wage_index_from_estat() -> List[Dict[str, Any]]:
    """
    e-Stat APIから賃金指数データを取得

    Returns:
        月次データのリスト [{date, scheduled_wage_index, general_index, part_time_index}, ...]
    """
    API_KEY = os.getenv('ESTAT_API_KEY')
    if not API_KEY:
        raise ValueError("ESTAT_API_KEY environment variable is required")

    BASE_URL = 'https://api.e-stat.go.jp/rest/3.0/app/json/getStatsData'

    # 産業別賃金指数（所定内給与）
    params = {
        'appId': API_KEY,
        'statsDataId': '0003030978',  # 産業別賃金指数（所定内給与）
        'cdCat01': '1000000',         # 調査産業計
        'cdCat02': '700',             # 5人以上
        'limit': 10000,
    }

    print(f"Fetching data from e-Stat API...")
    response = requests.get(BASE_URL, params=params, timeout=120)
    response.raise_for_status()

    data = response.json()
    result = data.get('GET_STATS_DATA', {}).get('RESULT', {})

    if result.get('STATUS') != 0:
        raise ValueError(f"API error: {result.get('ERROR_MSG')}")

    stat_data = data.get('GET_STATS_DATA', {}).get('STATISTICAL_DATA', {})
    data_inf = stat_data.get('DATA_INF', {})
    values = data_inf.get('VALUE', [])

    print(f"Retrieved {len(values)} raw values")

    # 月次データを抽出
    monthly_data = {}

    for v in values:
        time = v.get('@time', '')
        cat03 = v.get('@cat03', '')  # 就業形態
        val = v.get('$', '')

        if not time or not val or val == '-':
            continue

        # 時間形式: "2005000101" (年月日) または "2005000000" (年次)
        if len(time) < 10:
            continue

        year = time[:4]
        month_str = time[6:8]

        # 月次データのみ（01-12）
        try:
            month = int(month_str)
            if month < 1 or month > 12:
                continue
        except ValueError:
            continue

        date_key = f"{year}-{month:02d}-01"

        if date_key not in monthly_data:
            monthly_data[date_key] = {
                'date': date_key,
                'scheduled_wage_index': None,
                'general_index': None,
                'part_time_index': None,
            }

        # 就業形態別に格納
        # cat03: 計(10), 一般(20), パート(30) など - 統計表により異なる
        value = float(val)

        # このテーブルは就業形態の区分がないため、全体の指数のみ
        if cat03 in ['10', '700', '701', '']:
            monthly_data[date_key]['scheduled_wage_index'] = value

    print(f"Extracted {len(monthly_data)} monthly data points")
    return list(monthly_data.values())


def fetch_employment_type_data() -> Dict[str, Dict[str, float]]:
    """
    就業形態別（一般・パート）の指数データを取得

    Returns:
        {date: {general_index, part_time_index}, ...}
    """
    API_KEY = os.getenv('ESTAT_API_KEY')
    BASE_URL = 'https://api.e-stat.go.jp/rest/3.0/app/json/getStatsData'

    result_data = {}

    # 一般労働者
    print("Fetching general worker data...")
    params = {
        'appId': API_KEY,
        'statsDataId': '0003030712',  # 事業所規模別賃金指数（一般・パート別）
        'cdTab': '807',               # 賃金指数（所定内給与）
        'cdCat01': 'TL',              # 調査産業計
        'cdCat02': 'T',               # 5人以上
        'limit': 10000,
    }

    try:
        response = requests.get(BASE_URL, params=params, timeout=120)
        if response.status_code == 200:
            data = response.json()
            stat_data = data.get('GET_STATS_DATA', {}).get('STATISTICAL_DATA', {})
            values = stat_data.get('DATA_INF', {}).get('VALUE', [])

            for v in values:
                time = v.get('@time', '')
                cat03 = v.get('@cat03', '')  # 就業形態
                val = v.get('$', '')

                if not time or not val or val == '-':
                    continue

                if len(time) >= 10:
                    year = time[:4]
                    month_str = time[6:8]
                    try:
                        month = int(month_str)
                        if 1 <= month <= 12:
                            date_key = f"{year}-{month:02d}-01"

                            if date_key not in result_data:
                                result_data[date_key] = {}

                            value = float(val)

                            # 就業形態: 31=一般, 42=パート
                            if cat03 == '31':
                                result_data[date_key]['general_index'] = value
                            elif cat03 == '42':
                                result_data[date_key]['part_time_index'] = value
                    except (ValueError, TypeError):
                        continue

            print(f"Got {len(result_data)} dates with employment type data")
    except Exception as e:
        print(f"Warning: Could not fetch employment type data: {e}")

    return result_data


def calculate_yoy(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    前年同月比を計算

    Args:
        data: 月次データリスト（指数付き）

    Returns:
        YoY計算済みデータ
    """
    # 日付でソート
    sorted_data = sorted(data, key=lambda x: x['date'])

    # 日付→指数のマップ作成
    index_map = {d['date']: d for d in sorted_data}

    for item in sorted_data:
        date = item['date']
        year = int(date[:4])
        month = int(date[5:7])

        # 前年同月の日付
        prev_year_date = f"{year - 1}-{month:02d}-01"

        if prev_year_date in index_map:
            prev = index_map[prev_year_date]

            # 所定内給与YoY
            if item.get('scheduled_wage_index') and prev.get('scheduled_wage_index'):
                item['scheduled_wage_yoy'] = round(
                    (item['scheduled_wage_index'] / prev['scheduled_wage_index'] - 1) * 100, 2
                )

            # 一般YoY
            if item.get('general_index') and prev.get('general_index'):
                item['general_yoy'] = round(
                    (item['general_index'] / prev['general_index'] - 1) * 100, 2
                )

            # パートYoY
            if item.get('part_time_index') and prev.get('part_time_index'):
                item['part_time_yoy'] = round(
                    (item['part_time_index'] / prev['part_time_index'] - 1) * 100, 2
                )

    return sorted_data


def import_to_db(data: List[Dict[str, Any]]) -> int:
    """
    データをDBにインポート

    Args:
        data: インポートするデータ

    Returns:
        インポート件数
    """
    with SessionLocal() as session:
        imported = 0

        for item in data:
            try:
                # UPSERT
                session.execute(text("""
                    INSERT INTO japan_scheduled_wage_history (
                        date, scheduled_wage_index, scheduled_wage_yoy,
                        general_index, general_yoy,
                        part_time_index, part_time_yoy,
                        source, updated_at
                    ) VALUES (
                        :date, :scheduled_wage_index, :scheduled_wage_yoy,
                        :general_index, :general_yoy,
                        :part_time_index, :part_time_yoy,
                        'e-Stat', NOW()
                    )
                    ON CONFLICT (date) DO UPDATE SET
                        scheduled_wage_index = EXCLUDED.scheduled_wage_index,
                        scheduled_wage_yoy = EXCLUDED.scheduled_wage_yoy,
                        general_index = EXCLUDED.general_index,
                        general_yoy = EXCLUDED.general_yoy,
                        part_time_index = EXCLUDED.part_time_index,
                        part_time_yoy = EXCLUDED.part_time_yoy,
                        updated_at = NOW()
                """), {
                    'date': item['date'],
                    'scheduled_wage_index': item.get('scheduled_wage_index'),
                    'scheduled_wage_yoy': item.get('scheduled_wage_yoy'),
                    'general_index': item.get('general_index'),
                    'general_yoy': item.get('general_yoy'),
                    'part_time_index': item.get('part_time_index'),
                    'part_time_yoy': item.get('part_time_yoy'),
                })
                imported += 1

            except Exception as e:
                print(f"Error importing {item['date']}: {e}")
                continue

        session.commit()
        return imported


def main():
    """メイン処理"""
    print("=" * 60)
    print("Japan Scheduled Wage History Import")
    print("=" * 60)

    # 1. 基本の賃金指数を取得
    print("\n1. Fetching base wage index data...")
    monthly_data = fetch_wage_index_from_estat()

    # 2. 就業形態別データをマージ（可能な場合）
    print("\n2. Fetching employment type data...")
    emp_data = fetch_employment_type_data()

    for item in monthly_data:
        date = item['date']
        if date in emp_data:
            item['general_index'] = emp_data[date].get('general_index')
            item['part_time_index'] = emp_data[date].get('part_time_index')

    # 3. 前年比を計算
    print("\n3. Calculating YoY...")
    data_with_yoy = calculate_yoy(monthly_data)

    # YoYがある件数をカウント
    yoy_count = sum(1 for d in data_with_yoy if d.get('scheduled_wage_yoy') is not None)
    print(f"Data with YoY: {yoy_count} / {len(data_with_yoy)}")

    # 4. DBにインポート
    print("\n4. Importing to database...")
    imported = import_to_db(data_with_yoy)
    print(f"Imported {imported} records")

    # 5. 結果確認
    print("\n5. Verification...")
    with SessionLocal() as session:
        result = session.execute(text("""
            SELECT COUNT(*), MIN(date), MAX(date)
            FROM japan_scheduled_wage_history
            WHERE scheduled_wage_yoy IS NOT NULL
        """)).fetchone()

        print(f"Total records with YoY: {result[0]}")
        print(f"Date range: {result[1]} to {result[2]}")

        # 最新10件
        recent = session.execute(text("""
            SELECT date, scheduled_wage_yoy, general_yoy, part_time_yoy
            FROM japan_scheduled_wage_history
            WHERE scheduled_wage_yoy IS NOT NULL
            ORDER BY date DESC
            LIMIT 10
        """)).fetchall()

        print("\nLatest 10 records:")
        for r in recent:
            print(f"  {r[0]}: scheduled={r[1]}%, general={r[2]}%, part_time={r[3]}%")

    print("\n" + "=" * 60)
    print("Import completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
