"""
銀行貸し出し態度サービス（SLOOS マルチシリーズ版）
FRED APIからSLOOS（Senior Loan Officer Opinion Survey）データを取得

シリーズ一覧:
━━━ C&I 貸出基準 (Tightening Standards) ━━━
- DRTSCILM: 大企業・中堅企業向け
- DRTSCIS:  中小企業向け

━━━ C&I 貸出需要 (Stronger Demand) ━━━
- DRSDCILM: 大企業・中堅企業向け
- DRSDCIS:  中小企業向け

━━━ CRE 貸出基準 (Tightening Standards) ━━━
- SUBLPDRCSN: 非住宅商業不動産（Nonfarm Nonresidential）
- SUBLPDRCSC: 建設・土地開発（Construction & Land Development）
- SUBLPDRCSM: 集合住宅（Multifamily）

━━━ CRE 貸出需要 (Stronger Demand) ━━━
- SUBLPDRCDN: 非住宅商業不動産
- SUBLPDRCDC: 建設・土地開発
- SUBLPDRCDM: 集合住宅

発表スケジュール:
- 四半期ごと（2月、5月、8月、11月の初旬）
- 発表時刻: 14:00 ET

キャッシュ方式: last_updated判定（TTLなし）
スケジューラ: 発表日の23:00 JST（14:00 ET + 9時間）に更新
"""
import os
from datetime import datetime, date
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from core.redis_client import redis_client
from services.usa.fmp_next_release_utils import (
    get_next_release_from_fmp,
    should_refresh_by_fmp_schedule,
)

# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
ET = ZoneInfo("America/New_York")

# =====================================================================
# SLOOS FREDシリーズ定義
# =====================================================================

# C&I 貸出基準
SERIES_CI_STANDARDS_LARGE = "DRTSCILM"   # 大企業・中堅企業向け
SERIES_CI_STANDARDS_SMALL = "DRTSCIS"    # 中小企業向け

# C&I 貸出需要
SERIES_CI_DEMAND_LARGE = "DRSDCILM"      # 大企業・中堅企業向け
SERIES_CI_DEMAND_SMALL = "DRSDCIS"       # 中小企業向け

# CRE 貸出基準
SERIES_CRE_STANDARDS_NFNR = "SUBLPDRCSN"  # 非住宅商業不動産
SERIES_CRE_STANDARDS_CLD = "SUBLPDRCSC"    # 建設・土地開発
SERIES_CRE_STANDARDS_MF = "SUBLPDRCSM"     # 集合住宅

# CRE 貸出需要
SERIES_CRE_DEMAND_NFNR = "SUBLPDRCDN"     # 非住宅商業不動産
SERIES_CRE_DEMAND_CLD = "SUBLPDRCDC"       # 建設・土地開発
SERIES_CRE_DEMAND_MF = "SUBLPDRCDM"        # 集合住宅

# 全シリーズの定義マップ
# key: APIレスポンスのフィールド名, value: (FRED series_id, 日本語名, 英語名)
SLOOS_SERIES: Dict[str, tuple] = {
    # C&I 貸出基準
    "ci_standards_large":  (SERIES_CI_STANDARDS_LARGE,  "C&I貸出基準: 大企業・中堅",       "C&I Standards: Large/Medium Firms"),
    "ci_standards_small":  (SERIES_CI_STANDARDS_SMALL,  "C&I貸出基準: 中小企業",           "C&I Standards: Small Firms"),
    # C&I 貸出需要
    "ci_demand_large":     (SERIES_CI_DEMAND_LARGE,     "C&I貸出需要: 大企業・中堅",       "C&I Demand: Large/Medium Firms"),
    "ci_demand_small":     (SERIES_CI_DEMAND_SMALL,     "C&I貸出需要: 中小企業",           "C&I Demand: Small Firms"),
    # CRE 貸出基準
    "cre_standards_nfnr":  (SERIES_CRE_STANDARDS_NFNR,  "CRE貸出基準: 非住宅商業不動産",   "CRE Standards: Nonfarm Nonresidential"),
    "cre_standards_cld":   (SERIES_CRE_STANDARDS_CLD,   "CRE貸出基準: 建設・土地開発",     "CRE Standards: Construction & Land Dev."),
    "cre_standards_mf":    (SERIES_CRE_STANDARDS_MF,    "CRE貸出基準: 集合住宅",           "CRE Standards: Multifamily"),
    # CRE 貸出需要
    "cre_demand_nfnr":     (SERIES_CRE_DEMAND_NFNR,     "CRE貸出需要: 非住宅商業不動産",   "CRE Demand: Nonfarm Nonresidential"),
    "cre_demand_cld":      (SERIES_CRE_DEMAND_CLD,      "CRE貸出需要: 建設・土地開発",     "CRE Demand: Construction & Land Dev."),
    "cre_demand_mf":       (SERIES_CRE_DEMAND_MF,        "CRE貸出需要: 集合住宅",           "CRE Demand: Multifamily"),
}

# 後方互換: 旧メソッド用
BANK_LENDING_SERIES_ID = SERIES_CI_STANDARDS_LARGE

# SLOOS発表スケジュール
SLOOS_RELEASE_MONTHS = [2, 5, 8, 11]


class BankLendingService:
    """銀行貸し出し態度サービス（SLOOS マルチシリーズ）"""

    BASE_URL = "https://api.stlouisfed.org/fred"
    CACHE_KEY = "fred:series:bank_lending"
    CACHE_KEY_MULTI = "fred:series:bank_lending_multi"
    SCHEDULE_CACHE_KEY = "sloos:schedule"
    ECONALPHA_ID = "bank_lending"

    def __init__(self):
        self.api_key = os.environ.get("FRED_API_KEY", "")

    # =================================================================
    # メイン取得メソッド（マルチシリーズ版）
    # =================================================================

    def get_bank_lending_multi(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        SLOOS全10シリーズを一括取得

        Returns:
            {
                "series": {
                    "ci_standards_large": {
                        "data": [...], "latest": {...},
                        "fred_id": "DRTSCILM", "name_ja": "...", "name_en": "..."
                    },
                    ...
                },
                "next_release": {...},
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        # キャッシュチェック
        if not force_refresh:
            cached = redis_client.get(self.CACHE_KEY_MULTI)
            if cached:
                last_updated_str = cached.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    cached["next_release"] = self._get_next_sloos_release()
                    cached["cached"] = True
                    cached["source"] = "redis"
                    return cached

        # FRED APIから全シリーズ並列取得
        all_series = self._fetch_all_series()

        if all_series:
            next_release = self._get_next_sloos_release()
            now = datetime.now(JST).isoformat()

            # 発表レース対策ラグガード: 全SLOOS系列の最新四半期が既存キャッシュを超えて
            # いなければ last_updated を据え置き、次回再取得で自己回復させる（SLOOSは四半期）。
            _new_date = None
            for _s in all_series.values():
                if isinstance(_s, dict) and isinstance(_s.get("latest"), dict):
                    _d = _s["latest"].get("date")
                    if _d and (_new_date is None or _d > _new_date):
                        _new_date = _d
            _existing = redis_client.get(self.CACHE_KEY_MULTI)
            _old_date = None
            if isinstance(_existing, dict) and isinstance(_existing.get("series"), dict):
                for _s in _existing["series"].values():
                    if isinstance(_s, dict) and isinstance(_s.get("latest"), dict):
                        _d = _s["latest"].get("date")
                        if _d and (_old_date is None or _d > _old_date):
                            _old_date = _d
            if _existing and _old_date and _new_date and _new_date <= _old_date:
                now = _existing.get("last_updated", now)

            result = {
                "series": all_series,
                "next_release": next_release,
                "cached": False,
                "source": "api",
                "last_updated": now,
            }

            # キャッシュ保存
            redis_client.set(self.CACHE_KEY_MULTI, result, expire=0)

            return result

        return {
            "series": {},
            "next_release": self._get_next_sloos_release(),
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _fetch_all_series(self) -> Dict[str, Any]:
        """全10シリーズをFRED APIから並列取得"""
        result = {}

        def fetch_one(key: str, series_id: str, name_ja: str, name_en: str):
            data = self._fetch_fred_series(series_id)
            latest = data[-1] if data else None
            return key, {
                "data": data,
                "latest": latest,
                "fred_id": series_id,
                "name_ja": name_ja,
                "name_en": name_en,
            }

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for key, (series_id, name_ja, name_en) in SLOOS_SERIES.items():
                futures.append(
                    executor.submit(fetch_one, key, series_id, name_ja, name_en)
                )

            for future in as_completed(futures):
                try:
                    key, series_data = future.result()
                    result[key] = series_data
                except Exception as e:
                    print(f"[SLOOS] Error fetching series: {e}")

        fetched_count = sum(1 for v in result.values() if v.get("data"))
        print(f"[SLOOS] Fetched {fetched_count}/{len(SLOOS_SERIES)} series from FRED")
        return result

    def _fetch_fred_series(
        self,
        series_id: str,
        start_date: str = "1990-01-01",
    ) -> List[Dict[str, Any]]:
        """FRED APIから単一シリーズを取得"""
        try:
            if not self.api_key:
                return []

            url = f"{self.BASE_URL}/series/observations"
            params = {
                "series_id": series_id,
                "api_key": self.api_key,
                "file_type": "json",
                "observation_start": start_date,
                "sort_order": "asc",
            }

            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            raw = resp.json()

            result = []
            for obs in raw.get("observations", []):
                if obs.get("value") and obs["value"] != ".":
                    try:
                        result.append({
                            "date": obs["date"],
                            "value": round(float(obs["value"]), 2),
                        })
                    except (ValueError, TypeError):
                        continue

            return result

        except Exception as e:
            print(f"[SLOOS] Error fetching {series_id}: {e}")
            return []

    # =================================================================
    # 後方互換メソッド（旧: 単一シリーズ）
    # =================================================================

    def get_bank_lending_standards(
        self,
        start_date: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        銀行貸し出し態度データを取得（後方互換）

        マルチシリーズ版から ci_standards_large を返す
        """
        multi = self.get_bank_lending_multi(force_refresh=force_refresh)

        ci_large = multi.get("series", {}).get("ci_standards_large", {})
        data = ci_large.get("data", [])
        latest = ci_large.get("latest")

        return {
            "data": data,
            "latest": latest,
            "next_release": multi.get("next_release"),
            "cached": multi.get("cached", False),
            "source": multi.get("source", "none"),
            "last_updated": multi.get("last_updated"),
        }

    # =================================================================
    # SLOOS 発表スケジュール
    # =================================================================

    def _get_next_sloos_release(self) -> Optional[Dict[str, Any]]:
        """次回SLOOS発表日を計算"""
        today = date.today()
        current_year = today.year

        for year in [current_year, current_year + 1]:
            for month in SLOOS_RELEASE_MONTHS:
                first_day = date(year, month, 1)
                days_until_monday = (7 - first_day.weekday()) % 7
                if days_until_monday == 0 and first_day.weekday() != 0:
                    days_until_monday = 7
                first_monday = first_day.replace(
                    day=1 + days_until_monday if first_day.weekday() != 0 else 1
                )

                release_date = first_monday

                if release_date > today:
                    if month == 2:
                        quarter = f"{year-1}Q4"
                    elif month == 5:
                        quarter = f"{year}Q1"
                    elif month == 8:
                        quarter = f"{year}Q2"
                    else:
                        quarter = f"{year}Q3"

                    return {
                        "date": release_date.strftime("%Y-%m-%d"),
                        "quarter": quarter,
                        "title": f"SLOOS {quarter}",
                    }

        return None

    def get_sloos_schedule(self, year: Optional[int] = None) -> List[Dict[str, Any]]:
        """SLOOS発表スケジュールを取得"""
        if year is None:
            year = date.today().year

        schedule = []
        for target_year in [year, year + 1]:
            for month in SLOOS_RELEASE_MONTHS:
                first_day = date(target_year, month, 1)
                days_until_monday = (7 - first_day.weekday()) % 7
                if days_until_monday == 0 and first_day.weekday() != 0:
                    days_until_monday = 7
                first_monday = first_day.replace(
                    day=1 + days_until_monday if first_day.weekday() != 0 else 1
                )

                if month == 2:
                    quarter = f"{target_year-1}Q4"
                elif month == 5:
                    quarter = f"{target_year}Q1"
                elif month == 8:
                    quarter = f"{target_year}Q2"
                else:
                    quarter = f"{target_year}Q3"

                schedule.append({
                    "date": first_monday.strftime("%Y-%m-%d"),
                    "quarter": quarter,
                    "title": f"SLOOS {quarter}",
                    "release_time": "14:00 ET",
                })

        return schedule

    # =================================================================
    # キャッシュ・ユーティリティ
    # =================================================================

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（FMP 3分方式）"""
        return should_refresh_by_fmp_schedule(self.ECONALPHA_ID, last_updated_str)

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        redis_client.delete(self.CACHE_KEY)
        redis_client.delete(self.CACHE_KEY_MULTI)
        return True

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        cached_multi = redis_client.get(self.CACHE_KEY_MULTI)
        series_count = len(cached_multi.get("series", {})) if cached_multi else 0

        return {
            "series_ids": list(SLOOS_SERIES.keys()),
            "cache_key": self.CACHE_KEY_MULTI,
            "exists": cached_multi is not None,
            "series_count": series_count,
            "last_updated": cached_multi.get("last_updated") if cached_multi else None,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
        }

    def get_latest_value(self) -> Optional[Dict[str, Any]]:
        """最新の銀行貸し出し態度を取得（後方互換）"""
        result = self.get_bank_lending_standards()
        return result.get("latest")


# シングルトンインスタンス
bank_lending_service = BankLendingService()
