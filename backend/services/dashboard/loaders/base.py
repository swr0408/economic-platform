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

            # スケジュール時刻でキャッシュの鮮度をチェック
            if self._is_cache_stale(last_updated):
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
