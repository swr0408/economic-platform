"""
NBS 月次データ CSV 自動バックフィル

`backend/data/manual_update/monthly/china/*.csv` を走査し、
DB (nbs_monthly_data) に欠落している月を自動で UPSERT する。

ユーザがCSVを編集すると次回スケジューラ実行時に自動取込される。

CSV フォーマット:
    Column 0: 公表日 (YYYY/M 形式)
    "結果" 列に値 (列名は CSV により異なる)

ファイル名 → DB 指標ID マッピング:
    CSV_INDICATOR_MAP で定義
"""
import csv
import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# CSV ファイル名 → (DB 指標ID, 値が含まれる列名)
CSV_INDICATOR_MAP: Dict[str, tuple] = {
    "中国固定資産投資.csv": ("cn_fixed_asset_investment_ytd", "結果"),
    "中国輸出物価.csv": ("cn_export_prices_index", "結果"),
}

CSV_DIR = Path(__file__).parent.parent.parent / "data" / "manual_update" / "monthly" / "china"


def _parse_csv(file_path: Path, value_column: str) -> Dict[str, float]:
    """CSV を {YYYY-MM-DD: value} 形式でパース

    Args:
        file_path: CSV ファイルパス
        value_column: 値が含まれる列名（"結果" など）

    Returns:
        {"2010-08-01": 24.8, ...}
    """
    result: Dict[str, float] = {}
    try:
        with open(file_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if value_column not in (reader.fieldnames or []):
                logger.warning(
                    f"[NBS-CSV] '{value_column}' column not found in {file_path.name}, "
                    f"available: {reader.fieldnames}"
                )
                return result

            for row in reader:
                date_raw = row.get("公表日", "").strip()
                val_raw = row.get(value_column, "").strip()
                if not date_raw or not val_raw:
                    continue
                try:
                    parts = date_raw.split("/")
                    if len(parts) != 2:
                        continue
                    year, month = int(parts[0]), int(parts[1])
                    date_str = f"{year:04d}-{month:02d}-01"
                    result[date_str] = float(val_raw)
                except (ValueError, IndexError):
                    continue
    except Exception as e:
        logger.warning(f"[NBS-CSV] Failed to parse {file_path.name}: {e}")
    return result


def _load_db_dates(indicator: str) -> set:
    """DBに既に登録されている日付セットを返す"""
    try:
        from core.database import SessionLocal
        from sqlalchemy import text

        with SessionLocal() as session:
            rows = session.execute(text("""
                SELECT date FROM nbs_monthly_data WHERE indicator = :ind
            """), {"ind": indicator}).fetchall()
        return {row[0].isoformat() if hasattr(row[0], "isoformat") else str(row[0]) for row in rows}
    except Exception as e:
        logger.warning(f"[NBS-CSV] DB date load failed for {indicator}: {e}")
        return set()


def backfill_csv(indicator: Optional[str] = None) -> Dict[str, int]:
    """manual_update 配下の CSV から DB へ欠落月を補填

    Args:
        indicator: 指定時はその指標のCSVのみ処理。Noneなら全CSV処理。

    Returns:
        {indicator: inserted_count, ...}
    """
    from services.china.nbs_db_utils import upsert_nbs_data

    results: Dict[str, int] = {}

    for csv_name, (db_indicator, value_col) in CSV_INDICATOR_MAP.items():
        if indicator and db_indicator != indicator:
            continue

        csv_path = CSV_DIR / csv_name
        if not csv_path.exists():
            logger.debug(f"[NBS-CSV] CSV not found: {csv_path}")
            continue

        csv_data = _parse_csv(csv_path, value_col)
        if not csv_data:
            continue

        existing = _load_db_dates(db_indicator)
        missing = {dt: val for dt, val in csv_data.items() if dt not in existing}

        if not missing:
            logger.debug(f"[NBS-CSV] {db_indicator}: no missing months from {csv_name}")
            continue

        count = upsert_nbs_data(db_indicator, missing, source="csv")
        results[db_indicator] = count
        logger.info(
            f"[NBS-CSV] {db_indicator}: backfilled {count} months from {csv_name} "
            f"(CSV={len(csv_data)}, DB existing={len(existing)})"
        )

    return results
