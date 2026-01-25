"""
個人消費支出（Personal Consumption Expenditures）サービス
FRED APIから名目PCE・実質PCEC96データを取得

指標:
- PCE: Personal Consumption Expenditures（名目個人消費支出）
- PCEC96: Real Personal Consumption Expenditures（実質個人消費支出）

データソース:
- FRED: https://fred.stlouisfed.org/series/PCE
- FRED: https://fred.stlouisfed.org/series/PCEC96
- BEA: https://www.bea.gov/data/income-saving/personal-income

発表スケジュール:
- BEA Personal Income and Outlays レポート
- 毎月末 8:30 AM ET
- BEAから次回発表日を自動取得

キャッシュ方式: 発表日時ベース判定方式
"""
from typing import Dict, Any, Optional
from pathlib import Path

from services.usa.fred_utils import (
    fetch_fred_series,
    calculate_changes,
    CacheManager,
    build_nominal_real_response,
)


# FREDシリーズID
PCE_SERIES_ID = "PCE"       # 名目個人消費支出（10億ドル、季節調整済み年率換算）
PCEC96_SERIES_ID = "PCEC96" # 実質個人消費支出（2017年基準、10億ドル、季節調整済み年率換算）

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "usa" / "consumer"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "pce_cache.json"


class PCEService:
    """個人消費支出（Personal Consumption Expenditures）サービス"""

    DATA_CACHE_KEY = "fred:pce:data"
    ECONALPHA_ID = "pce_mom"  # FMPマッピング用ID

    def __init__(self):
        self.cache_manager = CacheManager(
            redis_key=self.DATA_CACHE_KEY,
            cache_file=DATA_CACHE_FILE,
            econalpha_id=self.ECONALPHA_ID
        )

    def get_pce_data(
        self,
        start_date: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        個人消費支出データを取得（名目・実質）

        Returns:
            {
                "nominal": {
                    "data": [{"date": str, "mom": float, "yoy": float}, ...],
                    "latest": {...}
                },
                "real": {
                    "data": [{"date": str, "mom": float, "yoy": float}, ...],
                    "latest": {...}
                },
                "next_release": {"date": str, "label": str} | null,
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        # キャッシュチェック
        cached_data, source = self.cache_manager.get_cached_data(force_refresh)
        if cached_data:
            return build_nominal_real_response(
                nominal_data=cached_data.get("nominal"),
                real_data=cached_data.get("real"),
                cached=True,
                source=source,
                last_updated=cached_data.get("last_updated"),
                econalpha_id=self.ECONALPHA_ID
            )

        # FRED APIから取得
        api_data = self._fetch_from_api(start_date)

        if api_data:
            cache_payload = {
                "nominal": api_data["nominal"],
                "real": api_data["real"],
            }
            self.cache_manager.save(cache_payload)

            return build_nominal_real_response(
                nominal_data=api_data["nominal"],
                real_data=api_data["real"],
                cached=False,
                source="api",
                last_updated=cache_payload.get("last_updated"),
                econalpha_id=self.ECONALPHA_ID
            )

        # 取得失敗時はファイルキャッシュから返す
        fallback_data, fallback_source = self.cache_manager.get_fallback_data()
        if fallback_data:
            return build_nominal_real_response(
                nominal_data=fallback_data.get("nominal"),
                real_data=fallback_data.get("real"),
                cached=True,
                source=fallback_source,
                last_updated=fallback_data.get("last_updated"),
                econalpha_id=self.ECONALPHA_ID
            )

        return build_nominal_real_response(
            nominal_data=None,
            real_data=None,
            cached=False,
            source="none",
            last_updated=None,
            econalpha_id=self.ECONALPHA_ID,
            error="No data available"
        )

    def _fetch_from_api(self, start_date: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """FRED APIから個人消費支出データを取得"""
        try:
            print("Fetching Personal Consumption Expenditures from FRED...")

            # 名目個人消費支出
            nominal_raw = fetch_fred_series(PCE_SERIES_ID, start_date)
            # 実質個人消費支出
            real_raw = fetch_fred_series(PCEC96_SERIES_ID, start_date)

            if not nominal_raw or not real_raw:
                return None

            # 変化率を計算
            nominal_data = calculate_changes(nominal_raw)
            real_data = calculate_changes(real_raw)

            nominal_latest = nominal_data[-1] if nominal_data else None
            real_latest = real_data[-1] if real_data else None

            print(f"Fetched {len(nominal_data)} Personal Consumption Expenditures records")
            return {
                "nominal": {
                    "data": nominal_data,
                    "latest": nominal_latest
                },
                "real": {
                    "data": real_data,
                    "latest": real_latest
                }
            }

        except Exception as e:
            print(f"Error fetching Personal Consumption Expenditures: {e}")
            import traceback
            traceback.print_exc()
            return None

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return self.cache_manager.invalidate()

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        status = self.cache_manager.get_status()
        status.update({
            "indicator": "Personal Consumption Expenditures",
            "source": "FRED / BEA",
            "series_ids": [PCE_SERIES_ID, PCEC96_SERIES_ID],
        })
        return status


# シングルトンインスタンス
pce_service = PCEService()
