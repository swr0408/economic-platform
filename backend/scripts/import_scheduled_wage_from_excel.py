"""
日本 所定内給与 履歴データインポート（e-Stat Excel版）

e-Stat Excelの付表データをDBに格納する
現在のExcelファイルには2023年11月以降の月次データが含まれている

使用方法:
    docker compose exec backend python scripts/import_scheduled_wage_from_excel.py
"""
import os
import sys

# パス設定
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.japan.scheduled_wage_service import scheduled_wage_service
from core.database import SessionLocal
from sqlalchemy import text


def main():
    """メイン処理"""
    print("=" * 60)
    print("Japan Scheduled Wage Import from e-Stat Excel")
    print("=" * 60)

    # 1. サービスからデータを取得（e-Stat Excel）
    print("\n1. Fetching data from e-Stat Excel...")
    result = scheduled_wage_service.get_scheduled_wage_data(force_refresh=True)

    source = result.get('source', 'unknown')
    print(f"Source: {source}")

    scheduled_wage = result.get('scheduled_wage', {})
    general = result.get('general', {})
    part_time = result.get('part_time', {})

    sw_data = scheduled_wage.get('data', []) if scheduled_wage else []
    gen_data = general.get('data', []) if general else []
    pt_data = part_time.get('data', []) if part_time else []

    print(f"Scheduled wage: {len(sw_data)} records")
    print(f"General: {len(gen_data)} records")
    print(f"Part-time: {len(pt_data)} records")

    if not sw_data:
        print("No data to import")
        return

    # 2. データをマージ
    print("\n2. Merging data...")
    date_set = set()
    for d in sw_data:
        date_set.add(d['date'])
    for d in gen_data:
        date_set.add(d['date'])
    for d in pt_data:
        date_set.add(d['date'])

    sw_map = {d['date']: d['value'] for d in sw_data}
    gen_map = {d['date']: d['value'] for d in gen_data}
    pt_map = {d['date']: d['value'] for d in pt_data}

    merged_data = []
    for date in sorted(date_set):
        merged_data.append({
            'date': date,
            'scheduled_wage_yoy': sw_map.get(date),
            'general_yoy': gen_map.get(date),
            'part_time_yoy': pt_map.get(date),
        })

    print(f"Merged: {len(merged_data)} records")

    # 3. DBにインポート
    print("\n3. Importing to database...")
    imported = 0

    with SessionLocal() as session:
        for item in merged_data:
            try:
                session.execute(text("""
                    INSERT INTO japan_scheduled_wage_history (
                        date, scheduled_wage_yoy, general_yoy, part_time_yoy,
                        source, updated_at
                    ) VALUES (
                        :date, :scheduled_wage_yoy, :general_yoy, :part_time_yoy,
                        'e-Stat Excel', NOW()
                    )
                    ON CONFLICT (date) DO UPDATE SET
                        scheduled_wage_yoy = COALESCE(EXCLUDED.scheduled_wage_yoy, japan_scheduled_wage_history.scheduled_wage_yoy),
                        general_yoy = COALESCE(EXCLUDED.general_yoy, japan_scheduled_wage_history.general_yoy),
                        part_time_yoy = COALESCE(EXCLUDED.part_time_yoy, japan_scheduled_wage_history.part_time_yoy),
                        source = CASE
                            WHEN EXCLUDED.scheduled_wage_yoy IS NOT NULL THEN 'e-Stat Excel'
                            ELSE japan_scheduled_wage_history.source
                        END,
                        updated_at = NOW()
                """), item)
                imported += 1
            except Exception as e:
                print(f"Error: {item['date']}: {e}")

        session.commit()

    print(f"Imported {imported} records")

    # 4. 結果確認
    print("\n4. Verification...")
    with SessionLocal() as session:
        result = session.execute(text("""
            SELECT COUNT(*), MIN(date), MAX(date)
            FROM japan_scheduled_wage_history
            WHERE scheduled_wage_yoy IS NOT NULL
        """)).fetchone()

        print(f"Total records with YoY: {result[0]}")
        print(f"Date range: {result[1]} to {result[2]}")

        recent = session.execute(text("""
            SELECT date, scheduled_wage_yoy, general_yoy, part_time_yoy, source
            FROM japan_scheduled_wage_history
            ORDER BY date DESC
            LIMIT 10
        """)).fetchall()

        print("\nLatest 10 records:")
        for r in recent:
            print(f"  {r[0]}: sw={r[1]}%, gen={r[2]}%, pt={r[3]}% [{r[4]}]")

    print("\n" + "=" * 60)
    print("Import completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
