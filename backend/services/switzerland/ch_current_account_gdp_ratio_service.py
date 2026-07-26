"""
スイス経常収支対GDP比サービス
SNB経常収支 / SECO名目GDP で比率を算出

指標:
- 経常収支対GDP比（Current Account to GDP Ratio）

データソース:
- SNB Data Portal cube: bopoverq (経常収支, 四半期, M CHF)
- SECO Excel: qna_p_na.xlsx (名目GDP, 四半期, M CHF)

計算:
- Ratio (%) = (Current Account M CHF / Nominal GDP M CHF) × 100

発表スケジュール:
- 四半期（GDP発表時に更新）

キャッシュ方式: FMP GDP発表日ベース判定
"""
import json
import io
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests
import pandas as pd

from core.redis_client import redis_client
from services.switzerland.fmp_next_release_utils import (
    get_next_release_by_pattern,
    should_refresh_by_pattern,
)


JST = ZoneInfo("Asia/Tokyo")
ZURICH = ZoneInfo("Europe/Zurich")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "switzerland" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ch_current_account_gdp_ratio_cache.json"

# SNB bopoverq cube: 経常収支ネット（D0=S0）
SNB_CURRENT_ACCOUNT_URL = (
    "https://data.snb.ch/api/cube/bopoverq/data/csv/en?"
    "dimSel=D0(S0)"
    "&fromDate=2000-Q1"
)

# SECO Excel: 名目GDP（調整前）
SECO_NOMINAL_GDP_URL = (
    "https://www.seco.admin.ch/dam/seco/de/dokumente/Wirtschaft/"
    "Wirtschaftslage/VIP%20Quartalssch%C3%A4tzungen/"
    "qna_p_na.xlsx.download.xlsx/qna_p_na.xlsx"
)

# 四半期→月マッピング（四半期末月の1日）
QUARTER_TO_DATE = {
    "Q1": "-03-01",
    "Q2": "-06-01",
    "Q3": "-09-01",
    "Q4": "-12-01",
}

# FMPイベントパターン（GDP発表時に更新）
FMP_EVENT_PATTERN = "GDP Growth Rate QoQ"
FMP_COUNTRY = "CH"


class CHCurrentAccountGdpRatioService:
    """スイス経常収支対GDP比サービス"""

    DATA_CACHE_KEY = "switzerland:ch_current_account_gdp_ratio:data"

    def __init__(self):
        pass

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """経常収支対GDP比データを取得"""
        next_release = get_next_release_by_pattern(FMP_EVENT_PATTERN, country=FMP_COUNTRY)

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
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # データソースから取得
        result = self._load_from_source()
        if result:
            latest = result[-1] if result else None
            from services.usa.fmp_next_release_utils import guarded_last_updated
            now_str = datetime.now(JST).isoformat()
            last_updated = guarded_last_updated(
                self.DATA_CACHE_KEY, latest.get("date") if latest else None, now_str
            )

            cache_payload = {
                "data": result,
                "latest": latest,
                "metadata": {
                    "source": "SNB + SECO",
                    "indicator": "Current Account to GDP Ratio",
                    "description": "スイス経常収支対GDP比",
                    "unit": "%",
                    "frequency": "quarterly",
                    "ca_source": "SNB bopoverq (M CHF)",
                    "gdp_source": "SECO qna_p_na.xlsx nom_q (M CHF)",
                },
                "last_updated": last_updated,
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": result,
                "latest": latest,
                "metadata": cache_payload["metadata"],
                "next_release": next_release,
                "cached": False,
                "source": "api",
                "last_updated": last_updated,
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "metadata": file_cache.get("metadata", {}),
                "next_release": next_release,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "data": [],
            "latest": None,
            "metadata": {},
            "next_release": next_release,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _load_from_source(self) -> List[Dict[str, Any]]:
        """SNB経常収支 + SECO名目GDPから対GDP比を計算"""
        try:
            # 1. SNBから経常収支データを取得（M CHF）
            print(f"[CH CA/GDP] Fetching current account from SNB bopoverq")
            ca_data = self._fetch_current_account()
            print(f"[CH CA/GDP] Current account: {len(ca_data)} quarters")

            # 2. SECOから名目GDPデータを取得（M CHF）
            print(f"[CH CA/GDP] Fetching nominal GDP from SECO")
            gdp_data = self._fetch_nominal_gdp()
            print(f"[CH CA/GDP] Nominal GDP: {len(gdp_data)} quarters")

            # 3. 比率を計算
            result = []
            for date_str in sorted(ca_data.keys()):
                if date_str in gdp_data:
                    ca_value = ca_data[date_str]
                    gdp_value = gdp_data[date_str]
                    if gdp_value > 0:
                        ratio = (ca_value / gdp_value) * 100
                        result.append({
                            "date": date_str,
                            "value": round(ratio, 2),
                            "current_account": round(ca_value, 2),
                            "gdp": round(gdp_value, 2),
                        })

            print(f"[CH CA/GDP] Calculated {len(result)} quarterly records")
            if result:
                print(f"[CH CA/GDP] Date range: {result[0]['date']} to {result[-1]['date']}")
                latest = result[-1]
                print(f"[CH CA/GDP] Latest: {latest['date']} Ratio={latest['value']}% CA={latest['current_account']}M GDP={latest['gdp']}M")

            return result

        except Exception as e:
            print(f"[CH CA/GDP] Error loading data: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _fetch_current_account(self) -> Dict[str, float]:
        """SNB bopoverq cubeから経常収支ネット(M CHF)を取得"""
        resp = requests.get(SNB_CURRENT_ACCOUNT_URL, timeout=60)
        resp.raise_for_status()

        csv_content = resp.content.decode("utf-8")
        lines = csv_content.strip().split("\n")

        ca_data: Dict[str, float] = {}
        in_data = False

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            parts = [p.strip().strip('"') for p in stripped.split(";")]

            if parts[0] == "Date":
                in_data = True
                continue

            if in_data and len(parts) >= 3:
                date_raw = parts[0]   # "2025-Q3"
                d0 = parts[1]         # "S0"
                val_str = parts[2]

                if d0 != "S0":
                    continue

                try:
                    val_m = float(val_str)  # M CHF
                except ValueError:
                    continue

                # YYYY-QN → YYYY-MM-01
                year_str = date_raw[:4]
                q_str = date_raw[5:]
                if q_str not in QUARTER_TO_DATE:
                    continue

                date_formatted = f"{year_str}{QUARTER_TO_DATE[q_str]}"
                ca_data[date_formatted] = val_m

        return ca_data

    def _fetch_nominal_gdp(self) -> Dict[str, float]:
        """SECO Excel (qna_p_na.xlsx) から名目GDP(M CHF)を取得

        SECO Excel形式:
        - シート: nom_q（名目GDP, 四半期）
        - Column 0: 年
        - Column 1: 四半期（1, 2, 3, 4）
        - Column 2: GDP値（M CHF）
        - データ行は11行目（index 11）から
        """
        resp = requests.get(SECO_NOMINAL_GDP_URL, timeout=60)
        resp.raise_for_status()

        df = pd.read_excel(io.BytesIO(resp.content), sheet_name='nom_q', header=None)

        gdp_data: Dict[str, float] = {}
        for i in range(11, len(df)):
            year = df.iloc[i, 0]
            quarter = df.iloc[i, 1]
            gdp_val = df.iloc[i, 2]  # GDP値は列2

            if pd.isna(year) or pd.isna(quarter) or pd.isna(gdp_val):
                continue

            try:
                year_int = int(year)
                quarter_int = int(quarter)

                # 四半期→月（Q1→03, Q2→06, Q3→09, Q4→12）（経常収支と同じ変換）
                q_key = f"Q{quarter_int}"
                if q_key not in QUARTER_TO_DATE:
                    continue

                date_str = f"{year_int}{QUARTER_TO_DATE[q_key]}"
                gdp_data[date_str] = float(gdp_val)
            except (ValueError, TypeError):
                continue

        return gdp_data

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        try:
            return should_refresh_by_pattern(FMP_EVENT_PATTERN, last_updated_str, country=FMP_COUNTRY)
        except Exception:
            try:
                last_updated = datetime.fromisoformat(last_updated_str)
                if last_updated.tzinfo is None:
                    last_updated = last_updated.replace(tzinfo=JST)
                now = datetime.now(JST)
                age = now - last_updated
                return age.total_seconds() > 86400 * 7
            except Exception:
                return True

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[CH CA/GDP] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CH CA/GDP] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "CH Current Account to GDP Ratio",
            "source": "SNB + SECO",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_by_pattern(FMP_EVENT_PATTERN, country=FMP_COUNTRY),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ch_current_account_gdp_ratio_service = CHCurrentAccountGdpRatioService()
