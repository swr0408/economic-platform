"""
中国雇用ダッシュボードローダー
失業率（全国・若年層）を一括取得

キャッシュ更新判定: NBS発表日時ベース
"""
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from zoneinfo import ZoneInfo

from services.dashboard.loaders.base import BaseDashboardLoader


JST = ZoneInfo("Asia/Tokyo")
CST = ZoneInfo("Asia/Shanghai")

# 失業率の手動更新CSV（NBS公式エクスポート）。total+youth をここから取り込む。
# このファイルが更新されたら集約キャッシュを stale 化し、失業率サービスを再取得させる。
_UNEMPLOYMENT_CSV = (
    Path(__file__).parent.parent.parent.parent
    / "data" / "csv_import" / "ChinaUnemployment Rate.csv"
)


class ChinaEmploymentLoader(BaseDashboardLoader):
    """
    中国雇用ダッシュボード用データローダー

    取得データ:
    - cn_unemployment_rate: 失業率（全国・若年層）
    """

    COUNTRY_CODE = "china"
    CATEGORY_CODE = "employment"

    EXPECTED_KEYS = [
        "cn_unemployment_rate",
    ]

    def __init__(self):
        super().__init__()
        self._stale_indicators: set = set()

    def get_expected_keys(self) -> List[str]:
        return self.EXPECTED_KEYS

    def get_manual_csv_paths(self) -> List[Path]:
        """手動更新CSVを宣言 → mtime がキャッシュより新しければ集約再構築。"""
        return [_UNEMPLOYMENT_CSV]

    def _csv_newer_than(self, last_updated_dt: datetime) -> bool:
        """失業率の手動CSVが last_updated 以降に更新されていれば True。"""
        try:
            if not _UNEMPLOYMENT_CSV.exists():
                return False
            mtime = datetime.fromtimestamp(os.path.getmtime(_UNEMPLOYMENT_CSV), tz=JST)
            return mtime > last_updated_dt
        except Exception:
            return False

    def _detect_stale_indicators(self, last_updated: Optional[str]) -> set:
        """
        発表日時を過ぎた指標を検出（FMPカレンダー自動判定）
        ＋ 手動更新CSVが更新されていれば再取得。
        """
        if last_updated is None:
            return set()

        try:
            last_updated_dt = datetime.fromisoformat(last_updated)
            if last_updated_dt.tzinfo is None:
                last_updated_dt = last_updated_dt.replace(tzinfo=JST)

            # 手動更新CSV(NBS公式エクスポート)が更新されていれば再取得
            if self._csv_newer_than(last_updated_dt):
                return {"all"}

            now = datetime.now(JST)
            release_datetimes = self.get_release_datetimes()

            for release_dt in release_datetimes:
                if release_dt and last_updated_dt < release_dt <= now:
                    return {"all"}

        except Exception as e:
            print(f"Error detecting stale indicators: {e}")
            # エラー時に {"all"} を返すと、エラーが続く限り毎リクエストで全指標の
            # 外部API一斉取得が走りイベントループ/executorを圧迫する (2026-06-13 障害)。
            # 判定不能時はキャッシュ継続に倒す (各サービスのスケジューラが個別に更新する)。
            return set()

        return set()

    def _should_force_refresh(self, indicator: str) -> bool:
        if "all" in self._stale_indicators:
            return True
        return indicator in self._stale_indicators

    def _prepare_for_refresh(self, last_updated: Optional[str]) -> None:
        self._stale_indicators = self._detect_stale_indicators(last_updated)
        if self._stale_indicators:
            print(f"[ChinaEmployment] Stale indicators detected: {self._stale_indicators}")

    def load_all(self) -> Dict[str, Any]:
        from services.china.cn_unemployment_rate_service import cn_unemployment_rate_service

        result = {
            "cn_unemployment_rate": None,
        }

        result["cn_unemployment_rate"] = self._get_generic_indicator(
            cn_unemployment_rate_service,
            "cn_unemployment_rate",
            "Unemployment Rate",
        )

        return result

    def _get_generic_indicator(self, service, key: str, label: str) -> dict:
        try:
            force_refresh = self._should_force_refresh(key)
            response = service.get_data(force_refresh=force_refresh)
            return {
                "data": response.get("data", []),
                "latest": response.get("latest"),
                "metadata": response.get("metadata", {}),
                "next_release": response.get("next_release"),
            }
        except Exception as e:
            print(f"[ChinaEmployment] Error getting {label}: {e}")
            return {"data": [], "latest": None, "metadata": {}, "next_release": None}
