"""
ダッシュボードローダー基底クラス
各国・カテゴリ別ローダーはこのクラスを継承して実装

キャッシュ更新判定: 発表日時ベース判定方式
- ダッシュボードキャッシュはTTLなし（永続化）
- 各サービスの発表日時をチェックし、last_updatedより後に発表があれば再取得
- 個別データ（タームプレミアム、FedWatch等）のTTLは各サービスで管理
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor, Future, as_completed

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

# ダッシュボード国コード → FMP 経済カレンダー国コードのマッピング
_DASHBOARD_TO_FMP_COUNTRY: Dict[str, List[str]] = {
    "usa": ["US"],
    "japan": ["JP"],
    "uk": ["GB", "UK"],
    "eurozone": ["EU", "DE", "FR", "ES"],
    "china": ["CN"],
    "australia": ["AU"],
    "canada": ["CA"],
    "newzealand": ["NZ"],
    "switzerland": ["CH"],
    "global": ["US", "JP", "EU", "CN", "GB", "KR", "TW"],  # 主要国の代表指標 + 韓国/台湾 (global/economy の輸出・PMI)
}

# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
ET = ZoneInfo("America/New_York")


class BaseDashboardLoader(ABC):
    """
    ダッシュボードデータローダーの基底クラス

    継承時に設定が必要:
    - COUNTRY_CODE: 国コード (例: "usa", "japan")
    - CATEGORY_CODE: カテゴリコード (例: "policy", "economy")

    継承時に実装が必要:
    - load_all(): 全データを取得して辞書で返す
    - get_release_datetimes(): 各指標の発表日時リストを返す（発表日時ベース判定用）
    """

    COUNTRY_CODE: str = ""
    CATEGORY_CODE: str = ""

    # スレッドプールエグゼキューター（同期関数を非同期で実行するため）
    _executor = ThreadPoolExecutor(max_workers=10)

    @property
    def cache_key(self) -> str:
        """Redisキャッシュキー"""
        return f"{self.COUNTRY_CODE}:{self.CATEGORY_CODE}:dashboard:v1"

    def get_release_datetimes(self) -> List[Optional[datetime]]:
        """
        各指標の発表日時リストを返す（サブクラスでオーバーライド）

        各サービスが持つnext_release情報を元に、発表日時のリストを返す。
        発表日時が不明な指標はNoneを含めてよい。

        デフォルト実装: FMP経済カレンダーDBから該当国の直近発表日時を自動取得。
        サブクラスで個別指標ごとの精密な判定が必要な場合はオーバーライドする。

        Returns:
            List[Optional[datetime]]: 発表日時のリスト（JST）
        """
        return self._get_release_datetimes_from_fmp_calendar()

    # キャッシュの最大年齢（時間）— これを超えたら発表日時に関係なく再取得
    # FMP カレンダーDB が一時的に空でも、最低限の鮮度を保証するセーフティネット
    MAX_CACHE_AGE_HOURS: int = 24

    def _is_cache_stale(self, last_updated: Optional[str]) -> bool:
        """
        キャッシュが古いかどうかを判定（発表日時ベース + 最大年齢フォールバック）

        Args:
            last_updated: キャッシュの最終更新日時（ISO形式）

        Returns:
            True: 再取得が必要（発表日時を跨いだ場合 or 最大年齢超過）
            False: キャッシュを使用可能
        """
        if last_updated is None:
            return True

        try:
            # last_updatedをパース
            last_updated_dt = datetime.fromisoformat(last_updated)
            if last_updated_dt.tzinfo is None:
                last_updated_dt = last_updated_dt.replace(tzinfo=JST)

            now = datetime.now(JST)

            # フォールバック: 最大年齢超過チェック
            # 発表日時情報が無い/失われた場合のセーフティネット
            age_hours = (now - last_updated_dt).total_seconds() / 3600
            if age_hours > self.MAX_CACHE_AGE_HOURS:
                print(
                    f"Cache exceeded max age for {self.COUNTRY_CODE}:{self.CATEGORY_CODE} "
                    f"({age_hours:.1f}h > {self.MAX_CACHE_AGE_HOURS}h)"
                )
                return True

            # 各指標の発表日時をチェック
            release_datetimes = self.get_release_datetimes()

            # 発表日時リストが空の場合はキャッシュを使用
            if not release_datetimes:
                return False

            for release_dt in release_datetimes:
                if release_dt is None:
                    continue

                # タイムゾーンがない場合はJSTとして扱う
                if release_dt.tzinfo is None:
                    release_dt = release_dt.replace(tzinfo=JST)

                # last_updated < 発表日時 <= now なら更新が必要
                # （最終更新後に発表があった場合）
                if last_updated_dt < release_dt <= now:
                    print(f"New release detected: {release_dt.isoformat()}")
                    return True

                # データソース反映ラグ対策:
                # 発表後60分以内にキャッシュが更新されている場合、
                # データソース（FRED等）がまだ反映されていない可能性がある。
                # 発表から60分経過するまでは再取得を試みる。
                if release_dt <= last_updated_dt <= now:
                    minutes_since_release = (last_updated_dt - release_dt).total_seconds() / 60
                    minutes_since_update = (now - last_updated_dt).total_seconds() / 60
                    if minutes_since_release < 60 and minutes_since_update > 10:
                        print(f"Post-release recheck: {release_dt.isoformat()} "
                              f"(updated {minutes_since_release:.0f}min after release, "
                              f"{minutes_since_update:.0f}min ago)")
                        return True

            return False

        except Exception as e:
            print(f"Error checking cache staleness: {e}")
            return True

    @abstractmethod
    def load_all(self) -> Dict[str, Any]:
        """
        全データを取得（サブクラスで実装必須）

        Returns:
            {
                "indicator_name": data,
                ...
            }
        """
        pass

    def get_cached(self) -> Optional[Dict[str, Any]]:
        """Redisキャッシュからデータを取得"""
        cached = redis_client.get(self.cache_key)
        if cached:
            return {
                "data": cached.get("data", {}),
                "cached": True,
                "last_updated": cached.get("last_updated"),
            }
        return None

    def save_to_cache(self, data: Dict[str, Any]) -> bool:
        """データをRedisキャッシュに保存（TTLなし、last_updated判定方式）"""
        cache_payload = {
            "data": data,
            "last_updated": datetime.now(JST).isoformat(),
        }
        return redis_client.set(self.cache_key, cache_payload, expire=0)

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.cache_key)

    def get_expected_keys(self) -> List[str]:
        """
        期待されるデータキーのリストを返す（サブクラスでオーバーライド）

        新しい指標が追加された場合、キャッシュに含まれていなければ
        自動的に再取得するために使用。

        Returns:
            List[str]: 期待されるデータキーのリスト
        """
        return []

    def _is_cache_incomplete(self, cached_data: Dict[str, Any]) -> bool:
        """
        キャッシュに必要な全キーが含まれているかチェック

        Args:
            cached_data: キャッシュされたデータ

        Returns:
            True: 一部のキーが欠けている（再取得が必要）
            False: 全キーが含まれている
        """
        expected_keys = self.get_expected_keys()
        if not expected_keys:
            return False

        data = cached_data.get("data", {})
        for key in expected_keys:
            if key not in data:
                print(f"Cache missing key '{key}' for {self.COUNTRY_CODE}:{self.CATEGORY_CODE}")
                return True

        return False

    # `latest` 内でNoneが許容されるフィールド（予想値・改定値・将来発表日など）
    # qoq / mom / composite は主指標（yoy / value / stock）と並ぶ二次/合成指標で、
    # 発表ラグや元データの構造によりNoneとなることがあるため許容する
    _LATEST_NULLABLE_FIELDS = frozenset({
        "date", "release_date", "forecast", "revised", "estimate",
        "expected", "previous", "actual",
        "qoq", "mom", "composite",
    })
    _LATEST_NULLABLE_PREFIXES = ("next_",)
    _LATEST_NULLABLE_SUFFIXES = (
        "_forecast", "_revised", "_estimate", "_expected", "_previous",
        "_qoq", "_mom",
    )

    def _has_null_values(self, cached_data: Dict[str, Any]) -> bool:
        """
        キャッシュにNone値が含まれているかチェック

        2段階で検査する:
        1. トップレベルの指標自体がNone（取得失敗）
        2. 各指標の`latest`内の主要フィールドがNone（部分的取得失敗）
           - 例: retail_salesのRSAFSだけ取得失敗 → latest.value=None

        Args:
            cached_data: キャッシュされたデータ

        Returns:
            True: None値のキーが存在する（再取得推奨）
            False: 全キーに値がある
        """
        data = cached_data.get("data", {})
        if not isinstance(data, dict):
            return False

        for key, value in data.items():
            # next_*キーは次回発表日情報で取得失敗が許容される（スキップ）
            if key.startswith("next_"):
                continue
            if value is None:
                print(f"Cache has null value for '{key}' in {self.COUNTRY_CODE}:{self.CATEGORY_CODE}")
                return True
            # 指標がdictの場合、内部の`latest`フィールドも検査
            if isinstance(value, dict) and self._has_broken_latest(value, key):
                return True

        return False

    def _has_broken_latest(self, indicator: Dict[str, Any], parent_key: str) -> bool:
        """
        指標dict内の`latest`フィールドに、許容されない None があるかチェック

        ネストされたdict（例: personal_income.nominal.latest）も再帰的に検査する。

        Args:
            indicator: 指標データのdict
            parent_key: ログ用の親キー名

        Returns:
            True: 主要フィールドにNoneがある（取得失敗の可能性）
            False: 問題なし
        """
        latest = indicator.get("latest")
        if isinstance(latest, dict):
            # 「取得失敗」と判定するのは、必須フィールド（=許容されないフィールド）が
            # **すべて** None の場合のみ。一部の二次指標が発表ラグでNoneになっても
            # 主指標に値があれば「取得失敗」とは見なさず再フェッチをトリガーしない。
            required_total = 0
            required_null = 0
            for k, v in latest.items():
                if k in self._LATEST_NULLABLE_FIELDS:
                    continue
                if any(k.startswith(p) for p in self._LATEST_NULLABLE_PREFIXES):
                    continue
                if any(k.endswith(s) for s in self._LATEST_NULLABLE_SUFFIXES):
                    continue
                required_total += 1
                if v is None:
                    required_null += 1

            if required_total > 0 and required_null == required_total:
                print(
                    f"Cache has all-null required fields in {parent_key}.latest "
                    f"for {self.COUNTRY_CODE}:{self.CATEGORY_CODE}"
                )
                return True

        # ネストされたdict（nominal/realなど）も検査
        for k, v in indicator.items():
            if k == "latest":
                continue
            if isinstance(v, dict):
                if self._has_broken_latest(v, f"{parent_key}.{k}"):
                    return True

        return False

    def get_data(self) -> Dict[str, Any]:
        """
        データを取得（キャッシュ優先、last_updated判定）

        フロー:
        - キャッシュ無し                              → ブロッキング再取得
        - キャッシュ欠損キー / latest全null           → ブロッキング再取得
          （データ品質問題のためユーザに stale を返したくない）
        - キャッシュ stale だがデータ健全           → SWR: stale 即返し + 裏で更新
          （30秒タイムアウト対策。外部API遅延がユーザに見えない）
        - キャッシュ fresh                             → そのまま返却

        Returns:
            {
                "data": {...},
                "cached": bool,
                "last_updated": str,
                "revalidating": bool  # SWR で裏更新が走っている場合のみ True
            }
        """
        cached = self.get_cached()
        last_updated = None

        if cached:
            last_updated = cached.get("last_updated")

            # データ品質問題 → ブロッキング再取得
            if self._is_cache_incomplete(cached):
                print(f"Cache incomplete for {self.COUNTRY_CODE}:{self.CATEGORY_CODE}, refreshing (blocking)...")
            elif self._has_null_values(cached):
                print(f"Cache has null values for {self.COUNTRY_CODE}:{self.CATEGORY_CODE}, refreshing (blocking)...")
            # 鮮度切れだがデータは健全 → SWR
            elif self._is_cache_stale(last_updated):
                print(f"Cache is stale for {self.COUNTRY_CODE}:{self.CATEGORY_CODE}, returning stale + background refresh...")
                self._trigger_background_refresh(last_updated)
                return {
                    **cached,
                    "revalidating": True,
                }
            else:
                return cached

        # キャッシュMISS or データ品質問題 → ブロッキング再取得
        self._prepare_for_refresh(last_updated)
        data = self.load_all()
        self.save_to_cache(data)

        return {
            "data": data,
            "cached": False,
            "last_updated": datetime.now(JST).isoformat(),
        }

    def _trigger_background_refresh(self, last_updated: Optional[str]) -> None:
        """SWR バックグラウンド再取得を起動。

        同一 cache_key の再取得が既に走っている場合はスキップ（thundering herd 防止）。
        サブクラスで `_stale_indicators` を共有する場合に備え、
        バックグラウンドでは新規ローダーインスタンスを使う。
        """
        try:
            from services.browser.stale_while_revalidate import background_revalidate
        except ImportError:
            from backend.services.browser.stale_while_revalidate import background_revalidate

        cls = type(self)

        def _refresh() -> None:
            worker = cls()
            worker._prepare_for_refresh(last_updated)
            data = worker.load_all()
            worker.save_to_cache(data)

        background_revalidate(f"swr:{self.cache_key}", _refresh)

    def _prepare_for_refresh(self, last_updated: Optional[str]) -> None:
        """
        データ再取得の前処理（サブクラスでオーバーライド可能）

        発表日時を過ぎた指標を検出し、force_refresh対象を設定する等の
        前処理を行う。

        デフォルト実装: _stale_indicators 属性が存在すれば {"all"} を設定し、
        全指標を force_refresh 対象にする。サブクラスが _detect_stale_indicators()
        で個別判定する場合はオーバーライドする。

        Args:
            last_updated: 前回のキャッシュ更新日時（ISO形式）
        """
        if hasattr(self, '_stale_indicators'):
            self._stale_indicators = {"all"}

    async def get_data_async(self) -> Dict[str, Any]:
        """
        非同期でデータを取得（FastAPIエンドポイント用）

        既存の同期サービスを非同期コンテキストで実行するためのラッパー
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, self.get_data)

    def get_data_light(self) -> Dict[str, Any]:
        """
        軽量指標のみを取得（プログレッシブレンダリング用）

        サブクラスでload_light()が実装されている場合のみ使用可能。
        未実装の場合はキャッシュを優先し、なければ通常の get_data() を使用。

        Returns:
            {
                "data": {...},
                "cached": bool,
                "last_updated": str,
                "partial": True
            }
        """
        # サブクラスにload_lightがない場合:
        # キャッシュが新鮮ならそのまま返す
        # キャッシュが古い → SWR: 古いデータを即返し + バックグラウンドで get_data 実行
        # キャッシュなし → 通常の get_data を使用（初回のみブロック）
        if not hasattr(self, 'load_light'):
            cached = self.get_cached()
            if cached:
                last_updated = cached.get("last_updated")
                is_stale = self._is_cache_stale(last_updated)
                has_nulls = self._has_null_values(cached)

                if not is_stale and not has_nulls:
                    # 新鮮なキャッシュ → そのまま返す
                    return {
                        "data": cached.get("data", {}),
                        "cached": True,
                        "last_updated": last_updated,
                        "partial": True,
                    }

                # SWR: 古い or null値あり → 即返し + バックグラウンドで更新
                from services.browser.stale_while_revalidate import background_revalidate
                background_revalidate(
                    f"swr:{self.cache_key}:light-fallback",
                    lambda: self.get_data(),  # invalidate + load_all + save
                )
                return {
                    "data": cached.get("data", {}),
                    "cached": True,
                    "last_updated": last_updated,
                    "partial": True,
                    "revalidating": True,
                }
            # キャッシュなし → 通常の get_data を使用（初回のみブロック）
            return self.get_data()

        # 1. キャッシュをチェック（軽量指標用）
        light_cache_key = f"{self.cache_key}:light"
        cached = redis_client.get(light_cache_key)
        last_updated = None

        if cached:
            last_updated = cached.get("last_updated")
            cached_wrapper = {"data": cached.get("data", {})}
            has_nulls = self._has_null_values(cached_wrapper)
            if has_nulls:
                print(f"Light cache has null values for {self.COUNTRY_CODE}:{self.CATEGORY_CODE}, refreshing...")
            elif not self._is_cache_stale(last_updated):
                return {
                    "data": cached.get("data", {}),
                    "cached": True,
                    "last_updated": last_updated,
                    "partial": True,
                }

        # 2. データを取得
        self._prepare_for_refresh(last_updated)
        data = self.load_light()

        # 3. キャッシュに保存
        cache_payload = {
            "data": data,
            "last_updated": datetime.now(JST).isoformat(),
        }
        redis_client.set(light_cache_key, cache_payload, expire=0)

        return {
            "data": data,
            "cached": False,
            "last_updated": cache_payload["last_updated"],
            "partial": True,
        }

    def get_data_heavy(self) -> Dict[str, Any]:
        """
        重い指標のみを取得（プログレッシブレンダリング用）

        Stale-While-Revalidate パターン:
        - キャッシュが新鮮ならそのまま返す
        - キャッシュが古い（stale）がデータは存在する → 古いデータを即返し、バックグラウンドで更新
        - キャッシュが存在しない → 同期で取得

        Returns:
            {
                "data": {...},
                "cached": bool,
                "last_updated": str,
                "partial": True
            }
        """
        # サブクラスにload_heavyがなければ空を返す
        if not hasattr(self, 'load_heavy'):
            return {
                "data": {},
                "cached": False,
                "last_updated": None,
                "partial": True,
            }

        # 1. キャッシュをチェック（重い指標用）
        heavy_cache_key = f"{self.cache_key}:heavy"
        cached = redis_client.get(heavy_cache_key)
        last_updated = None

        if cached:
            last_updated = cached.get("last_updated")
            cached_wrapper = {"data": cached.get("data", {})}
            has_nulls = self._has_null_values(cached_wrapper)
            is_stale = self._is_cache_stale(last_updated)

            if not has_nulls and not is_stale:
                # キャッシュが新鮮かつ完全 → そのまま返す
                return {
                    "data": cached.get("data", {}),
                    "cached": True,
                    "last_updated": last_updated,
                    "partial": True,
                }

            # SWR: キャッシュが古い or null値あり → 古いデータを即返し + バックグラウンド更新
            from services.browser.stale_while_revalidate import background_revalidate
            reason = "null values" if has_nulls else "stale"
            launched = background_revalidate(
                f"swr:{heavy_cache_key}",
                lambda: self._refresh_heavy_cache(heavy_cache_key, last_updated),
            )
            if launched:
                logger.info(
                    f"[SWR] heavy cache {reason} for {self.COUNTRY_CODE}:{self.CATEGORY_CODE}, "
                    f"returning cached data and revalidating in background"
                )
            return {
                "data": cached.get("data", {}),
                "cached": True,
                "last_updated": last_updated,
                "partial": True,
                "revalidating": True,
            }

        # 2. キャッシュなし → 同期で取得
        self._prepare_for_refresh(last_updated)
        data = self.load_heavy()

        # 3. キャッシュに保存
        cache_payload = {
            "data": data,
            "last_updated": datetime.now(JST).isoformat(),
        }
        redis_client.set(heavy_cache_key, cache_payload, expire=0)

        return {
            "data": data,
            "cached": False,
            "last_updated": cache_payload["last_updated"],
            "partial": True,
        }

    def _refresh_heavy_cache(self, heavy_cache_key: str, last_updated: Optional[str]) -> None:
        """バックグラウンドで heavy キャッシュを更新する"""
        self._prepare_for_refresh(last_updated)
        data = self.load_heavy()
        cache_payload = {
            "data": data,
            "last_updated": datetime.now(JST).isoformat(),
        }
        redis_client.set(heavy_cache_key, cache_payload, expire=0)
        logger.info(f"[SWR] heavy cache updated for {self.COUNTRY_CODE}:{self.CATEGORY_CODE}")

    async def get_data_light_async(self) -> Dict[str, Any]:
        """軽量指標を非同期で取得"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, self.get_data_light)

    async def get_data_heavy_async(self) -> Dict[str, Any]:
        """重い指標を非同期で取得"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, self.get_data_heavy)

    # future.result() のデフォルトタイムアウト (秒)
    FUTURE_TIMEOUT_SECONDS: int = 45

    def _collect_futures(
        self,
        futures: Dict[Future, str],
        result: Dict[str, Any],
        timeout: Optional[int] = None,
    ) -> None:
        """ThreadPoolExecutor の futures を収集し、result dict に格納する。

        個々の future にタイムアウトを適用し、1 つのタスクがハングしても
        他のタスクを待たずに先に進めるようにする。

        Args:
            futures: {future: key_name} のマッピング
            result: 結果を格納する辞書（key_name → value）
            timeout: future ごとのタイムアウト秒。None の場合はクラスデフォルト。
        """
        t = timeout or self.FUTURE_TIMEOUT_SECONDS
        for future in as_completed(futures, timeout=t + 5):
            key = futures[future]
            try:
                result[key] = future.result(timeout=t)
            except TimeoutError:
                logger.warning(
                    f"[{self.COUNTRY_CODE}:{self.CATEGORY_CODE}] "
                    f"future timeout for '{key}' after {t}s"
                )
                result[key] = None
            except Exception as e:
                logger.warning(
                    f"[{self.COUNTRY_CODE}:{self.CATEGORY_CODE}] "
                    f"error fetching '{key}': {e}"
                )
                result[key] = None

    def _get_release_datetimes_from_fmp_calendar(self) -> List[Optional[datetime]]:
        """FMP 経済カレンダー DB から、この国の直近の発表日時を取得する。

        get_release_datetimes() が未実装のローダーで、FMP カレンダーにある
        発表イベントを自動検知するための汎用メソッド。

        過去7日以内に発表時刻を過ぎたイベントの日時を返す。
        actual IS NULL でも発表時刻を過ぎていれば対象に含める
        （FMP が actual を遅延して入れるケースに対応）。

        _is_cache_stale() は「last_updated < release_dt <= now」で判定するため、
        last_updated 以降に発表時刻を過ぎたイベントがあれば stale と判定される。

        Returns:
            発表日時（JST）のリスト
        """
        fmp_countries = _DASHBOARD_TO_FMP_COUNTRY.get(self.COUNTRY_CODE)
        if not fmp_countries:
            return []

        try:
            from core.database import SessionLocal
            from sqlalchemy import text

            now = datetime.now(JST)
            seven_days_ago = now - timedelta(days=7)

            placeholders = ", ".join([f":c{i}" for i in range(len(fmp_countries))])
            params = {f"c{i}": c for i, c in enumerate(fmp_countries)}
            params["since"] = seven_days_ago.astimezone(ZoneInfo("UTC"))

            with SessionLocal() as session:
                rows = session.execute(
                    text(f"""
                        SELECT DISTINCT datetime_utc
                        FROM economic_calendar_events
                        WHERE country IN ({placeholders})
                          AND datetime_utc >= :since
                          AND datetime_utc <= NOW()
                        ORDER BY datetime_utc DESC
                        LIMIT 50
                    """),
                    params,
                ).fetchall()

            result: List[Optional[datetime]] = []
            utc = ZoneInfo("UTC")
            for row in rows:
                dt = row[0]
                if dt is None:
                    continue
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=utc)
                result.append(dt.astimezone(JST))

            return result

        except Exception as e:
            logger.warning(
                f"[{self.COUNTRY_CODE}:{self.CATEGORY_CODE}] "
                f"Failed to fetch FMP calendar release datetimes: {e}"
            )
            return []

    def _safe_get(self, func, default=None) -> Any:
        """
        サービス呼び出しを安全に実行（1つ失敗しても他に影響しない）

        Args:
            func: データ取得関数
            default: エラー時のデフォルト値

        Returns:
            取得したデータ、またはデフォルト値
        """
        try:
            result = func()
            return result.get("data") if isinstance(result, dict) else result
        except Exception as e:
            print(f"Error in dashboard loader: {e}")
            return default

    def _invalidate_service_caches(self, services: list) -> None:
        """
        複数サービスのキャッシュを一括無効化

        Args:
            services: (サービスインスタンス, サービス名) のタプルのリスト
                      例: [(retail_sales_service, "Retail Sales"), ...]
        """
        for service, name in services:
            try:
                service.invalidate_cache()
                print(f"{name} Redis cache invalidated")
            except Exception as e:
                print(f"Error invalidating {name} cache: {e}")

    def _get_release_datetime_from_service(
        self,
        get_data_func,
        release_hour_et: int = 8,
        release_minute_et: int = 30,
        indicator_name: str = "unknown"
    ) -> Optional[datetime]:
        """
        サービスからnext_releaseを取得し、発表日時（JST）を返す

        共通パターン:
        1. サービスからデータ取得（キャッシュ優先）
        2. next_release.dateをパース
        3. 発表時刻（ET）を付与してJSTに変換

        Args:
            get_data_func: データ取得関数（引数なし、dictを返す）
            release_hour_et: 発表時刻の時（ET）
            release_minute_et: 発表時刻の分（ET）
            indicator_name: エラーログ用の指標名

        Returns:
            発表日時（JST）、取得できない場合はNone

        使用例:
            def _get_retail_sales_release_datetime(self) -> Optional[datetime]:
                from services.usa.retail_sales_service import retail_sales_service
                return self._get_release_datetime_from_service(
                    retail_sales_service.get_retail_sales_data,
                    release_hour_et=8,
                    release_minute_et=30,
                    indicator_name="Retail Sales"
                )
        """
        try:
            data = get_data_func()
            next_release = data.get("next_release")

            if not next_release:
                return None

            date_str = next_release.get("date")
            if not date_str:
                return None

            # YYYY-MM-DD形式をパース
            try:
                base_date = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                return None

            # 発表時刻（ET）をJSTに変換
            release_et = datetime(
                base_date.year, base_date.month, base_date.day,
                release_hour_et, release_minute_et,
                tzinfo=ET
            )
            return release_et.astimezone(JST)

        except Exception as e:
            print(f"Error getting {indicator_name} release datetime: {e}")
            return None

    def _get_last_release_datetime_from_fmp(
        self,
        econalpha_id: str,
        release_hour_et: int = 8,
        release_minute_et: int = 30,
        indicator_name: str = "unknown",
        country: str = "usa"
    ) -> Optional[datetime]:
        """
        FMP APIから直近の過去発表日時（JST）を取得

        next_releaseは発表直後に次回日付へ切り替わるため、
        直近の過去リリースも確認してstale検出の見逃しを防ぐ。

        Args:
            econalpha_id: FMPマッピングID
            release_hour_et: 発表時刻の時（ET）— country="usa"の場合のみ使用
            release_minute_et: 発表時刻の分（ET）— country="usa"の場合のみ使用
            indicator_name: エラーログ用の指標名
            country: 国コード ("usa", "japan", "eurozone")

        Returns:
            直近の過去発表日時（JST）、取得できない場合はNone
        """
        try:
            if country == "japan":
                from services.japan.fmp_next_release_utils import get_last_release_from_fmp
            elif country == "eurozone":
                from services.eurozone.fmp_next_release_utils import get_last_release_from_fmp
            else:
                from services.usa.fmp_next_release_utils import get_last_release_from_fmp

            last_release = get_last_release_from_fmp(econalpha_id)
            if not last_release:
                return None

            # JP/EU: datetime_jstフィールドを直接使用
            if country in ("japan", "eurozone"):
                datetime_jst_str = last_release.get("datetime_jst")
                if datetime_jst_str:
                    return datetime.fromisoformat(datetime_jst_str)
                # datetime_jstがない場合はdateフィールドにフォールバック
                date_str = last_release.get("date")
                if not date_str:
                    return None
                try:
                    base_date = datetime.strptime(date_str, "%Y-%m-%d")
                except ValueError:
                    return None
                # JP/EUはデフォルト8:30 JSTとする
                return datetime(
                    base_date.year, base_date.month, base_date.day,
                    8, 30, tzinfo=JST
                )

            # USA: dateフィールド + ET時刻で構築
            date_str = last_release.get("date")
            if not date_str:
                return None

            try:
                base_date = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                return None

            release_et = datetime(
                base_date.year, base_date.month, base_date.day,
                release_hour_et, release_minute_et,
                tzinfo=ET
            )
            return release_et.astimezone(JST)

        except Exception as e:
            print(f"Error getting {indicator_name} last release datetime: {e}")
            return None

    def _is_stale_by_release(
        self,
        last_updated_dt: datetime,
        now: datetime,
        next_release: Optional[datetime],
        last_release: Optional[datetime] = None
    ) -> bool:
        """
        next_release と last_release の両方を使ってstale判定

        next_releaseだけでは発表直後に次回日付へ切り替わった場合に
        stale検出窓を見逃すため、last_releaseもフォールバックとして使う。

        Args:
            last_updated_dt: ダッシュボードキャッシュの最終更新日時
            now: 現在日時
            next_release: 次回発表日時（JST）
            last_release: 直近の過去発表日時（JST）

        Returns:
            staleならTrue
        """
        if next_release and last_updated_dt < next_release <= now:
            return True
        if last_release and last_updated_dt < last_release <= now:
            return True
        return False
