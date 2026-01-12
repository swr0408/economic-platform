"""
EU指標マッピング修正スクリプト

マーケットインパクトタブで発表履歴が取得できない問題を修正
"""
import os
import sys

# パス追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import get_db_connection


def fix_eu_mappings():
    """EU指標のeconalpha_idを修正"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # GDP成長率
            cur.execute("""
                UPDATE indicator_event_mapping
                SET econalpha_id = 'eu_gdp_growth'
                WHERE country = 'EU'
                  AND fmp_event_patterns @> ARRAY['GDP Growth Rate QoQ']
                  AND econalpha_id IS NULL
            """)
            gdp_count = cur.rowcount
            print(f"Updated eu_gdp_growth: {gdp_count} rows")

            # 鉱工業生産
            cur.execute("""
                UPDATE indicator_event_mapping
                SET econalpha_id = 'eu_industrial_production'
                WHERE country = 'EU'
                  AND fmp_event_patterns @> ARRAY['Industrial Production MoM']
                  AND econalpha_id IS NULL
            """)
            prod_count = cur.rowcount
            print(f"Updated eu_industrial_production: {prod_count} rows")

            conn.commit()

            # 確認
            cur.execute("""
                SELECT econalpha_id, econalpha_name, country, fmp_event_patterns, is_active
                FROM indicator_event_mapping
                WHERE country = 'EU'
                  AND econalpha_id IN ('eu_gdp_growth', 'eu_industrial_production')
            """)
            results = cur.fetchall()

            print("\n=== 修正後の状態 ===")
            for row in results:
                print(f"  {row[0]}: {row[1]} (active={row[4]})")
                print(f"    patterns: {row[3]}")

            if not results:
                print("  警告: マッピングが見つかりません。add_fmp_indicators.sqlを先に実行してください。")


if __name__ == "__main__":
    fix_eu_mappings()
