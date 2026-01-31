"""
スペインCPI/HICP 初回データ取込スクリプト

INE Tempus3 JSON APIから過去データを取得してDBに格納

使用方法:
    cd backend
    python scripts/import_spain_cpi_initial_data.py

シリーズコード:
- CPI MoM: IPC251855
- CPI YoY: IPC251856
- Core CPI MoM: IPC253989
- Core CPI YoY: IPC253990
- HICP MoM: IPCA1886
- HICP YoY: IPCA1885
"""
import sys
import os
import requests
from datetime import datetime
from typing import Dict, List, Any, Optional

# パスを追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# .envをロード
from dotenv import load_dotenv
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env')
load_dotenv(env_path)

from core.database import get_db_connection


# INE Tempus3 APIシリーズコード
INE_SERIES = {
    "cpi_mom": "IPC251855",
    "cpi_yoy": "IPC251856",
    "core_cpi_mom": "IPC253989",
    "core_cpi_yoy": "IPC253990",
    "hicp_mom": "IPCA1886",
    "hicp_yoy": "IPCA1885",
}

# APIエンドポイント
INE_API_BASE = "https://servicios.ine.es/wstempus/js/EN/DATOS_SERIE"

# 取得期間数（月数）- 全履歴を取得
PERIODS = 300  # 約25年分

# 月名マッピング
MONTH_MAP = {
    'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
    'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12,
    'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
    'julio': 7, 'agosto': 8, 'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12,
}


def parse_period_to_month(period_name: str) -> Optional[int]:
    """INEの期間名を月番号に変換"""
    if not period_name:
        return None

    period_lower = period_name.strip().lower()

    if period_lower in MONTH_MAP:
        return MONTH_MAP[period_lower]

    if period_lower.startswith('m') and len(period_lower) == 3:
        try:
            return int(period_lower[1:])
        except ValueError:
            pass

    try:
        month = int(period_name)
        if 1 <= month <= 12:
            return month
    except ValueError:
        pass

    return None


def fetch_from_api(series_code: str, data_type: str) -> List[Dict[str, Any]]:
    """INE Tempus3 APIからデータを取得"""
    try:
        url = f"{INE_API_BASE}/{series_code}?nult={PERIODS}"

        print(f"[{data_type}] Fetching from API: {url}")

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
        }

        response = requests.get(url, headers=headers, timeout=60)
        response.raise_for_status()

        json_data = response.json()

        # APIレスポンス形式: {"COD": "...", "Nombre": "...", "Data": [...]}
        # データは "Data" キー内にネストされている
        data_list = json_data.get("Data", []) if isinstance(json_data, dict) else json_data

        result = []
        for item in data_list:
            try:
                year = item.get("Anyo")
                # FK_Periodo は月番号（1-12）を直接表す
                month = item.get("FK_Periodo")
                value = item.get("Valor")

                if year is None or value is None or month is None:
                    continue

                # 月番号が1-12の範囲内か確認
                if not (1 <= month <= 12):
                    continue

                date_str = f"{year}-{month:02d}-01"

                result.append({
                    "date": date_str,
                    "value": round(float(value), 2),
                })

            except Exception as item_error:
                print(f"[{data_type}] Error parsing item: {item_error}")
                continue

        result.sort(key=lambda x: x["date"])
        print(f"[{data_type}] Fetched {len(result)} records from API")
        return result

    except requests.exceptions.RequestException as e:
        print(f"[{data_type}] Request error: {e}")
        return []
    except Exception as e:
        print(f"[{data_type}] Error: {e}")
        import traceback
        traceback.print_exc()
        return []


def merge_data(all_data: Dict[str, List[Dict]]) -> Dict[str, Dict[str, float]]:
    """
    各シリーズのデータをdate単位でマージ

    Returns:
        {
            "2024-01-01": {"cpi_mom": 0.1, "cpi_yoy": 3.2, ...},
            ...
        }
    """
    merged = {}

    for data_type, records in all_data.items():
        for record in records:
            date = record["date"]
            if date not in merged:
                merged[date] = {}
            merged[date][data_type] = record["value"]

    return merged


def import_to_database(merged_data: Dict[str, Dict[str, float]]):
    """マージしたデータをDBにインポート"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            insert_count = 0
            update_count = 0

            for date_str, values in sorted(merged_data.items()):
                # UPSERT（存在すれば更新、なければ挿入）
                sql = """
                    INSERT INTO spain_cpi_history (
                        date, cpi_yoy, cpi_mom, core_cpi_yoy, core_cpi_mom, hicp_yoy, hicp_mom, source
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, 'ine_api'
                    )
                    ON CONFLICT (date) DO UPDATE SET
                        cpi_yoy = COALESCE(EXCLUDED.cpi_yoy, spain_cpi_history.cpi_yoy),
                        cpi_mom = COALESCE(EXCLUDED.cpi_mom, spain_cpi_history.cpi_mom),
                        core_cpi_yoy = COALESCE(EXCLUDED.core_cpi_yoy, spain_cpi_history.core_cpi_yoy),
                        core_cpi_mom = COALESCE(EXCLUDED.core_cpi_mom, spain_cpi_history.core_cpi_mom),
                        hicp_yoy = COALESCE(EXCLUDED.hicp_yoy, spain_cpi_history.hicp_yoy),
                        hicp_mom = COALESCE(EXCLUDED.hicp_mom, spain_cpi_history.hicp_mom),
                        source = 'ine_api',
                        updated_at = NOW()
                    RETURNING (xmax = 0) AS inserted
                """

                cursor.execute(sql, (
                    date_str,
                    values.get("cpi_yoy"),
                    values.get("cpi_mom"),
                    values.get("core_cpi_yoy"),
                    values.get("core_cpi_mom"),
                    values.get("hicp_yoy"),
                    values.get("hicp_mom"),
                ))

                result = cursor.fetchone()
                if result and result[0]:
                    insert_count += 1
                else:
                    update_count += 1

            conn.commit()
            cursor.close()
            print(f"\nDatabase import completed:")
            print(f"  - Inserted: {insert_count} records")
            print(f"  - Updated: {update_count} records")

    except Exception as e:
        print(f"Error importing to database: {e}")
        import traceback
        traceback.print_exc()


def main():
    print("=" * 60)
    print("Spain CPI/HICP Initial Data Import (INE API)")
    print("=" * 60)

    # 各シリーズからデータを取得
    all_data = {}

    for data_type, series_code in INE_SERIES.items():
        print(f"\n--- Fetching {data_type} ({series_code}) ---")
        data = fetch_from_api(series_code, data_type)
        if data:
            all_data[data_type] = data
            print(f"  Date range: {data[0]['date']} to {data[-1]['date']}")
            print(f"  Latest: {data[-1]}")

    if not all_data:
        print("\nError: No data fetched from any source")
        return

    # データをマージ
    print("\n--- Merging data ---")
    merged_data = merge_data(all_data)
    print(f"Total dates: {len(merged_data)}")

    # 最初と最後のデータを表示
    sorted_dates = sorted(merged_data.keys())
    if sorted_dates:
        print(f"Date range: {sorted_dates[0]} to {sorted_dates[-1]}")

    # DBにインポート
    print("\n--- Importing to database ---")
    import_to_database(merged_data)

    print("\n" + "=" * 60)
    print("Import completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
