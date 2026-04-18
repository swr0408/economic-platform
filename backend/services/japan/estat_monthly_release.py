"""
e-Stat 毎月勤労統計調査 月次リリースファイル（概況）パーサー

月次リリースファイル（速報/確報）から前年比データを抽出する。
時系列コンパイルファイル（hon-t19.xls等）がe-Stat側で更新されるまでの間、
最新月のデータを補完するために使用する。

データソース: e-Stat 毎月勤労統計調査 概況Excel
URL: https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040187500&fileKind=4

Sheet 11（付表）カラムマッピング:
  c3:  現金給与総額 前年比 (%) - 全事業所
  c7:  所定内給与 前年比 (%) - 計
  c8:  所定内給与 前年比 (%) - 一般
  c9:  パート時間当たり 前年比 (%)
  c13: 実質賃金 前年比 (%) - 全事業所
  c15: 実質賃金 前年比 (%) - 共通事業所

Sheet 3（給与指数 - 所定内給与セクション）カラムマッピング:
  c9:  パート所定内給与 前年比 (%) - 全事業所
"""
import re
import requests
import pandas as pd
from typing import Dict, List, Any, Optional
from io import BytesIO
import logging

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

# 月次リリースファイルURL（概況Excel）
# パート時間当たり給与(Sheet 9)でも使用しているURL
MONTHLY_RELEASE_URL = "https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040187500&fileKind=4"

CACHE_KEY = "japan:employment:monthly_release_supplement:data"
CACHE_TTL = 86400  # 24 hours

# Sheet 11（付表）カラムインデックス
COL_CASH_EARNINGS = 3
COL_SCHEDULED_WAGE = 7
COL_GENERAL = 8
COL_PART_TIME_HOURLY = 9
COL_REAL_WAGE_ALL = 13
COL_REAL_WAGE_COMMON = 15


def get_monthly_release_supplement(force_refresh: bool = False) -> Optional[Dict[str, List[Dict[str, Any]]]]:
    """
    月次リリースファイルから補完データを取得

    Returns:
        {
            "cash_earnings": [{"date": "2026-02-01", "value": 3.3}, ...],
            "scheduled_wage": [...],
            "general": [...],
            "part_time_hourly": [...],
            "part_time_wage": [...],
            "real_wage_all": [...],
            "real_wage_common": [...],
        }
    """
    if not force_refresh:
        cached = redis_client.get(CACHE_KEY)
        if cached:
            logger.debug("Monthly release supplement loaded from Redis cache")
            return cached

    try:
        data = _download_and_parse()
        if data:
            redis_client.set(CACHE_KEY, data, expire=CACHE_TTL)
            logger.info("Monthly release supplement cached to Redis")
        return data
    except Exception as e:
        logger.error(f"Error getting monthly release supplement: {e}")
        return None


def _download_and_parse() -> Optional[Dict[str, List[Dict[str, Any]]]]:
    """月次リリースファイルをダウンロードしてSheet 11, Sheet 3を解析"""
    try:
        logger.info(f"Downloading monthly release file: {MONTHLY_RELEASE_URL}")
        response = requests.get(MONTHLY_RELEASE_URL, timeout=60)
        if response.status_code != 200:
            logger.error(f"Failed to download monthly release: {response.status_code}")
            return None

        content = BytesIO(response.content)

        # Sheet 11（付表）から主要系列を取得
        df11 = pd.read_excel(content, sheet_name=11, header=None)
        result = _parse_sheet11(df11)

        # Sheet 3（給与指数）からパート所定内給与を取得
        content.seek(0)
        df3 = pd.read_excel(content, sheet_name=3, header=None)
        part_time_wage = _parse_sheet3_part_time_wage(df3)
        if part_time_wage:
            result["part_time_wage"] = part_time_wage

        return result

    except Exception as e:
        logger.error(f"Error downloading/parsing monthly release: {e}")
        import traceback
        traceback.print_exc()
        return None


def _parse_period_rows(df: pd.DataFrame, period_col: int, start_row: int, end_row: int):
    """
    期間カラムから年月を解析するジェネレータ

    行構造:
    - "YYYY年" のみ → 年平均（スキップ）、current_year を更新
    - "YYYY年MM月" → 月次データ
    - "MM月" → 前行の年を継承した月次データ
    - "速報" プレフィックス → 最新速報値

    Yields:
        (row_index, year, month, row_data)
    """
    current_year = None
    # 全角数字→半角数字変換テーブル
    zenkaku_table = str.maketrans('０１２３４５６７８９', '0123456789')

    for i in range(start_row, min(end_row, len(df))):
        row = df.iloc[i]
        period = str(row[period_col]).strip() if pd.notna(row[period_col]) else ''

        if not period:
            continue

        # 全角スペース除去 + 全角数字を半角に変換
        period_clean = period.replace('\u3000', ' ').strip().translate(zenkaku_table)

        # 年を解析
        year_match = re.search(r'(\d{4})\s*年', period_clean)
        if year_match:
            current_year = int(year_match.group(1))

        # 月を解析
        month_match = re.search(r'(\d{1,2})\s*月', period_clean)
        if not month_match or not current_year:
            continue

        month = int(month_match.group(1))

        if current_year < 2000:
            continue

        yield i, current_year, month, row


def _parse_sheet11(df: pd.DataFrame) -> Dict[str, List[Dict[str, Any]]]:
    """Sheet 11（付表）を解析して前年比データを抽出"""
    col_map = {
        "cash_earnings": COL_CASH_EARNINGS,
        "scheduled_wage": COL_SCHEDULED_WAGE,
        "general": COL_GENERAL,
        "part_time_hourly": COL_PART_TIME_HOURLY,
        "real_wage_all": COL_REAL_WAGE_ALL,
        "real_wage_common": COL_REAL_WAGE_COMMON,
    }

    result = {key: [] for key in col_map}

    for _, year, month, row in _parse_period_rows(df, period_col=1, start_row=8, end_row=len(df)):
        date_str = f"{year}-{month:02d}-01"

        for key, col_idx in col_map.items():
            if col_idx >= len(df.columns):
                continue
            val = row[col_idx]
            if pd.notna(val) and val != '-' and val != '':
                try:
                    result[key].append({
                        "date": date_str,
                        "value": round(float(val), 1)
                    })
                except (ValueError, TypeError):
                    pass

    # ソート
    for key in result:
        result[key].sort(key=lambda x: x["date"])

    for key, data in result.items():
        if data:
            logger.info(f"Monthly release Sheet 11 [{key}]: {len(data)} points, "
                        f"latest={data[-1]}")

    return result


def _parse_sheet3_part_time_wage(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Sheet 3（給与指数）の所定内給与セクションからパート所定内給与前年比を取得

    Sheet 3 構造:
    - 前半（～row 44頃）: 現金給与総額セクション
    - 後半（row 45～）: 所定内給与セクション
      - c0: 年月
      - c3: 計 前年比
      - c6: 一般 前年比
      - c9: パートタイム 前年比 ← これを取得
    """
    # 所定内給与セクションの開始行を探す
    # 構造: 前半が現金給与総額、後半が所定内給与
    # 所定内給与セクションでは実質前年比(c4)が '－'(U+FF0D) で表示される
    shoteinai_start = None
    for i in range(30, min(70, len(df))):
        if not pd.notna(df.iloc[i, 0]):
            continue
        cell_str = str(df.iloc[i, 0]).replace('\u3000', ' ').strip()
        year_match = re.search(r'(\d{4})', cell_str)
        if not year_match:
            continue
        year = int(year_match.group(1))
        if 2020 <= year <= 2100 and shoteinai_start is None:
            c4 = df.iloc[i, 4] if 4 < len(df.columns) else None
            if pd.notna(c4) and isinstance(c4, str):
                # 所定内給与セクション: 実質前年比カラムが '－' (fullwidth hyphen U+FF0D)
                if '\uff0d' in c4 or '－' in c4:
                    shoteinai_start = i
                    break

    if shoteinai_start is None:
        logger.warning("Could not find 所定内給与 section in Sheet 3")
        return []

    logger.info(f"Sheet 3: 所定内給与 section starts at row {shoteinai_start}")

    result = []
    PART_TIME_WAGE_COL = 9  # パートタイム所定内給与 前年比

    for _, year, month, row in _parse_period_rows(df, period_col=0, start_row=shoteinai_start, end_row=len(df)):
        date_str = f"{year}-{month:02d}-01"

        if PART_TIME_WAGE_COL >= len(df.columns):
            continue
        val = row[PART_TIME_WAGE_COL]
        if pd.notna(val) and val != '-' and val != '':
            try:
                result.append({
                    "date": date_str,
                    "value": round(float(val), 1)
                })
            except (ValueError, TypeError):
                pass

    result.sort(key=lambda x: x["date"])

    if result:
        logger.info(f"Monthly release Sheet 3 [part_time_wage]: {len(result)} points, "
                    f"latest={result[-1]}")

    return result


def merge_supplement(
    base_data: List[Dict[str, Any]],
    supplement_data: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    ベースデータに補完データをマージ

    ベースデータに存在しない日付のみ補完データから追加する。
    （ベースデータ側が確報値の可能性があるため上書きしない）

    Args:
        base_data: 時系列ファイルからのデータ
        supplement_data: 月次リリースからの補完データ

    Returns:
        マージされたデータ（日付順）
    """
    if not supplement_data:
        return base_data

    if not base_data:
        return supplement_data

    existing_dates = {item["date"] for item in base_data}
    merged = list(base_data)

    added = 0
    for item in supplement_data:
        if item["date"] not in existing_dates:
            merged.append(item)
            added += 1

    if added > 0:
        merged.sort(key=lambda x: x["date"])
        logger.info(f"Supplemented {added} data points from monthly release")

    return merged
