#!/usr/bin/env python
"""
工作機械受注統計 PDFインポートスクリプト

JMTBAのアーカイブPDFから過去データ（2009年〜）を取得してDBに格納

使用方法:
    python scripts/import_machine_tool_orders_pdf.py [--start-year 2009] [--end-year 2020]
"""
import argparse
import io
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import pdfplumber
import requests
from dotenv import load_dotenv

# .envファイルを読み込み
load_dotenv(Path(__file__).parent.parent.parent / ".env")

# バックエンドモジュールを読み込むためにパスを追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import SessionLocal
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# JMTBA PDFアーカイブURL
# 2024年6月にアーカイブに移行されたデータ
ARCHIVE_BASE_URL = "https://www.jmtba.or.jp/wjmtbap/wp-content/uploads/2024/06/kakuhou{yy:02d}{mm:02d}.pdf"


def fetch_pdf(year: int, month: int) -> bytes | None:
    """
    PDFファイルを取得

    Args:
        year: 年（4桁）
        month: 月（1-12）

    Returns:
        PDFのバイトデータ、取得失敗時はNone
    """
    yy = year % 100
    url = ARCHIVE_BASE_URL.format(yy=yy, mm=month)

    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            return response.content
        else:
            logger.debug(f"PDF not found: {url} (status={response.status_code})")
            return None
    except requests.RequestException as e:
        logger.warning(f"Failed to fetch PDF {url}: {e}")
        return None


def parse_pdf(pdf_content: bytes, year: int, month: int) -> dict | None:
    """
    PDFからデータを抽出

    Args:
        pdf_content: PDFのバイトデータ
        year: 年（4桁）
        month: 月（1-12）

    Returns:
        抽出されたデータ辞書、抽出失敗時はNone
    """
    try:
        with pdfplumber.open(io.BytesIO(pdf_content)) as pdf:
            if not pdf.pages:
                return None

            page = pdf.pages[0]
            tables = page.extract_tables()

            if not tables:
                logger.warning(f"No tables found in PDF for {year}/{month:02d}")
                return None

            # テーブル2（合計欄）から受注総額と前年比を取得
            # 通常、最後のテーブルに合計が含まれる
            total_orders = None
            total_yoy = None
            domestic_orders = None
            domestic_yoy = None
            foreign_orders = None
            foreign_yoy = None

            for table in tables:
                for row in table:
                    if not row:
                        continue

                    # 最初のセルをクリーンアップして識別
                    first_cell = str(row[0] or '').replace('\n', ' ').strip()

                    # "受注総額" または "受注額" を探す
                    if '受注額' in first_cell or '受注総額' in first_cell or '合計' in first_cell:
                        # 数値を抽出
                        nums = []
                        for cell in row[1:]:
                            if cell:
                                # カンマを除去して数値を取得
                                clean = str(cell).replace(',', '').strip()
                                try:
                                    nums.append(float(clean))
                                except ValueError:
                                    pass

                        # 最初の数値が受注額、2番目が前年比（指数）
                        if len(nums) >= 2:
                            total_orders = nums[0]
                            # 前年比は指数形式（例: 125.3）なので成長率に変換
                            total_yoy = nums[1] - 100 if nums[1] > 50 else nums[1]

                    # 国内受注
                    if '国内' in first_cell or '内需' in first_cell:
                        nums = []
                        for cell in row[1:]:
                            if cell:
                                clean = str(cell).replace(',', '').strip()
                                try:
                                    nums.append(float(clean))
                                except ValueError:
                                    pass
                        if len(nums) >= 2:
                            domestic_orders = nums[0]
                            domestic_yoy = nums[1] - 100 if nums[1] > 50 else nums[1]

                    # 海外受注（外需）
                    if '海外' in first_cell or '外需' in first_cell:
                        nums = []
                        for cell in row[1:]:
                            if cell:
                                clean = str(cell).replace(',', '').strip()
                                try:
                                    nums.append(float(clean))
                                except ValueError:
                                    pass
                        if len(nums) >= 2:
                            foreign_orders = nums[0]
                            foreign_yoy = nums[1] - 100 if nums[1] > 50 else nums[1]

            # テーブル1から合計行を探す（フォールバック）
            if total_orders is None:
                table1 = tables[0] if tables else []
                for row in table1:
                    if not row:
                        continue

                    # 合計行を探す（1-12.など）
                    first_cell = str(row[0] or '').strip()
                    if '1-12' in first_cell or ('12.' in first_cell and '1-11' not in first_cell):
                        # 当月の数値を抽出
                        nums = []
                        for cell in row[1:]:
                            if cell:
                                clean = str(cell).replace(',', '').strip()
                                try:
                                    nums.append(float(clean))
                                except ValueError:
                                    pass

                        if len(nums) >= 2:
                            total_orders = nums[0]
                            total_yoy = nums[1] - 100 if nums[1] > 50 else nums[1]
                            break

            if total_orders is None and total_yoy is None:
                logger.warning(f"Could not extract data from PDF for {year}/{month:02d}")
                return None

            return {
                'date': f"{year}-{month:02d}-01",
                'total_orders': total_orders,
                'total_yoy': total_yoy,
                'domestic_orders': domestic_orders,
                'domestic_yoy': domestic_yoy,
                'foreign_orders': foreign_orders,
                'foreign_yoy': foreign_yoy,
                'data_type': 'kakuhou'
            }

    except Exception as e:
        logger.error(f"Failed to parse PDF for {year}/{month:02d}: {e}")
        return None


def save_to_db(data: dict) -> bool:
    """
    データをDBに保存（UPSERT）

    Args:
        data: 保存するデータ辞書

    Returns:
        保存成功したかどうか
    """
    try:
        with SessionLocal() as session:
            query = text("""
                INSERT INTO japan_machine_tool_orders_history
                (date, total_orders, total_yoy, domestic_orders, domestic_yoy,
                 foreign_orders, foreign_yoy, data_type, updated_at)
                VALUES (:date, :total_orders, :total_yoy, :domestic_orders, :domestic_yoy,
                        :foreign_orders, :foreign_yoy, :data_type, NOW())
                ON CONFLICT (date) DO UPDATE SET
                    total_orders = EXCLUDED.total_orders,
                    total_yoy = EXCLUDED.total_yoy,
                    domestic_orders = EXCLUDED.domestic_orders,
                    domestic_yoy = EXCLUDED.domestic_yoy,
                    foreign_orders = EXCLUDED.foreign_orders,
                    foreign_yoy = EXCLUDED.foreign_yoy,
                    data_type = EXCLUDED.data_type,
                    updated_at = NOW()
            """)
            session.execute(query, data)
            session.commit()
            return True
    except Exception as e:
        logger.error(f"Failed to save data to DB: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='Import Machine Tool Orders data from JMTBA PDFs')
    parser.add_argument('--start-year', type=int, default=2009, help='Start year (default: 2009)')
    parser.add_argument('--end-year', type=int, default=2020, help='End year (default: 2020)')
    parser.add_argument('--dry-run', action='store_true', help='Do not save to DB, just show parsed data')
    args = parser.parse_args()

    logger.info(f"Starting import from {args.start_year} to {args.end_year}")

    success_count = 0
    fail_count = 0

    for year in range(args.start_year, args.end_year + 1):
        for month in range(1, 13):
            # 未来の日付はスキップ
            if datetime(year, month, 1) > datetime.now():
                continue

            logger.info(f"Processing {year}/{month:02d}...")

            pdf_content = fetch_pdf(year, month)
            if not pdf_content:
                logger.warning(f"  PDF not found for {year}/{month:02d}")
                fail_count += 1
                continue

            data = parse_pdf(pdf_content, year, month)
            if not data:
                logger.warning(f"  Failed to parse PDF for {year}/{month:02d}")
                fail_count += 1
                continue

            logger.info(f"  Extracted: orders={data.get('total_orders')}, yoy={data.get('total_yoy')}")

            if args.dry_run:
                logger.info(f"  [DRY RUN] Would save: {data}")
                success_count += 1
            else:
                if save_to_db(data):
                    success_count += 1
                else:
                    fail_count += 1

    logger.info(f"Import completed: {success_count} success, {fail_count} failed")


if __name__ == '__main__':
    main()
