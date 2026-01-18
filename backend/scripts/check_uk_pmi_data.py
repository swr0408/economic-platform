"""
UK PMIデータの確認スクリプト
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(project_root, ".env"))

from core.database import get_db_connection


def check_uk_pmi():
    """UK PMIのDBデータを確認"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # 製造業PMIのデータ数を確認
            cur.execute("""
                SELECT COUNT(*), MIN(datetime_utc), MAX(datetime_utc)
                FROM economic_calendar_events
                WHERE country = 'UK'
                  AND event ILIKE '%S&P Global Manufacturing PMI%'
                  AND actual IS NOT NULL
            """)
            mfg_result = cur.fetchone()
            print(f"製造業PMI: {mfg_result[0]} records, {mfg_result[1]} ~ {mfg_result[2]}")

            # サービス業PMIのデータ数を確認
            cur.execute("""
                SELECT COUNT(*), MIN(datetime_utc), MAX(datetime_utc)
                FROM economic_calendar_events
                WHERE country = 'UK'
                  AND event ILIKE '%S&P Global Services PMI%'
                  AND actual IS NOT NULL
            """)
            svc_result = cur.fetchone()
            print(f"サービス業PMI: {svc_result[0]} records, {svc_result[1]} ~ {svc_result[2]}")

            # 総合PMIのデータ数を確認
            cur.execute("""
                SELECT COUNT(*), MIN(datetime_utc), MAX(datetime_utc)
                FROM economic_calendar_events
                WHERE country = 'UK'
                  AND event ILIKE '%S&P Global Composite PMI%'
                  AND actual IS NOT NULL
            """)
            cmp_result = cur.fetchone()
            print(f"総合PMI: {cmp_result[0]} records, {cmp_result[1]} ~ {cmp_result[2]}")

            # 製造業PMIのイベント名を確認（重複がないか）
            print("\n--- 製造業PMIのイベント名一覧 ---")
            cur.execute("""
                SELECT DISTINCT event
                FROM economic_calendar_events
                WHERE country = 'UK'
                  AND event ILIKE '%Manufacturing PMI%'
                ORDER BY event
            """)
            for row in cur.fetchall():
                print(f"  {row[0]}")

            # 製造業PMIの古いデータのサンプル
            print("\n--- 製造業PMI 古いデータサンプル (先頭10件) ---")
            cur.execute("""
                SELECT datetime_utc, actual, event, provider
                FROM economic_calendar_events
                WHERE country = 'UK'
                  AND event ILIKE '%S&P Global Manufacturing PMI%'
                  AND actual IS NOT NULL
                ORDER BY datetime_utc ASC
                LIMIT 10
            """)
            for row in cur.fetchall():
                print(f"  {row[0]}: {row[1]} ({row[2]}) - provider: {row[3]}")


if __name__ == "__main__":
    check_uk_pmi()
