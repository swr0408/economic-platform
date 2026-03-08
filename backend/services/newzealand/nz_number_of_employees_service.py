"""
NZ 雇用者数サービス

指標:
- Total Employed（総雇用者数）- HLFQ.S1A3S
- Full-time Employed（フルタイム雇用者数）- HLFQ.S5GS
- Part-time Employed（パートタイム雇用者数）- HLFQ.S5HS

データソース:
- Stats NZ Household Labour Force Survey (HLFS)
- https://www.stats.govt.nz/indicators/?filters=Employment%20and%20unemployment

取得方法:
- Stats NZ リリースページから Excel を直接ダウンロード
- Table 11 から 総雇用者数 / フルタイム / パートタイム の原数値・QoQ%・YoY% を取得
- Table 7 から 総雇用者数の長期原数値・QoQ%・YoY% を取得
- Table 7 の長期データ + Table 11 のフルタイム/パートタイム短期データをマージ

系列ID:
- S1A3S  : Total Employed (SA) (000)
- S5GS   : Full-time Employed (SA) (000)
- S5HS   : Part-time Employed (SA) (000)

発表スケジュール:
- 四半期ごと（FMPから次回発表日取得）

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
DATA_CACHE_FILE = CACHE_DIR / "nz_number_of_employees_cache.json"

# Stats NZ HLFS Excel URL パターン
QUARTER_MONTHS = {
    3: ("March", "march"),
    6: ("June", "june"),
    9: ("September", "september"),
    12: ("December", "december"),
}


def _build_hlfs_excel_url(year: int, quarter_month: int) -> str:
    """Stats NZ HLFS Excel URLを生成"""
    month_cap, month_lower = QUARTER_MONTHS[quarter_month]
    return (
        f"https://www.stats.govt.nz/assets/Uploads/Labour-market-statistics/"
        f"Labour-market-statistics-{month_cap}-{year}-quarter/Download-data/"
        f"household-labour-force-survey-{month_lower}-{year}-quarter.xlsx"
    )


def _quarter_month_to_date(year_str: str, month_str: str) -> Optional[str]:
    """Year + Month abbreviation を日付文字列 (YYYY-MM-01) に変換"""
    month_map = {
        "Mar": "03", "Jun": "06", "Sep": "09", "Dec": "12",
    }
    month_num = month_map.get(month_str)
    if month_num:
        return f"{year_str}-{month_num}-01"
    return None


def _parse_next_release_from_contents(excel_bytes: bytes) -> Optional[Dict[str, Any]]:
    """HLFS Excel の Contents シートから次回発表日を解析

    Row 37: "Next release"
    Row 38: "Labour market statistics: March 2026 quarter will be published 6 May 2026."
    → 日付部分 "6 May 2026" を解析して返す
    """
    try:
        df = pd.read_excel(io.BytesIO(excel_bytes), sheet_name='Contents', header=None)
        for row_idx in range(df.shape[0]):
            val = df.iloc[row_idx, 0]
            if pd.isna(val) or not isinstance(val, str):
                continue
            if "will be published" in val.lower():
                match = re.search(r'published\s+(\d{1,2}\s+\w+\s+\d{4})', val)
                if match:
                    date_str = match.group(1)
                    try:
                        dt = datetime.strptime(date_str, "%d %B %Y")
                        print(f"[NzHLFS] Next release parsed: {dt.strftime('%Y-%m-%d')} from: {val.strip()}")
                        return {
                            "date": dt.strftime("%Y-%m-%d"),
                            "label": val.strip(),
                        }
                    except ValueError:
                        pass
        return None
    except Exception as e:
        print(f"[NzHLFS] Error parsing Contents for next release: {e}")
        return None


class NzNumberOfEmployeesService:
    """NZ 雇用者数サービス"""

    DATA_CACHE_KEY = "newzealand:nz_number_of_employees:data"

    def __init__(self):
        pass

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """NZ 雇用者数データを取得"""

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

        # Stats NZ ExcelからHLFSデータ取得
        result, next_release = self._load_from_stats_nz()
        if result:
            latest = result[-1] if result else None

            cache_payload = {
                "data": result,
                "latest": latest,
                "metadata": {
                    "source": "Stats NZ",
                    "indicator": "Household Labour Force Survey - Number of Employees",
                    "description": "NZ 雇用者数（総雇用者数・フルタイム・パートタイム）",
                    "unit": "千人",
                    "frequency": "quarterly",
                    "series_total": "HLFQ.S1A3S",
                    "series_fulltime": "HLFQ.S5GS",
                    "series_parttime": "HLFQ.S5HS",
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

    def _download_excel(self, year: int, qm: int) -> Optional[bytes]:
        """指定四半期のHLFS Excelをダウンロード"""
        url = _build_hlfs_excel_url(year, qm)
        try:
            resp = requests.get(url, timeout=120)
            if resp.status_code == 200 and len(resp.content) > 50000:
                month_cap, _ = QUARTER_MONTHS[qm]
                print(f"[NzEmployees] Downloaded {month_cap} {year} ({len(resp.content)} bytes)")
                return resp.content
        except Exception as e:
            print(f"[NzEmployees] Error downloading {year} Q{qm // 3}: {e}")
        return None

    def _load_from_stats_nz(self) -> Tuple[Optional[List[Dict[str, Any]]], Optional[Dict[str, Any]]]:
        """Stats NZ HLFS Excelから雇用者数データを取得

        最新Excelから Table 7（長期・総雇用者数のみ）と Table 11（短期・フルタイム/パートタイム含む）を取得。
        さらに過去のExcelからも Table 7 と Table 11 を取得して長期データを構築する。

        データ取得戦略:
        - Table 7: 各Excelに長期データあり（2018Q4 Excel → 2009年～）。過去Excelも取得して最古のデータを確保
        - Table 11: 各Excelに約9四半期分。過去Excelを複数取得してフルタイム/パートタイムの長期データを構築

        Returns:
            (data_list, next_release) のタプル
        """
        try:
            now = datetime.now(JST)
            attempts = self._get_quarter_attempts(now.year, now.month)

            # 1. 最新のHLFS Excelをダウンロード
            latest_excel = None
            for year, qm in attempts:
                latest_excel = self._download_excel(year, qm)
                if latest_excel:
                    break

            if latest_excel is None:
                print("[NzEmployees] Failed to download latest HLFS Excel")
                return None, None

            # 2. Table 7: 総雇用者数（長期データ）- 最新Excel
            table7_data = self._parse_table7(latest_excel)

            # 3. Table 11: フルタイム/パートタイム（最新Excel分）
            table11_combined = self._parse_table11(latest_excel)

            # 4. Contentsシートから次回発表日を取得
            next_release = _parse_next_release_from_contents(latest_excel)

            # 5. 過去のExcelからも Table 7 + Table 11 を取得して長期データを構築
            #    Table 7: 過去Excelの方が古い期間のデータを持っている（2018Q4 Excel → 2009年～）
            #    Table 11: 各Excelに約9四半期分のフルタイム/パートタイムデータ
            historical_quarters = [
                (2022, 12), (2020, 12), (2018, 12),
                # 2016Q4 は Stats NZ から削除済み (404)
            ]
            for hist_year, hist_qm in historical_quarters:
                hist_excel = self._download_excel(hist_year, hist_qm)
                if hist_excel is None:
                    continue

                # Table 7: 過去Excelからも総雇用者数の長期データを取得
                hist_table7 = self._parse_table7(hist_excel)
                for date_str, entry in hist_table7.items():
                    if date_str not in table7_data:
                        table7_data[date_str] = entry

                # Table 11: フルタイム/パートタイム補完
                hist_table11 = self._parse_table11(hist_excel)
                for date_str, entry in hist_table11.items():
                    if date_str not in table11_combined:
                        table11_combined[date_str] = entry

            # 6. マージ: Table 7 + Table 11
            result = self._merge_tables(table7_data, table11_combined)

            if result:
                print(f"[NzEmployees] Total {len(result)} records")
                print(f"[NzEmployees] Date range: {result[0]['date']} to {result[-1]['date']}")
                latest = result[-1]
                print(f"[NzEmployees] Latest: total={latest.get('total')}, "
                      f"fulltime={latest.get('fulltime')}, parttime={latest.get('parttime')}, "
                      f"total_qoq={latest.get('total_qoq')}%, total_yoy={latest.get('total_yoy')}%")
                # フルタイムデータの範囲を表示
                ft_dates = [r["date"] for r in result if r.get("fulltime") is not None]
                if ft_dates:
                    print(f"[NzEmployees] Fulltime data range: {ft_dates[0]} to {ft_dates[-1]} ({len(ft_dates)} records)")
            if next_release:
                print(f"[NzEmployees] Next release: {next_release.get('date')}")

            return result, next_release

        except Exception as e:
            print(f"[NzEmployees] Error loading from Stats NZ: {e}")
            import traceback
            traceback.print_exc()
            return None, None

    def _parse_table7(self, excel_bytes: bytes) -> Dict[str, Dict[str, Any]]:
        """Table 7 からデータを取得

        Table 7 構造:
        - Row 8: Series ref: HLFQ | S1A3S (Col 2) | ...
        - Row 9: Quarter
        - Row 10+: データ行（Year Col0, Month Col1, Total Col2, QoQ_abs Col4, QoQ% Col6, YoY_abs Col8, YoY% Col10）
        """
        try:
            df = pd.read_excel(io.BytesIO(excel_bytes), sheet_name='Table 7', header=None)
            data = {}
            current_year = None

            for row_idx in range(10, df.shape[0]):
                # 年の取得
                year_val = df.iloc[row_idx, 0]
                if pd.notna(year_val) and isinstance(year_val, (int, float, str)):
                    year_str = str(year_val).strip()
                    if year_str.isdigit() and len(year_str) == 4:
                        current_year = year_str

                if current_year is None:
                    continue

                # 月の取得
                month_val = df.iloc[row_idx, 1]
                if pd.isna(month_val):
                    continue
                month_str = str(month_val).strip()

                date_str = _quarter_month_to_date(current_year, month_str)
                if date_str is None:
                    continue

                # 原数値
                total_val = df.iloc[row_idx, 2]
                if pd.isna(total_val):
                    continue
                try:
                    total = float(total_val)
                except (ValueError, TypeError):
                    continue

                # QoQ%
                qoq_pct = None
                qoq_val = df.iloc[row_idx, 6] if df.shape[1] > 6 else None
                if pd.notna(qoq_val):
                    try:
                        qoq_pct = round(float(qoq_val), 1)
                    except (ValueError, TypeError):
                        pass

                # YoY%
                yoy_pct = None
                yoy_val = df.iloc[row_idx, 10] if df.shape[1] > 10 else None
                if pd.notna(yoy_val):
                    try:
                        yoy_pct = round(float(yoy_val), 1)
                    except (ValueError, TypeError):
                        pass

                data[date_str] = {
                    "total": round(total, 1),
                    "total_qoq": qoq_pct,
                    "total_yoy": yoy_pct,
                }

            print(f"[NzEmployees] Table 7: {len(data)} records")
            return data

        except Exception as e:
            print(f"[NzEmployees] Error parsing Table 7: {e}")
            import traceback
            traceback.print_exc()
            return {}

    def _parse_table11(self, excel_bytes: bytes) -> Dict[str, Dict[str, Any]]:
        """Table 11 からフルタイム/パートタイム + 原数値を取得

        Table 11 構造:
        - Row 9: Series ref: HLFQ | S5GS (Col 2) | S5HS (Col 4) | S1A3S (Col 6) | ...
        - Row 10: Quarter
        - Row 11+: 原数値データ行
        - Row 20 (approx): Percentage change from previous quarter
        - Row 22+: QoQ% データ行
        - Row 31 (approx): Percentage change from the same period of previous year
        - Row 33+: YoY% データ行
        """
        try:
            df = pd.read_excel(io.BytesIO(excel_bytes), sheet_name='Table 11', header=None)
            data = {}

            # セクション分割: 原数値、QoQ%、YoY%
            section_starts = {"raw": None, "qoq": None, "yoy": None}
            for row_idx in range(df.shape[0]):
                val = df.iloc[row_idx, 0]
                if pd.notna(val) and isinstance(val, str):
                    if "Quarter" in val and section_starts["raw"] is None:
                        section_starts["raw"] = row_idx + 1
                    elif "previous quarter" in val.lower():
                        section_starts["qoq"] = row_idx + 2  # "Quarter" ヘッダー行をスキップ
                    elif "previous year" in val.lower():
                        section_starts["yoy"] = row_idx + 2

            # 原数値セクションを解析
            raw_data = {}
            if section_starts["raw"]:
                end = section_starts.get("qoq", df.shape[0])
                if end:
                    end = end - 2  # "Percentage change..." 行の前まで
                raw_data = self._parse_section(df, section_starts["raw"], end,
                                               ["fulltime", "parttime", "total"])

            # QoQ% セクションを解析
            qoq_data = {}
            if section_starts["qoq"]:
                end = section_starts.get("yoy", df.shape[0])
                if end:
                    end = end - 2
                qoq_data = self._parse_section(df, section_starts["qoq"], end,
                                               ["fulltime_qoq", "parttime_qoq", "total_qoq"])

            # YoY% セクションを解析
            yoy_data = {}
            if section_starts["yoy"]:
                yoy_data = self._parse_section(df, section_starts["yoy"], df.shape[0],
                                               ["fulltime_yoy", "parttime_yoy", "total_yoy"])

            # マージ
            all_dates = sorted(set(list(raw_data.keys()) + list(qoq_data.keys()) + list(yoy_data.keys())))
            for date_str in all_dates:
                entry = {}
                if date_str in raw_data:
                    entry.update(raw_data[date_str])
                if date_str in qoq_data:
                    entry.update(qoq_data[date_str])
                if date_str in yoy_data:
                    entry.update(yoy_data[date_str])
                if entry:
                    data[date_str] = entry

            print(f"[NzEmployees] Table 11: {len(data)} records")
            return data

        except Exception as e:
            print(f"[NzEmployees] Error parsing Table 11: {e}")
            import traceback
            traceback.print_exc()
            return {}

    def _parse_section(
        self, df: pd.DataFrame, start_row: int, end_row: int,
        fields: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """Excel セクションからデータ行を解析

        fields: Col 2, Col 4, Col 6 に対応するフィールド名
        """
        data = {}
        current_year = None

        for row_idx in range(start_row, min(end_row, df.shape[0])):
            year_val = df.iloc[row_idx, 0]
            if pd.notna(year_val):
                year_str = str(year_val).strip()
                if year_str.isdigit() and len(year_str) == 4:
                    current_year = year_str
                elif not any(c.isdigit() for c in year_str[:4] if year_str[:4]):
                    # 注釈行に到達 → セクション終了
                    break

            if current_year is None:
                continue

            month_val = df.iloc[row_idx, 1]
            if pd.isna(month_val):
                continue
            month_str = str(month_val).strip()

            date_str = _quarter_month_to_date(current_year, month_str)
            if date_str is None:
                continue

            entry = {}
            for i, field in enumerate(fields):
                col_idx = 2 + i * 2  # Col 2, 4, 6
                val = df.iloc[row_idx, col_idx] if df.shape[1] > col_idx else None
                if pd.notna(val):
                    try:
                        entry[field] = round(float(val), 1)
                    except (ValueError, TypeError):
                        entry[field] = None
                else:
                    entry[field] = None

            if any(v is not None for v in entry.values()):
                data[date_str] = entry

        return data

    def _merge_tables(
        self,
        table7: Dict[str, Dict[str, Any]],
        table11: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Table 7（長期）と Table 11（フルタイム/パートタイム）をマージ"""
        all_dates = sorted(set(list(table7.keys()) + list(table11.keys())))

        result = []
        for date_str in all_dates:
            item: Dict[str, Any] = {"date": date_str}

            t7 = table7.get(date_str, {})
            t11 = table11.get(date_str, {})

            # 原数値: Table 11 を優先、なければ Table 7
            item["total"] = t11.get("total") or t7.get("total")
            item["fulltime"] = t11.get("fulltime")
            item["parttime"] = t11.get("parttime")

            # QoQ%: Table 11 を優先、なければ Table 7
            item["total_qoq"] = t11.get("total_qoq") or t7.get("total_qoq")
            item["fulltime_qoq"] = t11.get("fulltime_qoq")
            item["parttime_qoq"] = t11.get("parttime_qoq")

            # YoY%: Table 11 を優先、なければ Table 7
            item["total_yoy"] = t11.get("total_yoy") or t7.get("total_yoy")
            item["fulltime_yoy"] = t11.get("fulltime_yoy")
            item["parttime_yoy"] = t11.get("parttime_yoy")

            # total が存在するレコードのみ保持
            if item["total"] is not None:
                result.append(item)

        return result

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
            logger.error(f"[NzEmployees] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[NzEmployees] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None
        return {
            "indicator": "NZ Number of Employees (HLFS)",
            "source": "Stats NZ",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
nz_number_of_employees_service = NzNumberOfEmployeesService()
