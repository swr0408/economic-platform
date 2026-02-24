"""
RBNZ中央銀行バランスシート（総資産）サービス

指標:
- RBNZ Central Bank Balance Sheet (Total Assets)

データソース:
- RBNZ Statistical Tables R1 (Our Balance Sheet)
- https://www.rbnz.govt.nz/statistics/series/reserve-bank/our-balance-sheet

取得方法:
- RBNZ R1 XLSX をcurlでダウンロードし Total Assets (Col 10) を抽出

データ構造（Data シート）:
- Row 0: カテゴリ（Assets / Liabilities 等）
- Row 1: サブヘッダー（Cash Balances, Total Assets, ...）
- Row 2: Notes
- Row 3: Unit (NZDm)
- Row 4: Series Id (RBNZ.MRA)
- Row 5+: データ（Col 0=datetime, Col 10=Total Assets）

発表スケジュール:
- 月次（月末から2-3週間後に発表）
- Published Date は Table Description シートから取得

キャッシュ方式:
- Redis + ファイルキャッシュ
"""
import json
import logging
import os
import subprocess
import tempfile
from datetime import datetime
from dateutil.relativedelta import relativedelta
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import pandas as pd

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "newzealand" / "policy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "nz_central_bank_balance_sheet_cache.json"

# RBNZ R1 XLSX URL
R1_URL = "https://www.rbnz.govt.nz/-/media/project/sites/rbnz/files/statistics/series/d-f-r/r1/hr1.xlsx"

# Excel構造定数
DATA_START_ROW = 5
DATE_COL = 0
TOTAL_ASSETS_COL = 10  # "Total Assets" (Series ID: RBNZ.MRA)


class NzCentralBankBalanceSheetService:
    """RBNZ中央銀行バランスシート（総資産）サービス"""

    DATA_CACHE_KEY = "newzealand:nz_central_bank_balance_sheet:data"

    def __init__(self):
        pass

    def get_nz_central_bank_balance_sheet_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """RBNZ中央銀行バランスシートデータを取得"""

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

        # R1 Excelからデータ取得
        result, published_date = self._load_from_r1_excel()
        if result:
            latest = result[-1] if result else None
            next_release = self._estimate_next_release(published_date)

            cache_payload = {
                "data": result,
                "latest": latest,
                "metadata": {
                    "source": "Reserve Bank of New Zealand",
                    "indicator": "Central Bank Balance Sheet (Total Assets)",
                    "description": "RBNZ中央銀行バランスシート（総資産）",
                    "unit": "NZD millions",
                    "frequency": "monthly",
                    "table": "R1 - Our Balance Sheet",
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
                "source": "rbnz_r1",
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

    def _load_from_r1_excel(self) -> tuple[List[Dict[str, Any]], Optional[str]]:
        """RBNZ R1 XLSXからTotal Assetsデータを取得

        Returns:
            (data_list, published_date_str)
        """
        try:
            print(f"[NzBalanceSheet] Downloading R1 via curl from: {R1_URL}")

            with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
                tmp_path = tmp.name

            try:
                proc = subprocess.run(
                    [
                        "curl", "-L", "-o", tmp_path,
                        "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                        "--max-time", "120",
                        "-s",
                        R1_URL,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=150,
                )

                if proc.returncode != 0:
                    print(f"[NzBalanceSheet] curl failed (exit {proc.returncode}): {proc.stderr[:200]}")
                    return [], None

                file_size = os.path.getsize(tmp_path)
                if file_size < 5000:
                    print(f"[NzBalanceSheet] Downloaded file too small ({file_size} bytes)")
                    return [], None

                print(f"[NzBalanceSheet] Downloaded {file_size} bytes")

                # Published Date を Table Description シートから取得
                published_date = None
                try:
                    desc_df = pd.read_excel(tmp_path, sheet_name="Table Description", header=None, engine="openpyxl")
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
                    print(f"[NzBalanceSheet] Could not read Published Date: {e}")

                # Data シートからTotal Assetsを取得
                df = pd.read_excel(tmp_path, sheet_name="Data", header=None, engine="openpyxl")

            finally:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

            # ヘッダー確認
            header_check = str(df.iloc[1, TOTAL_ASSETS_COL]) if df.shape[0] > 1 and df.shape[1] > TOTAL_ASSETS_COL else ""
            print(f"[NzBalanceSheet] Header check (Row 1, Col {TOTAL_ASSETS_COL}): '{header_check}'")

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
                print(f"[NzBalanceSheet] Total {len(result)} records")
                print(f"[NzBalanceSheet] Date range: {result[0]['date']} to {result[-1]['date']}")
                print(f"[NzBalanceSheet] Latest: {result[-1]['date']} = {result[-1]['value']:,.0f} NZDm")
                print(f"[NzBalanceSheet] Published Date: {published_date}")

            return result, published_date

        except Exception as e:
            print(f"[NzBalanceSheet] Error loading R1: {e}")
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
                "label": f"R1 Balance Sheet ({next_dt.strftime('%b %Y')})",
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
            logger.error(f"[NzBalanceSheet] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[NzBalanceSheet] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None
        return {
            "indicator": "RBNZ Central Bank Balance Sheet (Total Assets)",
            "source": "RBNZ",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
nz_central_bank_balance_sheet_service = NzCentralBankBalanceSheetService()
