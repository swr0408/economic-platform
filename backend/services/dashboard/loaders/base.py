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
from concurrent.futures import ThreadPoolExecutor

from core.redis_client import redis_client


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

        Returns:
            List[Optional[datetime]]: 発表日時のリスト（JST）
        """
        return []

    def _is_cache_stale(self, last_updated: Optional[str]) -> bool:
        """
        キャッシュが古いかどうかを判定（発表日時ベース方式）

        Args:
            last_updated: キャッシュの最終更新日時（ISO形式）

        Returns:
            True: 再取得が必要（発表日時を跨いだ場合）
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

    def _has_null_values(self, cached_data: Dict[str, Any]) -> bool:
        """
        キャッシュにNone値が含まれているかチェック

        一部の指標がNoneの場合、外部API取得失敗時のキャッシュと判断し、
        再取得を促す。全キーを対象にチェックする。

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

        return False

    def get_data(self) -> Dict[str, Any]:
        """
        データを取得（キャッシュ優先、last_updated判定）

        Returns:
            {
                "data": {...},
                "cached": bool,
                "last_updated": str
            }
        """
        # 1. キャッシュをチェック
        cached = self.get_cached()
        last_updated = None
        if cached:
            last_updated = cached.get("last_updated")

            # キャッシュに必要なキーが欠けている場合は再取得
            if self._is_cache_incomplete(cached):
                print(f"Cache incomplete for {self.COUNTRY_CODE}:{self.CATEGORY_CODE}, refreshing...")
            # キャッシュにNull値がある場合は再取得（外部API取得失敗の可能性）
            elif self._has_null_values(cached):
                print(f"Cache has null values for {self.COUNTRY_CODE}:{self.CATEGORY_CODE}, refreshing...")
            # スケジュール時刻でキャッシュの鮮度をチェック
            elif self._is_cache_stale(last_updated):
                print(f"Cache is stale for {self.COUNTRY_CODE}:{self.CATEGORY_CODE}, refreshing...")
            else:
                return cached

        # 2. キャッシュMISS or キャッシュが古い → データを取得
        # サブクラスに古くなった指標を通知（オーバーライド可能）
        self._prepare_for_refresh(last_updated)
        data = self.load_all()

        # 3. キャッシュに保存
        self.save_to_cache(data)

        return {
            "data": data,
            "cached": False,
            "last_updated": datetime.now(JST).isoformat(),
        }

    def _prepare_for_refresh(self, last_updated: Optional[str]) -> None:
        """
        データ再取得の前処理（サブクラスでオーバーライド可能）

        発表日時を過ぎた指標を検出し、force_refresh対象を設定する等の
        前処理を行う。

        Args:
            last_updated: 前回のキャッシュ更新日時（ISO形式）
        """
        pass

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

        Returns:
            {
                "data": {...},
                "cached": bool,
                "last_updated": str,
                "partial": True
            }
        """
        # サブクラスにload_lightがなければ通常のget_dataを使用
        if not hasattr(self, 'load_light'):
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

        サブクラスでload_heavy()が実装されている場合のみ使用可能。

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
            if has_nulls:
                print(f"Heavy cache has null values for {self.COUNTRY_CODE}:{self.CATEGORY_CODE}, refreshing...")
            elif not self._is_cache_stale(last_updated):
                return {
                    "data": cached.get("data", {}),
                    "cached": True,
                    "last_updated": last_updated,
                    "partial": True,
                }

        # 2. データを取得
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

    async def get_data_light_async(self) -> Dict[str, Any]:
        """軽量指標を非同期で取得"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, self.get_data_light)

    async def get_data_heavy_async(self) -> Dict[str, Any]:
        """重い指標を非同期で取得"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, self.get_data_heavy)

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
