"""
NZ銀行バランスシート（総資産）サービス

指標:
- NZ Banks Balance Sheet (Total Assets)

データソース:
- RBNZ Statistical Tables S10 (Banks: Balance sheet)
- https://www.rbnz.govt.nz/statistics/series/registered-banks/banks-balance-sheet

取得方法:
- RBNZ S10 XLSX を共通ヘルパー fetch_rbnz_xlsx（curl/wget自動選択・CF403リトライ）で
  ダウンロードし Total Assets (Col 19) を抽出

データ構造（Data シート）:
- Row 0: カテゴリ（Assets / Liabilities / Equity 等）
- Row 1: サブヘッダー（1. Cash, 2. Deposits, ..., 9. Total assets, ...）
- Row 2: Notes
- Row 3: Unit (NZDm)
- Row 4: Series Id
- Row 5+: データ（Col 0=datetime, Col 19=Total Assets）

発表スケジュール:
- 月次（月末から約1ヶ月後に発表）
- Published Date は Table Description シートから取得

キャッシュ方式:
- Redis + ファイルキャッシュ
"""
import io
import json
import logging
from datetime import datetime
from dateutil.relativedelta import relativedelta
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import pandas as pd

from core.redis_client import redis_client

# RBNZ Cloudflare 403 対策の共通フェッチャ (curl/wget 自動選択・リトライ付き)
try:
    from services.newzealand._rbnz_fetch import fetch_rbnz_xlsx
except ImportError:
    from backend.services.newzealand._rbnz_fetch import fetch_rbnz_xlsx

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "newzealand" / "policy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "nz_bank_balance_sheet_cache.json"

# RBNZ S10 XLSX URL
S10_URL = "https://www.rbnz.govt.nz/-/media/project/sites/rbnz/files/statistics/series/l-s/s10/hs10.xlsx"

# Excel構造定数
DATA_START_ROW = 5
DATE_COL = 0
TOTAL_ASSETS_COL = 19  # "9. Total assets"


class NzBankBalanceSheetService:
    """NZ銀行バランスシート（総資産）サービス"""

    DATA_CACHE_KEY = "newzealand:nz_bank_balance_sheet:data"

    def __init__(self):
        pass

    def get_nz_bank_balance_sheet_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """NZ銀行バランスシートデータを取得"""

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

        # S10 Excelからデータ取得
        result, published_date = self._load_from_s10_excel()
        if result:
            latest = result[-1] if result else None
            next_release = self._estimate_next_release(published_date)

            cache_payload = {
                "data": result,
                "latest": latest,
                "metadata": {
                    "source": "Reserve Bank of New Zealand",
                    "indicator": "Banks Balance Sheet (Total Assets)",
                    "description": "NZ銀行バランスシート（総資産）",
                    "unit": "NZD millions",
                    "frequency": "monthly",
                    "table": "S10 - Banks: Balance sheet",
                    "published_date": published_date,
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
                "source": "rbnz_s10",
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

    def _load_from_s10_excel(self) -> tuple[List[Dict[str, Any]], Optional[str]]:
        """RBNZ S10 XLSXからTotal Assetsデータを取得

        Returns:
            (data_list, published_date_str)
        """
        try:
            print(f"[NzBankBalanceSheet] Downloading S10 from: {S10_URL}")

            # 共通ヘルパー使用（curl/wget自動選択・CF403リトライ・xlsxマジックバイト検証）
            content = fetch_rbnz_xlsx(S10_URL, timeout=120)
            if content is None:
                logger.error(
                    "[NzBankBalanceSheet] ERROR: S10 download failed (all methods) — "
                    "serving stale cache. Check Cloudflare block on rbnz.govt.nz"
                )
                return [], None

            print(f"[NzBankBalanceSheet] Downloaded {len(content)} bytes")
            excel_io = io.BytesIO(content)

            # Published Date を Table Description シートから取得
            published_date = None
            try:
                desc_df = pd.read_excel(excel_io, sheet_name="Table Description", header=None, engine="openpyxl")
                for row_idx in range(desc_df.shape[0]):
                    label = desc_df.iloc[row_idx, 0]
                    if pd.notna(label) and "Published Date" in str(label):
                        date_val = desc_df.iloc[row_idx, 1]
                        if isinstance(date_val, datetime):
                            published_date = date_val.strftime("%Y-%m-%d")
                        elif pd.notna(date_val):
                            published_date = str(date_val)[:10]
                        break
            except Exception as e:
                print(f"[NzBankBalanceSheet] Could not read Published Date: {e}")

            # Data シートからTotal Assetsを取得
            excel_io.seek(0)
            df = pd.read_excel(excel_io, sheet_name="Data", header=None, engine="openpyxl")

            # ヘッダー確認
            header_check = str(df.iloc[1, TOTAL_ASSETS_COL]) if df.shape[0] > 1 and df.shape[1] > TOTAL_ASSETS_COL else ""
            print(f"[NzBankBalanceSheet] Header check (Row 1, Col {TOTAL_ASSETS_COL}): '{header_check}'")

            result = []
            for row_idx in range(DATA_START_ROW, df.shape[0]):
                date_val = df.iloc[row_idx, DATE_COL]
                assets_val = df.iloc[row_idx, TOTAL_ASSETS_COL]

                if pd.isna(date_val) or pd.isna(assets_val):
                    continue

                # 日付変換
                if isinstance(date_val, datetime):
                    date_str = date_val.strftime("%Y-%m-%d")
                elif isinstance(date_val, str):
                    try:
                        dt = pd.to_datetime(date_val)
                        date_str = dt.strftime("%Y-%m-%d")
                    except Exception:
                        continue
                else:
                    continue

                try:
                    value = round(float(assets_val), 0)
                    result.append({
                        "date": date_str,
                        "value": value,
                    })
                except (ValueError, TypeError):
                    continue

            if result:
                print(f"[NzBankBalanceSheet] Total {len(result)} records")
                print(f"[NzBankBalanceSheet] Date range: {result[0]['date']} to {result[-1]['date']}")
                print(f"[NzBankBalanceSheet] Latest: {result[-1]['date']} = {result[-1]['value']:,.0f} NZDm")
                print(f"[NzBankBalanceSheet] Published Date: {published_date}")

            return result, published_date

        except Exception as e:
            print(f"[NzBankBalanceSheet] Error loading S10: {e}")
            return [], None

    def _estimate_next_release(self, published_date: Optional[str]) -> Optional[Dict[str, Any]]:
        """次回発表日を推定（前回発表日 + 約1ヶ月）"""
        if not published_date:
            return None
        try:
            pub_dt = datetime.strptime(published_date, "%Y-%m-%d")
            next_dt = pub_dt + relativedelta(months=1)
            return {
                "date": next_dt.strftime("%Y-%m-%d"),
                "label": f"S10 Banks Balance Sheet ({next_dt.strftime('%b %Y')})",
                "estimated": True,
            }
        except Exception:
            return None

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"[NzBankBalanceSheet] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[NzBankBalanceSheet] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None
        return {
            "indicator": "NZ Banks Balance Sheet (Total Assets)",
            "source": "RBNZ",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
nz_bank_balance_sheet_service = NzBankBalanceSheetService()
