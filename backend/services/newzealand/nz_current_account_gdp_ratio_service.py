"""
NZ 経常収支対GDP比（Current Account Balance as % of GDP）サービス

指標:
- Current Account Balance / GDP (trailing 4四半期合計ベース): %

データソース:
- 経常収支: Stats NZ BOP CSV (BOPQ.S06AC100000000D)
  → nz_current_account_balance_service から再利用
- GDP: Stats NZ GDP supplementary tables Excel
  → Table 3, Col 57: SG02RSC00B15 (季節調整済み支出ベースGDP、百万NZD)

計算方法:
- Trailing 4Q合計 CA / Trailing 4Q合計 GDP × 100
- 例: 2025 Q3 ratio = (CA_Q4'24 + CA_Q1'25 + CA_Q2'25 + CA_Q3'25) /
                      (GDP_Q4'24 + GDP_Q1'25 + GDP_Q2'25 + GDP_Q3'25) × 100

発表スケジュール:
- 四半期（FMPイベント: "Current Account"）

キャッシュ方式:
- Redis + ファイルキャッシュ
"""
import json
import re
import io
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo
from pathlib import Path

import requests
import pandas as pd

from core.redis_client import redis_client
from services.newzealand.fmp_next_release_utils import get_next_release_by_pattern, should_refresh_by_pattern


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")

# キャッシュ設定
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "newzealand" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "nz_current_account_gdp_ratio_cache.json"

# FMPパターン（経常収支と同じ）
FMP_EVENT_PATTERN = "Current Account"
FMP_COUNTRY = "NZ"

# Stats NZ GDP Excel設定
QUARTER_MONTHS = {
    3: ("March", "march"),
    6: ("June", "june"),
    9: ("September", "september"),
    12: ("December", "december"),
}
QUARTER_STR_TO_MONTH = {"Mar": "03", "Jun": "06", "Sep": "09", "Dec": "12"}

# Table 3 の GDP 合計列インデックス（0始まり）
GDP_COL = 57   # SG02RSC00B15: Expenditure on GDP (SA, millions NZD)
GDP_DATA_START_ROW = 10  # データ開始行


def _discover_gdp_excel_url(year: int, qm: int) -> Optional[str]:
    """GDPリリースページをスクレイピングしてsupplementary-tables ExcelのURLを発見"""
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
        print(f"[NzCAGDP] Error discovering GDP URL for {year} Q{qm // 3}: {e}")
    return None


def _build_gdp_excel_url(year: int, quarter_month: int) -> str:
    """フォールバック用 GDP Excel URL"""
    month_cap, month_lower = QUARTER_MONTHS[quarter_month]
    return (
        f"https://www.stats.govt.nz/assets/Uploads/Gross-domestic-product/"
        f"Gross-domestic-product-{month_cap}-{year}-quarter/Download-data/"
        f"gross-domestic-product-{month_lower}-{year}-quarter-supplementary-tables.xlsx"
    )


def _get_quarter_attempts(year: int, month: int) -> List[Tuple[int, int]]:
    """試行する四半期リスト（最新から4件）"""
    quarter_months = [12, 9, 6, 3]
    current_qm = None
    for qm in quarter_months:
        if month >= qm:
            current_qm = qm
            break
    if current_qm is None:
        current_qm = 12
        year -= 1

    attempts = []
    y, qm = year, current_qm
    for _ in range(5):
        attempts.append((y, qm))
        idx = quarter_months.index(qm)
        if idx + 1 < len(quarter_months):
            qm = quarter_months[idx + 1]
        else:
            qm = quarter_months[0]
            y -= 1
    return attempts


def _download_gdp_excel(year: int, qm: int) -> Optional[bytes]:
    """GDP Excelをダウンロード"""
    # 1. リリースページから動的URLを発見
    url = _discover_gdp_excel_url(year, qm)
    if url:
        try:
            resp = requests.get(url, timeout=120)
            if resp.status_code == 200 and len(resp.content) > 50000:
                month_cap, _ = QUARTER_MONTHS[qm]
                print(f"[NzCAGDP] Downloaded GDP {month_cap} {year} ({len(resp.content):,} bytes)")
                return resp.content
        except Exception as e:
            print(f"[NzCAGDP] Error downloading GDP Excel: {e}")

    # 2. フォールバック: 固定URLパターン
    fallback_url = _build_gdp_excel_url(year, qm)
    try:
        resp = requests.get(fallback_url, timeout=120)
        if resp.status_code == 200 and len(resp.content) > 50000:
            month_cap, _ = QUARTER_MONTHS[qm]
            print(f"[NzCAGDP] Downloaded GDP {month_cap} {year} via fallback ({len(resp.content):,} bytes)")
            return resp.content
    except Exception as e:
        print(f"[NzCAGDP] Error downloading GDP fallback: {e}")
    return None


def _parse_gdp_level(content: bytes) -> Dict[str, float]:
    """Table 3 から季節調整済みGDPレベル（百万NZD）を抽出"""
    try:
        df = pd.read_excel(io.BytesIO(content), sheet_name="Table 3", header=None)
        result = {}
        current_year = None

        for r in range(GDP_DATA_START_ROW, df.shape[0]):
            yr_val = df.iloc[r, 0]
            if pd.notna(yr_val) and str(yr_val).strip().isdigit():
                current_year = str(yr_val).strip()

            qtr_val = df.iloc[r, 2]
            if not pd.notna(qtr_val) or str(qtr_val).strip() not in QUARTER_STR_TO_MONTH:
                continue
            if current_year is None:
                continue

            month_str = QUARTER_STR_TO_MONTH[str(qtr_val).strip()]
            date_str = f"{current_year}-{month_str}-01"

            gdp_val = df.iloc[r, GDP_COL] if GDP_COL < df.shape[1] else None
            if pd.notna(gdp_val):
                try:
                    result[date_str] = float(gdp_val)
                except (ValueError, TypeError):
                    pass

        print(f"[NzCAGDP] Parsed {len(result)} GDP records from Table 3")
        return result

    except Exception as e:
        print(f"[NzCAGDP] Error parsing GDP Excel: {e}")
        import traceback
        traceback.print_exc()
        return {}


def _load_ca_data() -> Dict[str, float]:
    """経常収支データをサービスから取得（Redisキャッシュ優先）"""
    try:
        from services.newzealand.nz_current_account_balance_service import nz_current_account_balance_service
        result = nz_current_account_balance_service.get_data(force_refresh=False)
        # 十億NZD → 百万NZD へ変換（GDPと単位を合わせる）
        return {
            item["date"]: item["value"] * 1000
            for item in result.get("data", [])
            if item.get("value") is not None
        }
    except Exception as e:
        print(f"[NzCAGDP] Error loading CA data: {e}")
        return {}


def _calculate_ratio(
    ca_data: Dict[str, float],
    gdp_data: Dict[str, float],
) -> List[Dict[str, Any]]:
    """Trailing 4四半期合計ベースで CA/GDP 比を計算"""
    all_dates = sorted(set(ca_data.keys()) & set(gdp_data.keys()))
    result = []

    for i, date_str in enumerate(all_dates):
        # Trailing 4Q計算（i>=3 のとき）
        if i >= 3:
            trailing_dates = all_dates[i - 3: i + 1]
            ca_4q = sum(ca_data[d] for d in trailing_dates if d in ca_data)
            gdp_4q = sum(gdp_data[d] for d in trailing_dates if d in gdp_data)
            ratio = round(ca_4q / gdp_4q * 100, 2) if gdp_4q != 0 else None
        else:
            ratio = None

        result.append({
            "date": date_str,
            "ratio": ratio,
            "ca_value": round(ca_data.get(date_str, 0) / 1000, 3),  # 十億NZD
            "gdp_value": round(gdp_data.get(date_str, 0) / 1000, 3),  # 十億NZD
        })

    return result


class NzCurrentAccountGdpRatioService:
    """NZ 経常収支対GDP比サービス"""

    DATA_CACHE_KEY = "newzealand:nz_current_account_gdp_ratio:data"

    def __init__(self):
        pass

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """経常収支対GDP比データを取得"""
        next_release = self._get_next_release()

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

        # データ取得・計算
        data = self._load_and_calculate()

        if data:
            latest = data[-1] if data else None
            if latest:
                print(f"[NzCAGDP] Latest: {latest['date']} ratio={latest.get('ratio')}%")

            metadata = {
                "source": "Stats NZ (BOP CSV + GDP Excel)",
                "indicator": "Current Account Balance as % of GDP",
                "description": "NZ 経常収支対GDP比（trailing 4Q合計ベース）",
                "unit": "%",
                "frequency": "quarterly",
                "gdp_series": "SG02RSC00B15 (SA expenditure GDP, millions NZD)",
                "ca_series": "BOPQ.S06AC100000000D (Current Account Balance, millions NZD)",
            }

            cache_payload = {
                "data": data,
                "latest": latest,
                "metadata": metadata,
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": data,
                "latest": latest,
                "metadata": metadata,
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
        }

    def _load_and_calculate(self) -> Optional[List[Dict[str, Any]]]:
        """GDP ExcelをDLし、CA データと合わせてratio計算"""
        # 1. GDPレベルデータ取得
        now = datetime.now(JST)
        attempts = _get_quarter_attempts(now.year, now.month)

        gdp_data = {}
        for year, qm in attempts:
            content = _download_gdp_excel(year, qm)
            if content:
                gdp_data = _parse_gdp_level(content)
                if gdp_data:
                    break

        if not gdp_data:
            print("[NzCAGDP] Failed to get GDP data")
            return None

        # 2. 経常収支データ取得（キャッシュから）
        ca_data = _load_ca_data()
        if not ca_data:
            print("[NzCAGDP] Failed to get CA data")
            return None

        # 3. Trailing 4Q ratio 計算
        result = _calculate_ratio(ca_data, gdp_data)
        # ratioがNoneのみのレコードも残す（初期期間のデータ）
        # ただし最低1件以上はratioあること
        has_ratio = any(r["ratio"] is not None for r in result)
        if not has_ratio:
            print("[NzCAGDP] No ratio data could be calculated")
            return None

        print(f"[NzCAGDP] Calculated {len(result)} ratio records")
        return result

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """次回発表日を取得"""
        try:
            return get_next_release_by_pattern(FMP_EVENT_PATTERN, country=FMP_COUNTRY)
        except Exception as e:
            print(f"[NzCAGDP] Error getting next release: {e}")
            return None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきか判定"""
        try:
            return should_refresh_by_pattern(FMP_EVENT_PATTERN, last_updated_str, country=FMP_COUNTRY)
        except Exception:
            try:
                last_updated = datetime.fromisoformat(last_updated_str)
                if last_updated.tzinfo is None:
                    last_updated = last_updated.replace(tzinfo=JST)
                now = datetime.now(JST)
                return (now - last_updated).total_seconds() > 86400
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
            print(f"[NzCAGDP] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[NzCAGDP] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None
        next_release = self._get_next_release()

        return {
            "indicator": "NZ Current Account Balance as % of GDP",
            "source": "Stats NZ BOP CSV + GDP Excel",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "next_release": next_release,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
nz_current_account_gdp_ratio_service = NzCurrentAccountGdpRatioService()
