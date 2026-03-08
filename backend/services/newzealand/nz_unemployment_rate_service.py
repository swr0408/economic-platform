"""
NZ 失業率サービス

指標:
- Unemployment Rate（失業率）- HLFQ.S1F3S（季節調整済み、Total）

データソース:
- Stats NZ Household Labour Force Survey (HLFS)
- https://www.stats.govt.nz/indicators/unemployment-rate/

取得方法:
- Stats NZ リリースページから Excel を直接ダウンロード
- Table 1 の「Total」セクション（Row 34-45付近）から失業率（Col 16）を取得
- 各Excelには約9四半期分のデータのみ含まれるため、過去のExcelも取得して長期データを構築

系列ID:
- S1F3S : Unemployment Rate (SA) (%)

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
DATA_CACHE_FILE = CACHE_DIR / "nz_unemployment_rate_cache.json"

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
                # "... will be published 6 May 2026." のパターン
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


class NzUnemploymentRateService:
    """NZ 失業率サービス"""

    DATA_CACHE_KEY = "newzealand:nz_unemployment_rate:data"

    def __init__(self):
        pass

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """NZ 失業率データを取得"""

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
                    "indicator": "Household Labour Force Survey - Unemployment Rate",
                    "description": "NZ 失業率（季節調整済み）",
                    "unit": "%",
                    "frequency": "quarterly",
                    "series": "HLFQ.S1F3S",
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
                print(f"[NzUnemployment] Downloaded {month_cap} {year} ({len(resp.content)} bytes)")
                return resp.content
        except Exception as e:
            print(f"[NzUnemployment] Error downloading {year} Q{qm // 3}: {e}")
        return None

    def _load_from_stats_nz(self) -> Tuple[Optional[List[Dict[str, Any]]], Optional[Dict[str, Any]]]:
        """Stats NZ HLFS Excelから失業率データを取得

        各Excelの Table 1「Total」セクションから失業率（Col 16 = S1F3S）を取得。
        各Excelに約9四半期分しかないため、過去のExcelも取得して長期データを構築する。

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
                print("[NzUnemployment] Failed to download latest HLFS Excel")
                return None, None

            # 2. 最新Excelから失業率データ取得
            all_data: Dict[str, Dict[str, Any]] = {}
            latest_data = self._parse_table1_unemployment(latest_excel)
            all_data.update(latest_data)

            # 3. Contentsシートから次回発表日を取得
            next_release = _parse_next_release_from_contents(latest_excel)

            # 4. 過去のExcelからも取得して長期データを構築
            #    各Excelに約9四半期分 → 2年間隔で取得すれば2016Q4まで遡れる
            historical_quarters = [
                (2022, 12), (2020, 12), (2018, 12),
                # 2016Q4 は Stats NZ から削除済み (404)
            ]
            for hist_year, hist_qm in historical_quarters:
                hist_excel = self._download_excel(hist_year, hist_qm)
                if hist_excel is None:
                    continue

                hist_data = self._parse_table1_unemployment(hist_excel)
                for date_str, entry in hist_data.items():
                    if date_str not in all_data:
                        all_data[date_str] = entry

            # 5. ソートしてリスト化
            result = [
                {"date": d, "value": all_data[d]["value"]}
                for d in sorted(all_data.keys())
            ]

            if result:
                print(f"[NzUnemployment] Total {len(result)} records")
                print(f"[NzUnemployment] Date range: {result[0]['date']} to {result[-1]['date']}")
                print(f"[NzUnemployment] Latest: {result[-1]['value']}%")
            if next_release:
                print(f"[NzUnemployment] Next release: {next_release.get('date')}")

            return result, next_release

        except Exception as e:
            print(f"[NzUnemployment] Error loading from Stats NZ: {e}")
            import traceback
            traceback.print_exc()
            return None, None

    def _parse_table1_unemployment(self, excel_bytes: bytes) -> Dict[str, Dict[str, Any]]:
        """Table 1 の「Total」セクションから失業率を取得

        Table 1 構造:
        - Row 34: "Total" ラベル
        - Row 35: Series ref（S1F3S が Col 16）
        - Row 36: "Quarter" ヘッダー
        - Row 37+: データ行（Year Col0, Quarter Col1, Unemployment Rate Col16）
        """
        try:
            df = pd.read_excel(io.BytesIO(excel_bytes), sheet_name='Table 1', header=None)
            data = {}

            # 「Total」セクションを探す
            total_row = None
            for row_idx in range(df.shape[0]):
                val = df.iloc[row_idx, 0]
                if pd.notna(val) and isinstance(val, str) and val.strip() == "Total":
                    total_row = row_idx
                    break

            if total_row is None:
                print("[NzUnemployment] 'Total' section not found in Table 1")
                return {}

            # データ行は Total + 3行目（Series ref, Quarter ヘッダーの後）から開始
            data_start = total_row + 3
            current_year = None

            for row_idx in range(data_start, df.shape[0]):
                # 年の取得
                year_val = df.iloc[row_idx, 0]
                if pd.notna(year_val):
                    year_str = str(year_val).strip()
                    if year_str.isdigit() and len(year_str) == 4:
                        current_year = year_str
                    elif not year_str[0].isdigit():
                        # 注釈行に到達 → セクション終了
                        break

                if current_year is None:
                    continue

                # 四半期の取得
                month_val = df.iloc[row_idx, 1]
                if pd.isna(month_val):
                    continue
                month_str = str(month_val).strip()

                date_str = _quarter_month_to_date(current_year, month_str)
                if date_str is None:
                    continue

                # 失業率（Col 16）
                unemp_val = df.iloc[row_idx, 16] if df.shape[1] > 16 else None
                if pd.isna(unemp_val):
                    continue
                try:
                    value = round(float(unemp_val), 1)
                except (ValueError, TypeError):
                    continue

                data[date_str] = {"value": value}

            print(f"[NzUnemployment] Table 1 Total: {len(data)} records")
            return data

        except Exception as e:
            print(f"[NzUnemployment] Error parsing Table 1: {e}")
            import traceback
            traceback.print_exc()
            return {}

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
            logger.error(f"[NzUnemployment] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[NzUnemployment] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None
        return {
            "indicator": "NZ Unemployment Rate (HLFS)",
            "source": "Stats NZ",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
nz_unemployment_rate_service = NzUnemploymentRateService()
