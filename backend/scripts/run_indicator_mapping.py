"""
indicator_event_mapping テーブルにUK PMIのマッピングを追加するスクリプト

使用方法:
  cd backend
  python scripts/run_indicator_mapping.py
"""
import sys
import os

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# .envファイルを読み込む
from dotenv import load_dotenv
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(project_root, ".env"))

from core.database import get_db_connection


def add_uk_pmi_mapping():
    """UK PMIのindicator_event_mappingを追加"""

    sql = """
    INSERT INTO indicator_event_mapping (econalpha_id, econalpha_name, country, frequency, fmp_event_patterns, is_active)
    VALUES ('uk_pmi', 'UK PMI（製造業・サービス業・総合）', 'UK', 'monthly', ARRAY['S&P Global Manufacturing PMI', 'S&P Global Services PMI', 'S&P Global Composite PMI'], TRUE)
    ON CONFLICT (econalpha_id) DO UPDATE SET fmp_event_patterns = EXCLUDED.fmp_event_patterns, updated_at = NOW();
    """

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                conn.commit()
                print("Successfully added uk_pmi mapping!")

                # 確認クエリ
                cur.execute("""
                    SELECT econalpha_id, econalpha_name, country, frequency, fmp_event_patterns
                    FROM indicator_event_mapping
                    WHERE econalpha_id = 'uk_pmi'
                """)
                result = cur.fetchone()
                if result:
                    print(f"\nInserted record:")
                    print(f"  econalpha_id: {result[0]}")
                    print(f"  econalpha_name: {result[1]}")
                    print(f"  country: {result[2]}")
                    print(f"  frequency: {result[3]}")
                    print(f"  fmp_event_patterns: {result[4]}")

    except Exception as e:
        print(f"Error: {e}")
        return False

    return True


if __name__ == "__main__":
    add_uk_pmi_mapping()
