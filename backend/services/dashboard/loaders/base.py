"""
ダッシュボードローダー基底クラス
各国・カテゴリ別ローダーはこのクラスを継承して実装

キャッシュ更新判定: last_updated判定方式（スケジュール時刻ベース）
- ダッシュボードキャッシュはTTLなし（永続化）
- スケジュール時刻を過ぎたらlast_updatedと比較して再取得判定
- 個別データ（タームプレミアム、FedWatch等）のTTLは各サービスで管理
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
import asyncio
from concurrent.futures import ThreadPoolExecutor

from core.redis_client import redis_client


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")


class BaseDashboardLoader(ABC):
    """
    ダッシュボードデータローダーの基底クラス

    継承時に設定が必要:
    - COUNTRY_CODE: 国コード (例: "usa", "japan")
    - CATEGORY_CODE: カテゴリコード (例: "policy", "economy")

    継承時に実装が必要:
    - load_all(): 全データを取得して辞書で返す

    オプション（スケジュール時刻ベースの更新判定用）:
    - get_schedule_time(): スケジュール時刻を返す（デフォルトはNone=キャッシュ常時使用）
    """

    COUNTRY_CODE: str = ""
    CATEGORY_CODE: str = ""

    # スレッドプールエグゼキューター（同期関数を非同期で実行するため）
    _executor = ThreadPoolExecutor(max_workers=10)

    @property
    def cache_key(self) -> str:
        """Redisキャッシュキー"""
        return f"{self.COUNTRY_CODE}:{self.CATEGORY_CODE}:dashboard:v1"

    def get_schedule_time(self) -> Optional[time]:
        """
        スケジュール時刻を返す（日本時間）
        サブクラスでオーバーライドして設定

        Returns:
            time: 毎日の更新時刻（例: time(6, 0) = 6:00 JST）
            None: スケジュール判定なし（キャッシュがあれば常に使用）
        """
        return None

    def _is_cache_stale(self, last_updated: Optional[str]) -> bool:
        """
        キャッシュが古いかどうかを判定（last_updated方式）

        Args:
            last_updated: キャッシュの最終更新日時（ISO形式）

        Returns:
            True: 再取得が必要
            False: キャッシュを使用可能
        """
        if last_updated is None:
            return True

        schedule_time = self.get_schedule_time()
        if schedule_time is None:
            # スケジュール設定なし → キャッシュを使用
            return False

        try:
            # last_updatedをパース
            last_updated_dt = datetime.fromisoformat(last_updated)
            if last_updated_dt.tzinfo is None:
                last_updated_dt = last_updated_dt.replace(tzinfo=JST)

            now = datetime.now(JST)
            today_schedule = datetime.combine(now.date(), schedule_time, tzinfo=JST)

            # 今日のスケジュール時刻を経過しているか
            if now >= today_schedule:
                # 今日のスケジュール時刻以降 → last_updatedが今日のスケジュール時刻より前なら再取得
                return last_updated_dt < today_schedule
            else:
                # 今日のスケジュール時刻より前 → 昨日のスケジュール時刻と比較
                yesterday_schedule = today_schedule - timedelta(days=1)
                return last_updated_dt < yesterday_schedule

        except Exception as e:
            print(f"Error parsing last_updated: {e}")
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
        if cached:
            last_updated = cached.get("last_updated")

            # スケジュール時刻でキャッシュの鮮度をチェック
            if self._is_cache_stale(last_updated):
                print(f"Cache is stale for {self.COUNTRY_CODE}:{self.CATEGORY_CODE}, refreshing...")
            else:
                return cached

        # 2. キャッシュMISS or キャッシュが古い → データを取得
        data = self.load_all()

        # 3. キャッシュに保存
        self.save_to_cache(data)

        return {
            "data": data,
            "cached": False,
            "last_updated": datetime.now(JST).isoformat(),
        }

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
