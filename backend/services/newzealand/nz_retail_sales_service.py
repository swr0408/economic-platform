"""
NZ 小売売上高サービス

指標:
- Total Retail Sales (Volume, SA) - RTTQ.SF91KS → QoQ%計算
- Core Retail Sales (Volume, SA) - RTTQ.SF11KS → QoQ%計算
- Total Retail Sales (Volume, Actual) - RTTQ.SF91KA → YoY%計算
- Core Retail Sales (Volume, Actual) - RTTQ.SF11KA → YoY%計算

データソース:
- Stats NZ Retail Trade Survey
- https://www.stats.govt.nz/topics/retail-and-wholesale-trade/

取得方法:
- Stats NZ リリースページから Excel を直接ダウンロード
- Table 4 (SA volumes): Row 22=Core(SF11KS), Row 25=Total(SF91KS) → QoQ%計算
- Table 2 (Actual volumes): Row 22=Core(SF11KA), Row 25=Total(SF91KA) → YoY%計算
- 各Excelには約9四半期分のデータのみ含まれるため、過去のExcelも取得して長期データを構築

発表スケジュール:
- 四半期ごと（ExcelのContentsシートから次回発表日取得）

キャッシュ方式:
- Redis + ファイルキャッシュ
"""
import hashlib
import json
import logging
import re
from collections import OrderedDict
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from zoneinfo import ZoneInfo
from pathlib import Path

import requests
import pandas as pd
import io


# Excel パース結果のキャッシュ。_load_from_stats_nz は同一 Excel の同一シートを
# 複数の行ぶん繰り返し読むため(1 load あたり ~16 回 read_excel)、(内容ハッシュ, シート名)で
# read_excel 結果を再利用し、同じワークブックを何度も再パース(高コスト・CPU占有で
# イベントループを飢えさせる)のを防ぐ。SWR バックグラウンド再取得が同じ Excel で再実行されても
# 再パースしない。read 専用 (呼び出し側は df を変更しない) のため共有して安全。
_EXCEL_DF_CACHE: "OrderedDict[tuple, pd.DataFrame]" = OrderedDict()
_EXCEL_DF_CACHE_MAX = 12


def _read_excel_cached(excel_bytes: bytes, sheet_name: str) -> pd.DataFrame:
    key = (hashlib.md5(excel_bytes).hexdigest(), sheet_name)
    df = _EXCEL_DF_CACHE.get(key)
    if df is None:
        df = pd.read_excel(io.BytesIO(excel_bytes), sheet_name=sheet_name, header=None)
        _EXCEL_DF_CACHE[key] = df
        if len(_EXCEL_DF_CACHE) > _EXCEL_DF_CACHE_MAX:
            _EXCEL_DF_CACHE.popitem(last=False)
    else:
        _EXCEL_DF_CACHE.move_to_end(key)
    return df

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "newzealand" / "consumer"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "nz_retail_sales_cache.json"

QUARTER_MONTHS = {
    3: ("March", "march"),
    6: ("June", "june"),
    9: ("September", "september"),
    12: ("December", "december"),
}

MONTH_MAP = {
    "Mar": "03", "Jun": "06", "Sep": "09", "Dec": "12",
}


def _build_retail_excel_url(year: int, quarter_month: int) -> str:
    """Retail Trade Survey Excel URLを生成"""
    month_cap, month_lower = QUARTER_MONTHS[quarter_month]
    return (
        f"https://www.stats.govt.nz/assets/Uploads/Retail-trade-survey/"
        f"Retail-trade-survey-{month_cap}-{year}-quarter/Download-data/"
        f"retail-trade-survey-{month_lower}-{year}-quarter.xlsx"
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
            if "will be released" in val.lower() or "will be published" in val.lower():
                match = re.search(r'(?:released|published)\s+(?:on\s+)?(\d{1,2}\s+\w+\s+\d{4})', val)
                if match:
                    date_str = match.group(1)
                    try:
                        dt = datetime.strptime(date_str, "%d %B %Y")
                        print(f"[NzRetail] Next release parsed: {dt.strftime('%Y-%m-%d')}")
                        return {
                            "date": dt.strftime("%Y-%m-%d"),
                            "label": val.strip(),
                        }
                    except ValueError:
                        pass
        return None
    except Exception as e:
        print(f"[NzRetail] Error parsing Contents for next release: {e}")
        return None


class NzRetailSalesService:
    """NZ 小売売上高サービス"""

    DATA_CACHE_KEY = "newzealand:nz_retail_sales:data"

    def __init__(self):
        pass

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """NZ 小売売上高データを取得"""

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
                    "indicator": "Retail Trade Survey",
                    "description": "NZ 小売売上高（実質・季節調整済み）",
                    "unit": "%",
                    "frequency": "quarterly",
                    "series": {
                        "total_qoq": "SF91KS (SA Volume) → QoQ%",
                        "core_qoq": "SF11KS (SA Volume) → QoQ%",
                        "total_yoy": "SF91KA (Actual Volume) → YoY%",
                        "core_yoy": "SF11KA (Actual Volume) → YoY%",
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

    def _discover_excel_url(self, year: int, qm: int) -> Optional[str]:
        """リリースページをスクレイピングして実際のExcel URLを取得"""
        _, month_lower = QUARTER_MONTHS[qm]
        release_url = (
            f"https://www.stats.govt.nz/information-releases/"
            f"retail-trade-survey-{month_lower}-{year}-quarter/"
        )
        try:
            resp = requests.get(release_url, timeout=30)
            if resp.status_code != 200:
                return None
            text = resp.text.replace("\\/", "/")
            links = re.findall(
                r'(/assets/Uploads/Retail-trade-survey/[^"&\s]+\.xlsx)',
                text
            )
            for link in links:
                if "deflator" not in link.lower() and month_lower in link.lower():
                    return f"https://www.stats.govt.nz{link}"
        except Exception as e:
            print(f"[NzRetail] Error discovering URL for {year} Q{qm // 3}: {e}")
        return None

    def _download_excel(self, year: int, qm: int) -> Optional[bytes]:
        """指定四半期のRetail Trade Excelをダウンロード"""
        # 1. リリースページから動的にURLを発見
        url = self._discover_excel_url(year, qm)
        if url:
            try:
                resp = requests.get(url, timeout=120)
                if resp.status_code == 200 and len(resp.content) > 50000:
                    month_cap, _ = QUARTER_MONTHS[qm]
                    print(f"[NzRetail] Downloaded {month_cap} {year} via release page ({len(resp.content)} bytes)")
                    return resp.content
            except Exception as e:
                print(f"[NzRetail] Error downloading discovered URL: {e}")

        # 2. フォールバック: 従来の固定URLパターン
        fallback_url = _build_retail_excel_url(year, qm)
        try:
            resp = requests.get(fallback_url, timeout=120)
            if resp.status_code == 200 and len(resp.content) > 50000:
                month_cap, _ = QUARTER_MONTHS[qm]
                print(f"[NzRetail] Downloaded {month_cap} {year} via fallback ({len(resp.content)} bytes)")
                return resp.content
        except Exception as e:
            print(f"[NzRetail] Error downloading {year} Q{qm // 3}: {e}")
        return None

    def _load_from_stats_nz(self) -> Tuple[Optional[List[Dict[str, Any]]], Optional[Dict[str, Any]]]:
        """Stats NZ Retail Trade Excelからデータを取得"""
        try:
            now = datetime.now(JST)
            attempts = self._get_quarter_attempts(now.year, now.month)

            # 1. 最新のExcelをダウンロード
            latest_excel = None
            for year, qm in attempts:
                latest_excel = self._download_excel(year, qm)
                if latest_excel:
                    break

            if latest_excel is None:
                print("[NzRetail] Failed to download latest Retail Trade Excel")
                return None, None

            # 2. SA volumes (Table 4) → QoQ%計算用
            sa_total: Dict[str, float] = {}
            sa_core: Dict[str, float] = {}

            # 3. Actual volumes (Table 2) → YoY%計算用
            actual_total: Dict[str, float] = {}
            actual_core: Dict[str, float] = {}

            # 最新Excelから取得
            t4 = self._parse_table_row_data(latest_excel, 'Table 4', 25)  # SF91KS
            t4_core = self._parse_table_row_data(latest_excel, 'Table 4', 22)  # SF11KS
            t2 = self._parse_table_row_data(latest_excel, 'Table 2', 25)  # SF91KA
            t2_core = self._parse_table_row_data(latest_excel, 'Table 2', 22)  # SF11KA

            sa_total.update(t4)
            sa_core.update(t4_core)
            actual_total.update(t2)
            actual_core.update(t2_core)

            # Contentsシートから次回発表日を取得
            next_release = _parse_next_release_from_contents(latest_excel)

            # 4. 過去のExcelからも取得
            historical_quarters = [
                (2023, 6), (2021, 6), (2019, 6),
            ]
            for hist_year, hist_qm in historical_quarters:
                hist_excel = self._download_excel(hist_year, hist_qm)
                if hist_excel is None:
                    continue

                for date_str, val in self._parse_table_row_data(hist_excel, 'Table 4', 25).items():
                    if date_str not in sa_total:
                        sa_total[date_str] = val
                for date_str, val in self._parse_table_row_data(hist_excel, 'Table 4', 22).items():
                    if date_str not in sa_core:
                        sa_core[date_str] = val
                for date_str, val in self._parse_table_row_data(hist_excel, 'Table 2', 25).items():
                    if date_str not in actual_total:
                        actual_total[date_str] = val
                for date_str, val in self._parse_table_row_data(hist_excel, 'Table 2', 22).items():
                    if date_str not in actual_core:
                        actual_core[date_str] = val

            # 5. QoQ% / YoY% を計算
            total_qoq = self._calc_qoq(sa_total)
            core_qoq = self._calc_qoq(sa_core)
            total_yoy = self._calc_yoy(actual_total)
            core_yoy = self._calc_yoy(actual_core)

            # 6. マージ
            all_dates = set()
            all_dates.update(total_qoq.keys())
            all_dates.update(core_qoq.keys())
            all_dates.update(total_yoy.keys())
            all_dates.update(core_yoy.keys())

            result = []
            for d in sorted(all_dates):
                entry = {
                    "date": d,
                    "total_qoq": total_qoq.get(d),
                    "core_qoq": core_qoq.get(d),
                    "total_yoy": total_yoy.get(d),
                    "core_yoy": core_yoy.get(d),
                }
                result.append(entry)

            if result:
                print(f"[NzRetail] Total {len(result)} records")
                print(f"[NzRetail] Date range: {result[0]['date']} to {result[-1]['date']}")
                latest = result[-1]
                if latest.get("total_qoq") is not None:
                    print(f"[NzRetail] Latest total QoQ: {latest['total_qoq']}%")
                if latest.get("total_yoy") is not None:
                    print(f"[NzRetail] Latest total YoY: {latest['total_yoy']}%")
            if next_release:
                print(f"[NzRetail] Next release: {next_release.get('date')}")

            return result, next_release

        except Exception as e:
            print(f"[NzRetail] Error loading from Stats NZ: {e}")
            import traceback
            traceback.print_exc()
            return None, None

    def _parse_table_row_data(self, excel_bytes: bytes, sheet_name: str, target_row: int) -> Dict[str, float]:
        """指定テーブルの指定行からデータを取得

        Excel構造:
        - Row 5: 年ヘッダー（Col 4, 10, 18... に年が入る）
        - Row 6: 四半期ヘッダー（偶数列に Jun/Sep/Dec/Mar）
        - target_row: データ行（偶数列に値）
        """
        try:
            df = _read_excel_cached(excel_bytes, sheet_name)
            result = {}

            # 年ヘッダーを解析（Row 5）
            year_map = {}  # col_idx -> year_str
            for c in range(4, df.shape[1]):
                val = df.iloc[5, c]
                if pd.notna(val):
                    year_str = str(val).strip()
                    if year_str.isdigit() and len(year_str) == 4:
                        year_map[c] = year_str

            # 各データ列を読み取り
            current_year = None
            for c in range(4, df.shape[1], 2):  # 偶数列のみ
                # 年の更新
                if c in year_map:
                    current_year = year_map[c]
                if current_year is None:
                    continue

                # 四半期の取得（Row 6）
                qtr_val = df.iloc[6, c]
                if pd.isna(qtr_val):
                    continue
                qtr_str = str(qtr_val).strip()

                date_str = _quarter_month_to_date(current_year, qtr_str)
                if date_str is None:
                    continue

                # 値の取得（target_row）
                data_val = df.iloc[target_row, c]
                if pd.isna(data_val):
                    continue
                try:
                    result[date_str] = float(data_val)
                except (ValueError, TypeError):
                    continue

            return result

        except Exception as e:
            print(f"[NzRetail] Error parsing {sheet_name} row {target_row}: {e}")
            return {}

    def _calc_qoq(self, level_data: Dict[str, float]) -> Dict[str, float]:
        """水準値から前期比（QoQ%）を計算"""
        sorted_dates = sorted(level_data.keys())
        result = {}

        for i in range(1, len(sorted_dates)):
            curr_date = sorted_dates[i]
            prev_date = sorted_dates[i - 1]

            # 前四半期かチェック（3ヶ月差）
            curr_parts = curr_date.split("-")
            prev_parts = prev_date.split("-")
            curr_m = int(curr_parts[1])
            prev_m = int(prev_parts[1])
            curr_y = int(curr_parts[0])
            prev_y = int(prev_parts[0])

            expected_prev_m = curr_m - 3
            expected_prev_y = curr_y
            if expected_prev_m <= 0:
                expected_prev_m += 12
                expected_prev_y -= 1

            if prev_y == expected_prev_y and prev_m == expected_prev_m:
                prev_val = level_data[prev_date]
                curr_val = level_data[curr_date]
                if prev_val > 0:
                    qoq = ((curr_val - prev_val) / prev_val) * 100
                    result[curr_date] = round(qoq, 1)

        return result

    def _calc_yoy(self, level_data: Dict[str, float]) -> Dict[str, float]:
        """水準値から前年比（YoY%）を計算"""
        result = {}

        for date_str, curr_val in level_data.items():
            parts = date_str.split("-")
            prev_year = int(parts[0]) - 1
            prev_date = f"{prev_year}-{parts[1]}-{parts[2]}"

            if prev_date in level_data:
                prev_val = level_data[prev_date]
                if prev_val > 0:
                    yoy = ((curr_val - prev_val) / prev_val) * 100
                    result[date_str] = round(yoy, 1)

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
            logger.error(f"[NzRetail] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[NzRetail] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None
        return {
            "indicator": "NZ Retail Sales",
            "source": "Stats NZ",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
nz_retail_sales_service = NzRetailSalesService()
