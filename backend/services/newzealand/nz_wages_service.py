"""
NZ 賃金サービス

指標:
- All Salary and Wage Rates Index（全給与・賃金率指数）- LCIQ.SG53Z9
  Labour Cost Index Excel Table 1 から取得
- Average Hourly Earnings（平均時給）- QEMQ.SASZ9A
  Quarterly Employment Survey Excel Table 8 から取得

データソース:
- Stats NZ Labour Cost Index (LCI)
- Stats NZ Quarterly Employment Survey (QES)
- https://www.stats.govt.nz/information-releases/labour-market-statistics/

取得方法:
- Stats NZ リリースページから Excel を直接ダウンロード
- LCI: Table 1 の Block 3（All salary and wage rates including overtime）から SG53Z9 を取得
- QES: Table 8（Average hourly earnings by sector）から SASZ9A を取得
- 各Excelには限られた四半期分のデータのみ含まれるため、過去のExcelも取得して長期データを構築

系列ID:
- LCIQ.SG53Z9 : All salary and wage rates (incl overtime) index (Base: Jun 2009 = 1000)
- QEMQ.SASZ9A : Average hourly earnings – Ordinary time – Total ($)

発表スケジュール:
- 四半期ごと（ExcelのContentsシートから次回発表日取得）

キャッシュ方式:
- Redis + ファイルキャッシュ
"""
import json
import logging
import re
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from zoneinfo import ZoneInfo
from pathlib import Path

import requests
import pandas as pd
import io

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "newzealand" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "nz_wages_cache.json"

QUARTER_MONTHS = {
    3: ("March", "march"),
    6: ("June", "june"),
    9: ("September", "september"),
    12: ("December", "december"),
}

MONTH_MAP = {
    "Mar": "03", "Jun": "06", "Sep": "09", "Dec": "12",
}


def _build_lci_excel_url(year: int, quarter_month: int) -> str:
    """Labour Cost Index Excel URLを生成"""
    month_cap, month_lower = QUARTER_MONTHS[quarter_month]
    return (
        f"https://www.stats.govt.nz/assets/Uploads/Labour-market-statistics/"
        f"Labour-market-statistics-{month_cap}-{year}-quarter/Download-data/"
        f"labour-cost-index-salary-and-wage-rates-{month_lower}-{year}-quarter.xlsx"
    )


def _build_qes_excel_url(year: int, quarter_month: int) -> str:
    """Quarterly Employment Survey Excel URLを生成"""
    month_cap, month_lower = QUARTER_MONTHS[quarter_month]
    return (
        f"https://www.stats.govt.nz/assets/Uploads/Labour-market-statistics/"
        f"Labour-market-statistics-{month_cap}-{year}-quarter/Download-data/"
        f"quarterly-employment-survey-{month_lower}-{year}-quarter.xlsx"
    )


def _quarter_month_to_date(year_str: str, month_str: str) -> Optional[str]:
    """Year + Month abbreviation を日付文字列 (YYYY-MM-01) に変換"""
    month_num = MONTH_MAP.get(month_str)
    if month_num:
        return f"{year_str}-{month_num}-01"
    return None


def _parse_next_release_from_contents(excel_bytes: bytes) -> Optional[Dict[str, Any]]:
    """Excel の Contents シートから次回発表日を解析"""
    try:
        df = pd.read_excel(io.BytesIO(excel_bytes), sheet_name='Contents', header=None)
        for row_idx in range(df.shape[0]):
            val = df.iloc[row_idx, 0]
            if pd.isna(val) or not isinstance(val, str):
                continue
            if "will be published" in val.lower() or "will be released" in val.lower():
                match = re.search(r'(?:published|released)\s+(?:on\s+)?(\d{1,2}\s+\w+\s+\d{4})', val)
                if match:
                    date_str = match.group(1)
                    try:
                        dt = datetime.strptime(date_str, "%d %B %Y")
                        print(f"[NzWages] Next release parsed: {dt.strftime('%Y-%m-%d')} from: {val.strip()}")
                        return {
                            "date": dt.strftime("%Y-%m-%d"),
                            "label": val.strip(),
                        }
                    except ValueError:
                        pass
        return None
    except Exception as e:
        print(f"[NzWages] Error parsing Contents for next release: {e}")
        return None


class NzWagesService:
    """NZ 賃金サービス（LCI + QES）"""

    DATA_CACHE_KEY = "newzealand:nz_wages:data"

    def __init__(self):
        pass

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """NZ 賃金データを取得"""

        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": cached_data.get("next_release"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # Stats NZ Excelからデータ取得
        result, next_release = self._load_from_stats_nz()
        if result:
            latest = result[-1] if result else None

            cache_payload = {
                "data": result,
                "latest": latest,
                "metadata": {
                    "source": "Stats NZ",
                    "indicator": "Labour Cost Index + Quarterly Employment Survey",
                    "description": "NZ 全給与・賃金率指数 + 平均時給",
                    "frequency": "quarterly",
                    "series": {
                        "wage_index": "LCIQ.SG53Z9 (Base: Jun 2009 = 1000)",
                        "hourly_earnings": "QEMQ.SASZ9A ($ per hour)",
                    },
                },
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": result,
                "latest": latest,
                "metadata": cache_payload["metadata"],
                "next_release": next_release,
                "cached": False,
                "source": "stats_nz",
                "last_updated": datetime.now(JST).isoformat(),
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "metadata": file_cache.get("metadata", {}),
                "next_release": file_cache.get("next_release"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "data": [],
            "latest": None,
            "metadata": {},
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
        }

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきか判定（1日1回）"""
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            now = datetime.now(JST)
            return (now - last_updated).total_seconds() > 86400
        except Exception:
            return True

    def _download_excel(self, url: str, label: str) -> Optional[bytes]:
        """Excelをダウンロード"""
        try:
            resp = requests.get(url, timeout=120)
            if resp.status_code == 200 and len(resp.content) > 50000:
                print(f"[NzWages] Downloaded {label} ({len(resp.content)} bytes)")
                return resp.content
        except Exception as e:
            print(f"[NzWages] Error downloading {label}: {e}")
        return None

    def _load_from_stats_nz(self) -> Tuple[Optional[List[Dict[str, Any]]], Optional[Dict[str, Any]]]:
        """Stats NZ Excelからデータを取得

        Returns:
            (data_list, next_release) のタプル
        """
        try:
            now = datetime.now(JST)
            attempts = self._get_quarter_attempts(now.year, now.month)

            # 1. LCI データ取得
            lci_data = self._load_lci_data(attempts)

            # 2. QES データ取得
            qes_data, next_release = self._load_qes_data(attempts)

            if not lci_data and not qes_data:
                print("[NzWages] Failed to load both LCI and QES data")
                return None, None

            # 3. マージ（日付ベース）
            all_dates = set()
            if lci_data:
                all_dates.update(lci_data.keys())
            if qes_data:
                all_dates.update(qes_data.keys())

            result = []
            for date_str in sorted(all_dates):
                lci = lci_data.get(date_str, {}) if lci_data else {}
                qes = qes_data.get(date_str, {}) if qes_data else {}

                entry = {
                    "date": date_str,
                    "wage_index": lci.get("value"),
                    "wage_index_qoq": lci.get("qoq"),
                    "wage_index_yoy": lci.get("yoy"),
                    "hourly_earnings": qes.get("value"),
                    "hourly_earnings_qoq": qes.get("qoq"),
                    "hourly_earnings_yoy": qes.get("yoy"),
                }
                result.append(entry)

            if result:
                print(f"[NzWages] Total {len(result)} records")
                print(f"[NzWages] Date range: {result[0]['date']} to {result[-1]['date']}")
                latest = result[-1]
                if latest.get("wage_index") is not None:
                    print(f"[NzWages] Latest wage_index: {latest['wage_index']}")
                if latest.get("hourly_earnings") is not None:
                    print(f"[NzWages] Latest hourly_earnings: ${latest['hourly_earnings']}")

            return result, next_release

        except Exception as e:
            print(f"[NzWages] Error loading from Stats NZ: {e}")
            import traceback
            traceback.print_exc()
            return None, None

    # =========================================================================
    # LCI（Labour Cost Index）解析
    # =========================================================================

    def _load_lci_data(self, attempts: List[tuple]) -> Optional[Dict[str, Dict[str, Any]]]:
        """LCI Excelから全給与・賃金率指数を取得"""
        all_data: Dict[str, Dict[str, Any]] = {}

        # 最新のLCI Excelをダウンロード
        latest_excel = None
        for year, qm in attempts:
            url = _build_lci_excel_url(year, qm)
            label = f"LCI {QUARTER_MONTHS[qm][0]} {year}"
            latest_excel = self._download_excel(url, label)
            if latest_excel:
                break

        if latest_excel is None:
            print("[NzWages] Failed to download latest LCI Excel")
            return None

        # 最新Excelから取得
        latest_data = self._parse_lci_table1(latest_excel)
        all_data.update(latest_data)

        # 過去のExcelからも取得（5Qずつなので2年間隔）
        lci_historical = [
            (2023, 9), (2021, 9), (2019, 6),
        ]
        for hist_year, hist_qm in lci_historical:
            url = _build_lci_excel_url(hist_year, hist_qm)
            label = f"LCI {QUARTER_MONTHS[hist_qm][0]} {hist_year}"
            hist_excel = self._download_excel(url, label)
            if hist_excel is None:
                continue
            hist_data = self._parse_lci_table1(hist_excel)
            for date_str, entry in hist_data.items():
                if date_str not in all_data:
                    all_data[date_str] = entry

        print(f"[NzWages] LCI total: {len(all_data)} records")
        return all_data if all_data else None

    def _parse_lci_table1(self, excel_bytes: bytes) -> Dict[str, Dict[str, Any]]:
        """LCI Table 1 から SG53Z9 (All salary and wage rates incl overtime) を取得

        Table 1 構造:
        - シート名に先頭スペースあり: " Table 1"
        - SG53Z9 は Col 11 にある
        - Block 3 にインデックス / QoQ% / YoY% が3セクションに分かれている
        - 各セクション5データ行
        """
        try:
            df = pd.read_excel(io.BytesIO(excel_bytes), sheet_name=' Table 1', header=None)
            data: Dict[str, Dict[str, Any]] = {}

            # SG53Z9 のある行を見つける（Col 11）
            sg53_row = None
            for row_idx in range(df.shape[0]):
                val = df.iloc[row_idx, 11] if df.shape[1] > 11 else None
                if pd.notna(val) and isinstance(val, str) and "SG53Z9" in val:
                    sg53_row = row_idx
                    break

            if sg53_row is None:
                print("[NzWages] SG53Z9 not found in LCI Table 1")
                return {}

            # インデックス値セクション: sg53_row + 3 から開始
            index_data = self._parse_lci_section(df, sg53_row + 3)

            # QoQ%セクション: インデックスの後
            # "Percentage change from previous quarter" の行を探す
            qoq_start = None
            for row_idx in range(sg53_row + 3, min(sg53_row + 20, df.shape[0])):
                val = df.iloc[row_idx, 0]
                if pd.notna(val) and isinstance(val, str) and "previous quarter" in val.lower():
                    # データは2行後（"Quarter"ヘッダーの次）
                    qoq_start = row_idx + 2
                    break

            qoq_data = self._parse_lci_section(df, qoq_start) if qoq_start else {}

            # YoY%セクション: QoQ%の後
            yoy_start = None
            search_from = qoq_start + 1 if qoq_start else sg53_row + 10
            for row_idx in range(search_from, min(search_from + 15, df.shape[0])):
                val = df.iloc[row_idx, 0]
                if pd.notna(val) and isinstance(val, str) and "previous year" in val.lower():
                    yoy_start = row_idx + 2
                    break

            yoy_data = self._parse_lci_section(df, yoy_start) if yoy_start else {}

            # マージ
            all_dates = set(index_data.keys()) | set(qoq_data.keys()) | set(yoy_data.keys())
            for date_str in all_dates:
                data[date_str] = {
                    "value": index_data.get(date_str),
                    "qoq": qoq_data.get(date_str),
                    "yoy": yoy_data.get(date_str),
                }

            print(f"[NzWages] LCI Table 1: {len(data)} records parsed")
            return data

        except Exception as e:
            print(f"[NzWages] Error parsing LCI Table 1: {e}")
            import traceback
            traceback.print_exc()
            return {}

    def _parse_lci_section(self, df: pd.DataFrame, start_row: Optional[int]) -> Dict[str, float]:
        """LCI Table 1 の1セクション（インデックス/QoQ%/YoY%）からデータを取得

        Col 0: Year（前方フィル必要）
        Col 2: Quarter month (Mar/Jun/Sep/Dec)
        Col 11: SG53Z9 の値
        """
        if start_row is None:
            return {}

        result = {}
        current_year = None

        for row_idx in range(start_row, min(start_row + 10, df.shape[0])):
            # 年の取得
            year_val = df.iloc[row_idx, 0]
            if pd.notna(year_val):
                year_str = str(year_val).strip()
                if year_str.isdigit() and len(year_str) == 4:
                    current_year = year_str
                elif not year_str[0].isdigit():
                    break  # セクション終了

            if current_year is None:
                continue

            # 四半期の取得
            month_val = df.iloc[row_idx, 2]
            if pd.isna(month_val):
                continue
            month_str = str(month_val).strip()

            date_str = _quarter_month_to_date(current_year, month_str)
            if date_str is None:
                continue

            # 値（Col 11）
            val = df.iloc[row_idx, 11] if df.shape[1] > 11 else None
            if pd.isna(val):
                continue
            try:
                result[date_str] = round(float(val), 2)
            except (ValueError, TypeError):
                continue

        return result

    # =========================================================================
    # QES（Quarterly Employment Survey）解析
    # =========================================================================

    def _load_qes_data(self, attempts: List[tuple]) -> Tuple[Optional[Dict[str, Dict[str, Any]]], Optional[Dict[str, Any]]]:
        """QES Excelから平均時給を取得

        Returns:
            (data_dict, next_release) のタプル
        """
        all_data: Dict[str, Dict[str, Any]] = {}
        next_release = None

        # 最新のQES Excelをダウンロード
        latest_excel = None
        for year, qm in attempts:
            url = _build_qes_excel_url(year, qm)
            label = f"QES {QUARTER_MONTHS[qm][0]} {year}"
            latest_excel = self._download_excel(url, label)
            if latest_excel:
                break

        if latest_excel is None:
            print("[NzWages] Failed to download latest QES Excel")
            return None, None

        # 最新Excelから取得
        latest_data = self._parse_qes_table8(latest_excel)
        all_data.update(latest_data)

        # Contentsシートから次回発表日を取得
        next_release = _parse_next_release_from_contents(latest_excel)

        # 過去のExcelからも取得（9Qずつなので約2年間隔）
        qes_historical = [
            (2023, 3), (2021, 9), (2019, 6), (2018, 12),
        ]
        for hist_year, hist_qm in qes_historical:
            url = _build_qes_excel_url(hist_year, hist_qm)
            label = f"QES {QUARTER_MONTHS[hist_qm][0]} {hist_year}"
            hist_excel = self._download_excel(url, label)
            if hist_excel is None:
                continue
            hist_data = self._parse_qes_table8(hist_excel)
            for date_str, entry in hist_data.items():
                if date_str not in all_data:
                    all_data[date_str] = entry

        print(f"[NzWages] QES total: {len(all_data)} records")
        return (all_data if all_data else None), next_release

    def _parse_qes_table8(self, excel_bytes: bytes) -> Dict[str, Dict[str, Any]]:
        """QES Table 8 から SASZ9A (Average hourly earnings - Ordinary time - Total) を取得

        Table 8 構造:
        - Row 8: Series ref（SASZ9A は Col 16）
        - セクション1（ドル値）: Row 12-21 付近（9データ行）
        - セクション2（YoY%）: Row 25-34 付近
        - セクション3（QoQ%）: Row 38-47 付近
        """
        try:
            df = pd.read_excel(io.BytesIO(excel_bytes), sheet_name='Table 8', header=None)
            data: Dict[str, Dict[str, Any]] = {}

            # SASZ9A の列を動的に検索（通常 Col 16）
            target_col = None
            for row_idx in range(min(15, df.shape[0])):
                for col_idx in range(df.shape[1]):
                    val = df.iloc[row_idx, col_idx]
                    if pd.notna(val) and isinstance(val, str) and "SASZ9A" in val:
                        target_col = col_idx
                        break
                if target_col is not None:
                    break

            if target_col is None:
                print("[NzWages] SASZ9A not found in QES Table 8")
                return {}

            # 3つのセクションを解析
            # セクション1: ドル値 - "($)" または "Quarter" の後
            level_start = None
            for row_idx in range(8, min(20, df.shape[0])):
                val = df.iloc[row_idx, 0]
                if pd.notna(val) and isinstance(val, str) and "Quarter" in val:
                    level_start = row_idx + 1
                    break
                # Col 2 or Col 3 を確認（"Quarter"がCol 0以外にある場合）
                for c in range(min(4, df.shape[1])):
                    cv = df.iloc[row_idx, c]
                    if pd.notna(cv) and isinstance(cv, str) and "Quarter" in str(cv):
                        level_start = row_idx + 1
                        break
                if level_start is not None:
                    break

            if level_start is None:
                level_start = 13  # フォールバック

            level_data = self._parse_qes_section(df, level_start, target_col)

            # セクション2: YoY% - "same quarter of previous year" の後
            yoy_start = None
            for row_idx in range(level_start, min(level_start + 20, df.shape[0])):
                val = df.iloc[row_idx, 0]
                if pd.notna(val) and isinstance(val, str) and "previous year" in val.lower():
                    # "Quarter"ヘッダーの次からデータ
                    for r2 in range(row_idx + 1, min(row_idx + 3, df.shape[0])):
                        v2 = df.iloc[r2, 0]
                        if pd.isna(v2):
                            continue
                        v2s = str(v2).strip()
                        if "Quarter" in v2s:
                            yoy_start = r2 + 1
                            break
                        if v2s.isdigit() and len(v2s) == 4:
                            yoy_start = r2
                            break
                    if yoy_start is None:
                        yoy_start = row_idx + 2
                    break

            yoy_data = self._parse_qes_section(df, yoy_start, target_col) if yoy_start else {}

            # セクション3: QoQ% - "previous quarter" の後
            qoq_start = None
            search_from = yoy_start + 1 if yoy_start else level_start + 15
            for row_idx in range(search_from, min(search_from + 20, df.shape[0])):
                val = df.iloc[row_idx, 0]
                if pd.notna(val) and isinstance(val, str) and "previous quarter" in val.lower():
                    for r2 in range(row_idx + 1, min(row_idx + 3, df.shape[0])):
                        v2 = df.iloc[r2, 0]
                        if pd.isna(v2):
                            continue
                        v2s = str(v2).strip()
                        if "Quarter" in v2s:
                            qoq_start = r2 + 1
                            break
                        if v2s.isdigit() and len(v2s) == 4:
                            qoq_start = r2
                            break
                    if qoq_start is None:
                        qoq_start = row_idx + 2
                    break

            qoq_data = self._parse_qes_section(df, qoq_start, target_col) if qoq_start else {}

            # マージ
            all_dates = set(level_data.keys()) | set(qoq_data.keys()) | set(yoy_data.keys())
            for date_str in all_dates:
                data[date_str] = {
                    "value": level_data.get(date_str),
                    "qoq": qoq_data.get(date_str),
                    "yoy": yoy_data.get(date_str),
                }

            print(f"[NzWages] QES Table 8: {len(data)} records parsed")
            return data

        except Exception as e:
            print(f"[NzWages] Error parsing QES Table 8: {e}")
            import traceback
            traceback.print_exc()
            return {}

    def _parse_qes_section(self, df: pd.DataFrame, start_row: Optional[int], target_col: int) -> Dict[str, float]:
        """QES Table 8 の1セクション（ドル値/QoQ%/YoY%）からデータを取得

        Col 0: Year（前方フィル必要）
        Col 2: Quarter month (Mar/Jun/Sep/Dec)
        target_col: SASZ9A の値
        """
        if start_row is None:
            return {}

        result = {}
        current_year = None

        for row_idx in range(start_row, min(start_row + 15, df.shape[0])):
            # 年の取得（Col 0）
            year_val = df.iloc[row_idx, 0]
            if pd.notna(year_val):
                year_str = str(year_val).strip()
                if year_str.isdigit() and len(year_str) == 4:
                    current_year = year_str
                elif not year_str[0].isdigit():
                    break  # セクション終了（注釈行等）

            if current_year is None:
                continue

            # 四半期の取得（Col 2）
            month_val = df.iloc[row_idx, 2]
            if pd.isna(month_val):
                continue
            month_str = str(month_val).strip()

            date_str = _quarter_month_to_date(current_year, month_str)
            if date_str is None:
                continue

            # 値
            val = df.iloc[row_idx, target_col] if df.shape[1] > target_col else None
            if pd.isna(val):
                continue
            try:
                result[date_str] = round(float(val), 2)
            except (ValueError, TypeError):
                continue

        return result

    # =========================================================================
    # ユーティリティ
    # =========================================================================

    def _get_quarter_attempts(self, year: int, month: int) -> List[tuple]:
        """ダウンロード試行する四半期リスト（最新から過去3四半期分）"""
        quarter_months = [12, 9, 6, 3]
        attempts = []

        current_qm = None
        for qm in quarter_months:
            if month >= qm:
                current_qm = qm
                break

        if current_qm is None:
            current_qm = 12
            year -= 1

        y, qm = year, current_qm
        for _ in range(3):
            attempts.append((y, qm))
            idx = quarter_months.index(qm)
            if idx + 1 < len(quarter_months):
                qm = quarter_months[idx + 1]
            else:
                qm = quarter_months[0]
                y -= 1

        return attempts

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"[NzWages] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[NzWages] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None
        return {
            "indicator": "NZ Wages (LCI + QES)",
            "source": "Stats NZ",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
nz_wages_service = NzWagesService()
