"""
NZ GDP成長率サービス

指標:
- GDP Growth Rate QoQ% (生産ベース、季節調整済み実質連鎖)
- GDP Growth Rate YoY% (生産ベース、同四半期前年比)

データソース:
- Stats NZ Gross Domestic Product
- https://www.stats.govt.nz/indicators/gross-domestic-product-gdp/

取得方法:
- Stats NZ GDP リリースの supplementary-tables Excel をダウンロード
- Table 11: QoQ% (Col 3 = SG01RSC00B01 SA chain-volume)
- Table 10: YoY% (Col 5 = SNEQ.SG01RSC00B01 same-quarter-previous-year)
- 各Excelには約38年分のデータ含まれるため、最新1ファイルで十分

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

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "newzealand" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "nz_gdp_growth_rate_cache.json"

QUARTER_MONTHS = {
    3: ("March", "march"),
    6: ("June", "june"),
    9: ("September", "september"),
    12: ("December", "december"),
}

MONTH_MAP = {
    "Mar": "03", "Jun": "06", "Sep": "09", "Dec": "12",
}


def _build_gdp_excel_url(year: int, quarter_month: int) -> str:
    """GDP supplementary tables Excel URLを生成"""
    month_cap, month_lower = QUARTER_MONTHS[quarter_month]
    return (
        f"https://www.stats.govt.nz/assets/Uploads/Gross-domestic-product/"
        f"Gross-domestic-product-{month_cap}-{year}-quarter/Download-data/"
        f"gross-domestic-product-{month_lower}-{year}-quarter-supplementary-tables.xlsx"
    )


def _quarter_month_to_date(year_str: str, month_str: str) -> Optional[str]:
    """Year + Quarter abbreviation を日付文字列 (YYYY-MM-01) に変換"""
    month_num = MONTH_MAP.get(month_str)
    if month_num:
        return f"{year_str}-{month_num}-01"
    return None


class NzGdpGrowthRateService:
    """NZ GDP成長率サービス"""

    DATA_CACHE_KEY = "newzealand:nz_gdp_growth_rate:data"

    def __init__(self):
        pass

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """NZ GDP成長率データを取得"""

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
                    "indicator": "Gross Domestic Product",
                    "description": "NZ GDP成長率（生産ベース、実質連鎖）",
                    "unit": "%",
                    "frequency": "quarterly",
                    "series": {
                        "qoq": "SG01RSC00B01 (SA chain-volume) → QoQ%",
                        "yoy": "SNEQ.SG01RSC00B01 (Actual) → Same-quarter YoY%",
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
            f"gross-domestic-product-{month_lower}-{year}-quarter/"
        )
        try:
            resp = requests.get(release_url, timeout=30)
            if resp.status_code != 200:
                return None
            text = resp.text.replace("\\/", "/")
            links = re.findall(
                r'(/assets/Uploads/Gross-domestic-product/[^"&\s]+supplementary-tables\.xlsx)',
                text
            )
            if links:
                return f"https://www.stats.govt.nz{links[0]}"
        except Exception as e:
            print(f"[NzGDP] Error discovering URL for {year} Q{qm // 3}: {e}")
        return None

    def _download_excel(self, year: int, qm: int) -> Optional[bytes]:
        """指定四半期のGDP Excelをダウンロード"""
        # 1. リリースページから動的にURLを発見
        url = self._discover_excel_url(year, qm)
        if url:
            try:
                resp = requests.get(url, timeout=120)
                if resp.status_code == 200 and len(resp.content) > 50000:
                    month_cap, _ = QUARTER_MONTHS[qm]
                    print(f"[NzGDP] Downloaded {month_cap} {year} via release page ({len(resp.content)} bytes)")
                    return resp.content
            except Exception as e:
                print(f"[NzGDP] Error downloading discovered URL: {e}")

        # 2. フォールバック: 固定URLパターン
        fallback_url = _build_gdp_excel_url(year, qm)
        try:
            resp = requests.get(fallback_url, timeout=120)
            if resp.status_code == 200 and len(resp.content) > 50000:
                month_cap, _ = QUARTER_MONTHS[qm]
                print(f"[NzGDP] Downloaded {month_cap} {year} via fallback ({len(resp.content)} bytes)")
                return resp.content
        except Exception as e:
            print(f"[NzGDP] Error downloading {year} Q{qm // 3}: {e}")
        return None

    def _load_from_stats_nz(self) -> Tuple[Optional[List[Dict[str, Any]]], Optional[Dict[str, Any]]]:
        """Stats NZ GDP Excelからデータを取得"""
        try:
            now = datetime.now(JST)
            attempts = self._get_quarter_attempts(now.year, now.month)

            # 最新のExcelをダウンロード
            latest_excel = None
            for year, qm in attempts:
                latest_excel = self._download_excel(year, qm)
                if latest_excel:
                    break

            if latest_excel is None:
                print("[NzGDP] Failed to download GDP Excel")
                return None, None

            # Table 11: QoQ% (Col 3)
            qoq_data = self._parse_growth_table(latest_excel, 'Table 11', target_col=3, data_start_row=10)

            # Table 10: YoY% - same-quarter-previous-year (Col 5)
            yoy_data = self._parse_growth_table(latest_excel, 'Table 10', target_col=5, data_start_row=9)

            # Contentsシートから次回発表日を取得
            next_release = self._parse_next_release(latest_excel)

            # マージ
            all_dates = set()
            all_dates.update(qoq_data.keys())
            all_dates.update(yoy_data.keys())

            result = []
            for d in sorted(all_dates):
                entry = {
                    "date": d,
                    "qoq": qoq_data.get(d),
                    "yoy": yoy_data.get(d),
                }
                # QoQもYoYもNoneの場合はスキップ
                if entry["qoq"] is not None or entry["yoy"] is not None:
                    result.append(entry)

            if result:
                print(f"[NzGDP] Total {len(result)} records")
                print(f"[NzGDP] Date range: {result[0]['date']} to {result[-1]['date']}")
                latest = result[-1]
                if latest.get("qoq") is not None:
                    print(f"[NzGDP] Latest QoQ: {latest['qoq']}%")
                if latest.get("yoy") is not None:
                    print(f"[NzGDP] Latest YoY: {latest['yoy']}%")
            if next_release:
                print(f"[NzGDP] Next release: {next_release.get('date')}")

            return result, next_release

        except Exception as e:
            print(f"[NzGDP] Error loading from Stats NZ: {e}")
            import traceback
            traceback.print_exc()
            return None, None

    def _parse_growth_table(
        self,
        excel_bytes: bytes,
        sheet_name: str,
        target_col: int,
        data_start_row: int,
    ) -> Dict[str, float]:
        """GDPテーブルから成長率データを取得

        Excel構造:
        - Col 0: 年（各年の最初の四半期のみ、他はNaN → forward fill）
        - Col 2: 四半期名（Mar, Jun, Sep, Dec）
        - target_col: 成長率値（文字列、'..'はデータなし）
        """
        try:
            df = pd.read_excel(io.BytesIO(excel_bytes), sheet_name=sheet_name, header=None)
            result = {}

            current_year = None

            for row_idx in range(data_start_row, df.shape[0]):
                # 年の更新（Col 0）
                year_val = df.iloc[row_idx, 0]
                if pd.notna(year_val):
                    year_str = str(year_val).strip()
                    # 整数や浮動小数点の年（e.g., 2024.0）
                    try:
                        year_int = int(float(year_str))
                        if 1900 <= year_int <= 2100:
                            current_year = str(year_int)
                    except (ValueError, TypeError):
                        pass

                if current_year is None:
                    continue

                # 四半期名（Col 2）
                qtr_val = df.iloc[row_idx, 2]
                if pd.isna(qtr_val):
                    continue
                qtr_str = str(qtr_val).strip()

                date_str = _quarter_month_to_date(current_year, qtr_str)
                if date_str is None:
                    continue

                # 値の取得
                data_val = df.iloc[row_idx, target_col]
                if pd.isna(data_val):
                    continue
                val_str = str(data_val).strip()
                if val_str in ('..', '', '-', 'NA', 'N/A'):
                    continue

                try:
                    result[date_str] = round(float(val_str), 1)
                except (ValueError, TypeError):
                    continue

            return result

        except Exception as e:
            print(f"[NzGDP] Error parsing {sheet_name} col {target_col}: {e}")
            return {}

    def _parse_next_release(self, excel_bytes: bytes) -> Optional[Dict[str, Any]]:
        """Contentsシートから次回発表日を解析"""
        try:
            df = pd.read_excel(io.BytesIO(excel_bytes), sheet_name='Contents', header=None)
            for row_idx in range(df.shape[0]):
                for col_idx in range(min(5, df.shape[1])):
                    val = df.iloc[row_idx, col_idx]
                    if pd.isna(val) or not isinstance(val, str):
                        continue
                    val_lower = val.lower()
                    if "will be released" in val_lower or "will be published" in val_lower or "next release" in val_lower:
                        match = re.search(r'(\d{1,2}\s+\w+\s+\d{4})', val)
                        if match:
                            date_str = match.group(1)
                            try:
                                dt = datetime.strptime(date_str, "%d %B %Y")
                                print(f"[NzGDP] Next release parsed: {dt.strftime('%Y-%m-%d')}")
                                return {
                                    "date": dt.strftime("%Y-%m-%d"),
                                    "label": val.strip(),
                                }
                            except ValueError:
                                pass
            return None
        except Exception as e:
            print(f"[NzGDP] Error parsing Contents for next release: {e}")
            return None

    def _get_quarter_attempts(self, year: int, month: int) -> List[tuple]:
        """ダウンロード試行する四半期リスト（最新から過去4四半期分）"""
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
        for _ in range(4):
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
            logger.error(f"[NzGDP] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[NzGDP] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None
        return {
            "indicator": "NZ GDP Growth Rate",
            "source": "Stats NZ",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
nz_gdp_growth_rate_service = NzGdpGrowthRateService()
