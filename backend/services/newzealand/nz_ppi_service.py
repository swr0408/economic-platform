"""
NZ生産者物価指数（PPI）サービス

指標:
- PPI Outputs (All Industries) - 産出価格指数
- PPI Inputs (All Industries) - 投入価格指数

データソース:
- Stats NZ Business Price Indexes
- https://www.stats.govt.nz/information-releases/business-price-indexes-december-2025-quarter/

取得方法:
- Stats NZ リリースページから ZIP を直接ダウンロード
- ZIP内CSVから PPIQ.SQU900000 (Output) / PPIQ.SQN900000 (Input) を抽出
- Index, QoQ%, YoY% の3系列を取得

URL パターン:
- https://www.stats.govt.nz/assets/Uploads/Business-price-indexes/
  Business-price-indexes-{Month}-{Year}-quarter/Download-data/
  business-price-indexes-{month}-{year}-quarter.zip

系列ID:
- PPIQ.SQU900000    : Output Index (base Dec 2010 = 1000)
- PPIQ.SQU900000PC  : Output QoQ %
- PPIQ.SQU900000AC  : Output YoY %
- PPIQ.SQN900000    : Input Index
- PPIQ.SQN900000PC  : Input QoQ %
- PPIQ.SQN900000AC  : Input YoY %

発表スケジュール:
- 四半期ごと（FMPから次回発表日取得）

キャッシュ方式:
- Redis + ファイルキャッシュ
"""
import json
import logging
import os
import zipfile
import io
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests
import pandas as pd

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "newzealand" / "inflation"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "nz_ppi_cache.json"

# Stats NZ Business Price Indexes ZIP URL パターン
# 四半期: March, June, September, December
QUARTER_MONTHS = {
    3: ("March", "march"),
    6: ("June", "june"),
    9: ("September", "september"),
    12: ("December", "december"),
}

# 対象系列ID
SERIES_CONFIG = {
    "output_index": "PPIQ.SQU900000",
    "output_qoq": "PPIQ.SQU900000PC",
    "output_yoy": "PPIQ.SQU900000AC",
    "input_index": "PPIQ.SQN900000",
    "input_qoq": "PPIQ.SQN900000PC",
    "input_yoy": "PPIQ.SQN900000AC",
}


def _build_zip_url(year: int, quarter_month: int) -> str:
    """Stats NZ BPI ZIP URLを生成"""
    month_cap, month_lower = QUARTER_MONTHS[quarter_month]
    return (
        f"https://www.stats.govt.nz/assets/Uploads/Business-price-indexes/"
        f"Business-price-indexes-{month_cap}-{year}-quarter/Download-data/"
        f"business-price-indexes-{month_lower}-{year}-quarter.zip"
    )


def _period_to_date(period_str: str) -> str:
    """Stats NZ Period (YYYY.MM) を日付文字列 (YYYY-MM-01) に変換"""
    parts = period_str.split(".")
    if len(parts) == 2:
        return f"{parts[0]}-{parts[1].zfill(2)}-01"
    return period_str


class NzPpiService:
    """NZ生産者物価指数（PPI）サービス"""

    DATA_CACHE_KEY = "newzealand:nz_ppi:data"

    def __init__(self):
        pass

    def get_nz_ppi_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """NZ PPIデータを取得"""

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

        # Stats NZ CSVからデータ取得
        result = self._load_from_stats_nz()
        if result:
            latest = result[-1] if result else None
            next_release = self._get_next_release()

            cache_payload = {
                "data": result,
                "latest": latest,
                "metadata": {
                    "source": "Stats NZ",
                    "indicator": "Producers Price Index (PPI)",
                    "description": "NZ生産者物価指数（PPI）",
                    "unit": "Index (Dec 2010 = 1000)",
                    "frequency": "quarterly",
                    "series_output": "PPIQ.SQU900000",
                    "series_input": "PPIQ.SQN900000",
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

    def _load_from_stats_nz(self) -> Optional[List[Dict[str, Any]]]:
        """Stats NZ BPI ZIPからPPIデータを取得"""
        try:
            # 最新四半期を決定して順に試行
            now = datetime.now(JST)
            attempts = self._get_quarter_attempts(now.year, now.month)

            df = None
            for year, qm in attempts:
                url = _build_zip_url(year, qm)
                print(f"[NzPPI] Trying: {url}")
                try:
                    resp = requests.get(url, timeout=90)
                    if resp.status_code == 200 and len(resp.content) > 5000:
                        z = zipfile.ZipFile(io.BytesIO(resp.content))
                        csv_names = [n for n in z.namelist() if n.endswith(".csv")]
                        if csv_names:
                            with z.open(csv_names[0]) as f:
                                df = pd.read_csv(f, low_memory=False)
                            month_cap, _ = QUARTER_MONTHS[qm]
                            print(f"[NzPPI] Downloaded {month_cap} {year} quarter ({len(resp.content)} bytes, {len(df)} rows)")
                            break
                    else:
                        print(f"[NzPPI] HTTP {resp.status_code} for {month_cap} {year}")
                except Exception as e:
                    print(f"[NzPPI] Error downloading {year} Q{qm//3}: {e}")
                    continue

            if df is None:
                print("[NzPPI] Failed to download any quarter data")
                return None

            # 対象系列を抽出
            series_data: Dict[str, Dict[str, float]] = {}
            for key, series_ref in SERIES_CONFIG.items():
                subset = df[df["Series_reference"] == series_ref].copy()
                if len(subset) > 0:
                    mapping = {}
                    for _, row in subset.iterrows():
                        period = str(row["Period"])
                        value = row["Data_value"]
                        if pd.notna(value):
                            date_str = _period_to_date(period)
                            try:
                                mapping[date_str] = round(float(value), 2)
                            except (ValueError, TypeError):
                                continue
                    series_data[key] = mapping
                    print(f"[NzPPI] {key} ({series_ref}): {len(mapping)} records")

            if not series_data.get("output_index"):
                print("[NzPPI] No output index data found")
                return None

            # 全日付を集約してマージ
            all_dates = set()
            for mapping in series_data.values():
                all_dates.update(mapping.keys())
            all_dates_sorted = sorted(all_dates)

            result = []
            for date_str in all_dates_sorted:
                item: Dict[str, Any] = {"date": date_str}
                has_any = False

                for key in ["output_index", "output_qoq", "output_yoy",
                            "input_index", "input_qoq", "input_yoy"]:
                    val = series_data.get(key, {}).get(date_str)
                    item[key] = val
                    if val is not None and key in ("output_index", "input_index"):
                        has_any = True

                if has_any:
                    result.append(item)

            if result:
                print(f"[NzPPI] Total {len(result)} records")
                print(f"[NzPPI] Date range: {result[0]['date']} to {result[-1]['date']}")
                latest = result[-1]
                print(f"[NzPPI] Latest: Output={latest.get('output_index')}, Input={latest.get('input_index')}")
                print(f"[NzPPI] Latest QoQ: Output={latest.get('output_qoq')}%, Input={latest.get('input_qoq')}%")
                print(f"[NzPPI] Latest YoY: Output={latest.get('output_yoy')}%, Input={latest.get('input_yoy')}%")

            return result

        except Exception as e:
            print(f"[NzPPI] Error loading from Stats NZ: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _get_quarter_attempts(self, year: int, month: int) -> List[tuple]:
        """ダウンロード試行する四半期リスト（最新から過去2四半期分）"""
        # 現在の四半期月
        quarter_months = [12, 9, 6, 3]
        attempts = []

        # 過去3四半期分を試行
        current_qm = None
        for qm in quarter_months:
            if month >= qm:
                current_qm = qm
                break

        if current_qm is None:
            current_qm = 12
            year -= 1

        # 現在の四半期から過去3つ
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

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """FMPから次回発表日を取得"""
        try:
            from services.newzealand.fmp_next_release_utils import get_next_release_by_pattern
            return get_next_release_by_pattern(
                "Producer Price Index QoQ",
                country="NZ",
            )
        except Exception as e:
            print(f"[NzPPI] Error getting next release: {e}")
            return None

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"[NzPPI] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[NzPPI] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None
        return {
            "indicator": "NZ Producers Price Index (PPI)",
            "source": "Stats NZ",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
nz_ppi_service = NzPpiService()
