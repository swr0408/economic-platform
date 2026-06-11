"""
NAIRU / 失業率サービス
FRED APIから NROU（自然失業率 / NAIRU）と UNRATE（失業率）を取得し、
1つのチャートで「自然失業率 vs 実際の失業率」を比較表示する

指標:
- NROU:  Noncyclical Rate of Unemployment（CBO推計の自然失業率 / NAIRU）四半期
- UNRATE: Unemployment Rate（実際の失業率 / U-3）月次

データソース:
- FRED: https://fred.stlouisfed.org/series/NROU （出所: CBO）
- FRED: https://fred.stlouisfed.org/series/UNRATE （出所: BLS）
- CBO: https://www.cbo.gov/about/products/major-recurring-reports

発表スケジュール:
- 実際の失業率（UNRATE）: BLS Employment Situation、毎月第1金曜日 8:30 AM ET
- NAIRU（NROU）: CBOの経済見通し改定時に不定期更新（四半期データ）

更新スケジュール:
- 失業率の発表スケジュール（FMP econalpha_id="unemployment_rate"）に加え、
  CacheManager の週次フォールバック（7日）で最低週1回 FRED を再取得する。
- NROU は再取得のたびに data 配列へ反映されるため、CBOによる
  ヴィンテージ改定（過去値の修正）も次回の週次チェックで取り込まれる。

マージ方針:
- PRIMARY_SERIES = "unrate"（月次）をベースに NROU（四半期）をマージ。
  NROU は四半期始月（1/4/7/10月）でのみ値を持ち、それ以外の月は None。
  フロントの StandardLineChart は connectNulls=true のため NAIRU を連続線で描画する。
  将来のCBO見通し（UNRATEより先の四半期）は実績UR比較の対象外として除外される。

リファクタリング: fred_utils.BaseMultiSeriesService を使用
"""
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.usa.fred_utils import (
    JST,
    BaseMultiSeriesService,
    build_single_series_response,
    redis_client,
)


# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "usa" / "employment"


class NairuService(BaseMultiSeriesService):
    """NAIRU（自然失業率）/ 失業率 比較サービス"""

    # 必須設定
    SERIES_CONFIG = {
        "unrate": "UNRATE",   # 実際の失業率（U-3、月次）
        "nairu": "NROU",      # 自然失業率 / NAIRU（CBO、四半期）
    }
    REDIS_KEY = "fred:nairu:data"
    # 次回発表日は実際の失業率（雇用統計）のFMPスケジュールを使用
    ECONALPHA_ID = "unemployment_rate"
    CACHE_FILE = CACHE_DIR / "nairu_cache.json"
    INDICATOR_NAME = "NAIRU / Unemployment Rate"

    # オプション設定
    PRIMARY_SERIES = "unrate"  # 月次UNRATEをベースに四半期NROUをマージ
    VALUE_ROUND_DIGITS = 2
    CALCULATE_CHANGES = False  # 原数値（%）のみ。前月比/前年比は不要

    def get_nairu_data(self, start_date=None, force_refresh=False):
        """
        NAIRU / 失業率データを取得

        Args:
            start_date: 開始日 (YYYY-MM-DD)
            force_refresh: キャッシュを無視して再取得

        Returns:
            統一されたAPIレスポンス形式
            data: [{"date": str, "unrate": float | None, "nairu": float | None}, ...]
            ※ 末尾には実際の失業率（unrate=None）より先の四半期について
              CBOのNAIRU見通し（nairu のみ）が約10年分含まれる
        """
        return self.get_data(start_date=start_date, force_refresh=force_refresh)

    def _merge_series_data(
        self,
        series_data: Dict[str, List[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        """
        UNRATE（月次）と NROU（四半期、将来見通しを含む）を全日付の和集合でマージ。

        デフォルト実装は PRIMARY_SERIES（unrate）の日付のみを採用するため、
        実際の失業率より先のNROU見通し（CBO、約10年先まで）が脱落してしまう。
        ここでは両系列の全日付を残すことで、将来のNAIRU見通しを描画可能にする。
        """
        series_maps: Dict[str, Dict[str, float]] = {
            name: {item["date"]: item["value"] for item in data}
            for name, data in series_data.items()
        }

        all_dates = set()
        for date_map in series_maps.values():
            all_dates.update(date_map.keys())

        result: List[Dict[str, Any]] = []
        for date in sorted(all_dates):
            entry: Dict[str, Any] = {"date": date}
            for name in self.SERIES_CONFIG.keys():
                entry[name] = series_maps.get(name, {}).get(date)
            result.append(entry)

        return result

    def _latest_actual(self, data: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """実際の失業率（unrate）を持つ最新行を返す（将来のNAIRU見通し行を除外）"""
        for item in reversed(data):
            if item.get("unrate") is not None:
                return item
        return data[-1] if data else None

    def get_data(
        self,
        start_date: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        BaseMultiSeriesService.get_data のオーバーライド。

        将来のNAIRU見通し行（unrate=None）が data 末尾に含まれるため、
        キャッシュの鮮度判定に使う "latest" は「実際の失業率の最新行」に固定する。
        これを怠ると、固定された将来日付が常に "latest" となり last_updated が
        更新されず、毎リクエストで FRED を叩いてしまう。
        """
        # 1. キャッシュチェック
        cached_data, source = self._cache_manager.get_cached_data(force_refresh)
        if cached_data:
            return build_single_series_response(
                data=cached_data.get("data", []),
                cached=True,
                source=source,
                last_updated=cached_data.get("last_updated"),
                econalpha_id=self.ECONALPHA_ID,
            )

        # 2. APIから取得
        api_data = self._fetch_and_process(start_date)

        if api_data:
            latest = self._latest_actual(api_data)
            now_str = datetime.now(JST).isoformat()

            # FREDの更新遅延で実績URが進まなかった場合、last_updatedを維持
            existing_cache = redis_client.get(self.REDIS_KEY)
            existing_latest_date = None
            if existing_cache and existing_cache.get("latest"):
                existing_latest_date = existing_cache["latest"].get("date")
            new_latest_date = latest.get("date") if latest else None

            if existing_latest_date and new_latest_date and new_latest_date <= existing_latest_date:
                last_updated = existing_cache.get("last_updated", now_str)
                print(f"  {self.INDICATOR_NAME}: actual UR not newer (latest={new_latest_date}), keeping last_updated={last_updated}")
            else:
                last_updated = now_str

            self._cache_manager.save({
                "data": api_data,
                "latest": latest,
                "last_updated": last_updated,
            })

            return build_single_series_response(
                data=api_data,
                cached=False,
                source="api",
                last_updated=last_updated,
                econalpha_id=self.ECONALPHA_ID,
            )

        # 3. フォールバック
        fallback_data, fallback_source = self._cache_manager.get_fallback_data()
        if fallback_data:
            return build_single_series_response(
                data=fallback_data.get("data", []),
                cached=True,
                source=fallback_source,
                last_updated=fallback_data.get("last_updated"),
                econalpha_id=self.ECONALPHA_ID,
            )

        return build_single_series_response(
            data=[],
            cached=False,
            source="none",
            last_updated=None,
            econalpha_id=self.ECONALPHA_ID,
            error="No data available",
        )


# シングルトンインスタンス
nairu_service = NairuService()
