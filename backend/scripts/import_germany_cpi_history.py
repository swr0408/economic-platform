"""
ドイツCPI/HICP履歴データをDestatis APIからインポート

使用方法:
    cd backend
    python -m scripts.import_germany_cpi_history

実行内容:
    1. Destatis GENESIS APIからCPI/HICPの長期データを取得
    2. germany_cpi_historyテーブルにUPSERT
"""
import os
import sys
from datetime import datetime

# プロジェクトルートをパスに追加
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from dotenv import load_dotenv
load_dotenv()

from services.eurozone.germany_cpi_service import germany_cpi_service


def import_destatis_data():
    """Destatis APIからデータを取得してDBにインポート"""
    print("=" * 60)
    print("ドイツCPI/HICP履歴データインポート")
    print("=" * 60)

    # 1. Destatis APIからデータを取得
    print("\n[1/3] Destatis APIからデータを取得中...")
    result = germany_cpi_service.get_germany_cpi_data(force_refresh=True)

    if result.get("error") or not result.get("data"):
        print(f"Error: データ取得に失敗しました - {result.get('error', 'No data')}")
        return False

    data = result["data"]
    print(f"取得件数: {len(data)}件")

    # 2. DBにインポート
    print("\n[2/3] DBにインポート中...")

    try:
        from core.database import SessionLocal
        from sqlalchemy import text

        with SessionLocal() as session:
            upsert_query = text("""
                INSERT INTO germany_cpi_history (
                    date, cpi_index, cpi_yoy_change, cpi_mom_change,
                    hicp_index, hicp_yoy_change, hicp_mom_change,
                    source, is_preliminary
                ) VALUES (
                    :date, :cpi_index, :cpi_yoy_change, :cpi_mom_change,
                    :hicp_index, :hicp_yoy_change, :hicp_mom_change,
                    'destatis', FALSE
                )
                ON CONFLICT (date) DO UPDATE SET
                    cpi_index = COALESCE(EXCLUDED.cpi_index, germany_cpi_history.cpi_index),
                    cpi_yoy_change = COALESCE(EXCLUDED.cpi_yoy_change, germany_cpi_history.cpi_yoy_change),
                    cpi_mom_change = COALESCE(EXCLUDED.cpi_mom_change, germany_cpi_history.cpi_mom_change),
                    hicp_index = COALESCE(EXCLUDED.hicp_index, germany_cpi_history.hicp_index),
                    hicp_yoy_change = COALESCE(EXCLUDED.hicp_yoy_change, germany_cpi_history.hicp_yoy_change),
                    hicp_mom_change = COALESCE(EXCLUDED.hicp_mom_change, germany_cpi_history.hicp_mom_change),
                    source = CASE
                        WHEN germany_cpi_history.is_preliminary THEN 'destatis'
                        ELSE germany_cpi_history.source
                    END,
                    is_preliminary = FALSE,
                    updated_at = NOW()
            """)

            inserted = 0
            for point in data:
                try:
                    session.execute(upsert_query, {
                        "date": point["date"],
                        "cpi_index": point.get("cpi_index"),
                        "cpi_yoy_change": point.get("cpi_yoy_change"),
                        "cpi_mom_change": point.get("cpi_mom_change"),
                        "hicp_index": point.get("hicp_index"),
                        "hicp_yoy_change": point.get("hicp_yoy_change"),
                        "hicp_mom_change": point.get("hicp_mom_change"),
                    })
                    inserted += 1
                except Exception as e:
                    print(f"  Warning: {point['date']} のインポートに失敗: {e}")
                    continue

            session.commit()
            print(f"インポート完了: {inserted}件")

    except Exception as e:
        print(f"Error: DBインポートに失敗しました - {e}")
        import traceback
        traceback.print_exc()
        return False

    # 3. 確認
    print("\n[3/3] インポート結果を確認中...")
    try:
        with SessionLocal() as session:
            count_query = text("SELECT COUNT(*) FROM germany_cpi_history")
            total = session.execute(count_query).scalar()

            latest_query = text("""
                SELECT date, cpi_yoy_change, hicp_yoy_change, source
                FROM germany_cpi_history
                ORDER BY date DESC
                LIMIT 5
            """)
            latest = session.execute(latest_query).fetchall()

            print(f"\n総レコード数: {total}件")
            print("\n最新5件:")
            print("-" * 60)
            for row in latest:
                print(f"  {row[0]}: CPI={row[1]}%, HICP={row[2]}%, source={row[3]}")

    except Exception as e:
        print(f"Warning: 確認クエリでエラー - {e}")

    print("\n" + "=" * 60)
    print("インポート完了")
    print("=" * 60)
    return True


if __name__ == "__main__":
    import_destatis_data()
