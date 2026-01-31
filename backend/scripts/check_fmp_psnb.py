"""FMP DB内のPublic Sector Net Borrowingイベントを確認"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env')
load_dotenv(env_path)

from core.database import get_db_connection

with get_db_connection() as conn:
    cursor = conn.cursor()

    # テーブル構造を確認
    cursor.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'economic_calendar_events'
        ORDER BY ordinal_position
    """)
    print("=== Table columns ===")
    for row in cursor.fetchall():
        print(row)

    # GBのPSNBイベントを確認
    cursor.execute("""
        SELECT event, datetime_utc
        FROM economic_calendar_events
        WHERE country IN ('GB', 'UK') AND event ILIKE '%Public Sector%'
        ORDER BY datetime_utc DESC
        LIMIT 10
    """)
    rows = cursor.fetchall()
    print("\n=== GB/UK Public Sector events ===")
    for row in rows:
        print(row)

    # 将来のGBイベント数を確認
    cursor.execute("""
        SELECT COUNT(*)
        FROM economic_calendar_events
        WHERE country IN ('GB', 'UK') AND datetime_utc >= NOW()
    """)
    count = cursor.fetchone()[0]
    print(f"\n=== Future GB/UK events: {count} ===")

    # 直近の将来GBイベント
    cursor.execute("""
        SELECT event, datetime_utc, actual
        FROM economic_calendar_events
        WHERE country IN ('GB', 'UK') AND datetime_utc >= NOW()
        ORDER BY datetime_utc ASC
        LIMIT 10
    """)
    rows = cursor.fetchall()
    print("\n=== Next 10 GB/UK events ===")
    for row in rows:
        print(row)

    cursor.close()
