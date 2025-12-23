"""
経済データサービス基底クラス
全ての国・カテゴリの経済データサービスはこのクラスを継承

キャッシュ更新判定:
- TTLではなくスケジュール時刻ベースで判定
- last_updatedがスケジュール時刻より古ければ再取得
"""
from abc import ABC, abstractmethod
from datetime import datetime, time
from typing import List, Dict, Any, Optional, Tuple
from zoneinfo import ZoneInfo

from core.database import SessionLocal
from core.redis_client import redis_client
from sqlalchemy import text


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")


class BaseEconomicService(ABC):
    """
    経済データサービスの基底クラス

    継承時に必要な設定:
    - INDICATOR_CODE: 経済指標コード (例: "US_POLICY_RATE", "JP_CPI")
    - CACHE_KEY_PREFIX: Redisキャッシュキーのプレフィックス (例: "usa:policy_rate")

    継承時に実装が必要なメソッド:
    - _fetch_from_external_api(): 外部APIからデータを取得

    オプション（スケジュール時刻ベースの更新判定用）:
    - get_schedule_time(): スケジュール時刻を返す（デフォルトはNone=常にキャッシュ使用）
    """

    # サブクラスで設定
    INDICATOR_CODE: str = ""
    CACHE_KEY_PREFIX: str = ""

    @property
    def cache_key(self) -> str:
        """Redisキャッシュキー"""
        return f"{self.CACHE_KEY_PREFIX}:data"

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
        キャッシュが古いかどうかを判定

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
                from datetime import timedelta
                yesterday_schedule = today_schedule - timedelta(days=1)
                return last_updated_dt < yesterday_schedule

        except Exception as e:
            print(f"Error parsing last_updated: {e}")
            return True

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        データを取得（Redis → DB → 外部API の順で取得）

        Args:
            force_refresh: Trueの場合、キャッシュを無視して再取得

        Returns:
            {
                "data": [...],
                "cached": bool,
                "source": "redis" | "database" | "api",
                "last_updated": str
            }
        """
        # 1. Redisキャッシュをチェック
        if not force_refresh:
            cached_data = redis_client.get(self.cache_key)
            if cached_data:
                last_updated = cached_data.get("last_updated")

                # スケジュール時刻ベースで古いかチェック
                if not self._is_cache_stale(last_updated):
                    return {
                        "data": cached_data.get("data", []),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated
                    }
                else:
                    print(f"Cache is stale for {self.INDICATOR_CODE}, refreshing...")

        # 2. DBからデータを取得
        db_data = self._load_from_database()
        if db_data and not force_refresh:
            # Redisにキャッシュ（TTLなし = 永続化、スケジュール判定で管理）
            cache_payload = {
                "data": db_data,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.cache_key, cache_payload, expire=0)

            return {
                "data": db_data,
                "cached": False,
                "source": "database",
                "last_updated": datetime.now(JST).isoformat()
            }

        # 3. 外部APIからデータを取得（キャッシュMISS or 強制更新 or キャッシュ古い）
        api_data = self._fetch_from_external_api()

        if api_data:
            # DBに保存
            self._save_to_database(api_data)

            # Redisにキャッシュ（TTLなし）
            cache_payload = {
                "data": api_data,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.cache_key, cache_payload, expire=0)

            return {
                "data": api_data,
                "cached": False,
                "source": "api",
                "last_updated": datetime.now(JST).isoformat()
            }

        # 4. API取得失敗 → 古いDBデータを返す
        if db_data:
            return {
                "data": db_data,
                "cached": True,
                "source": "database_stale",
                "last_updated": None,
                "error": "API fetch failed, using stale data"
            }

        return {
            "data": [],
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def refresh_cache(self) -> bool:
        """
        キャッシュを強制更新（手動更新API用）

        Returns:
            成功した場合True
        """
        result = self.get_data(force_refresh=True)
        return len(result.get("data", [])) > 0

    def invalidate_cache(self) -> bool:
        """Redisキャッシュを無効化"""
        return redis_client.delete(self.cache_key)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        cached_data = redis_client.get(self.cache_key)
        cache_exists = cached_data is not None
        last_updated = cached_data.get("last_updated") if cached_data else None
        is_stale = self._is_cache_stale(last_updated) if cache_exists else True

        return {
            "indicator_code": self.INDICATOR_CODE,
            "cache_key": self.cache_key,
            "exists": cache_exists,
            "last_updated": last_updated,
            "is_stale": is_stale,
            "schedule_time": str(self.get_schedule_time()) if self.get_schedule_time() else None
        }

    def _load_from_database(self) -> List[Dict[str, Any]]:
        """DBからデータを読み込み"""
        try:
            with SessionLocal() as session:
                # 指標IDを取得
                indicator_query = text("""
                    SELECT id FROM public.economic_indicators
                    WHERE code = :code
                """)
                result = session.execute(indicator_query, {"code": self.INDICATOR_CODE})
                row = result.fetchone()

                if not row:
                    print(f"Indicator {self.INDICATOR_CODE} not found in database")
                    return []

                indicator_id = row[0]

                # データを取得
                data_query = text("""
                    SELECT timestamp, value, metadata
                    FROM timeseries.economic_data
                    WHERE indicator_id = :indicator_id
                    ORDER BY timestamp ASC
                """)
                result = session.execute(data_query, {"indicator_id": indicator_id})
                rows = result.fetchall()

                data = self._format_db_rows(rows)

                print(f"Loaded {len(data)} records from database for {self.INDICATOR_CODE}")
                return data

        except Exception as e:
            print(f"Error loading from database: {e}")
            return []

    def _format_db_rows(self, rows) -> List[Dict[str, Any]]:
        """
        DBの行をフォーマット（サブクラスでオーバーライド可能）
        デフォルトは date/value 形式
        """
        data = []
        for row in rows:
            data.append({
                "date": row[0].strftime('%Y-%m-%d'),
                "value": float(row[1]) if row[1] else None
            })
        return data

    def _save_to_database(self, data: List[Dict[str, Any]]) -> bool:
        """DBにデータを保存"""
        try:
            with SessionLocal() as session:
                # 指標IDを取得
                indicator_query = text("""
                    SELECT id FROM public.economic_indicators
                    WHERE code = :code
                """)
                result = session.execute(indicator_query, {"code": self.INDICATOR_CODE})
                row = result.fetchone()

                if not row:
                    print(f"Indicator {self.INDICATOR_CODE} not found")
                    return False

                indicator_id = row[0]

                # UPSERT（存在すれば更新、なければ挿入）
                upsert_query = text("""
                    INSERT INTO timeseries.economic_data
                        (indicator_id, timestamp, value, unit, period)
                    VALUES
                        (:indicator_id, :timestamp, :value, :unit, :period)
                    ON CONFLICT (indicator_id, timestamp)
                    DO UPDATE SET
                        value = EXCLUDED.value,
                        source_update_time = CURRENT_TIMESTAMP
                """)

                for item in data:
                    session.execute(upsert_query, {
                        "indicator_id": indicator_id,
                        "timestamp": self._get_timestamp(item),
                        "value": self._get_value(item),
                        "unit": self._get_unit(),
                        "period": self._get_period(item)
                    })

                session.commit()
                print(f"Saved {len(data)} records to database for {self.INDICATOR_CODE}")
                return True

        except Exception as e:
            print(f"Error saving to database: {e}")
            import traceback
            traceback.print_exc()
            return False

    # --- サブクラスでオーバーライド可能なヘルパーメソッド ---

    def _get_timestamp(self, item: Dict) -> str:
        """データアイテムからタイムスタンプを取得"""
        return item.get("date", item.get("timestamp", ""))

    def _get_value(self, item: Dict) -> float:
        """データアイテムから値を取得"""
        return item.get("value", item.get("rate", 0))

    def _get_unit(self) -> str:
        """単位を取得"""
        return "%"

    def _get_period(self, item: Dict) -> str:
        """期間を取得（YYYY-MM形式）"""
        timestamp = self._get_timestamp(item)
        return timestamp[:7] if timestamp else ""

    # --- サブクラスで必ず実装が必要なメソッド ---

    @abstractmethod
    def _fetch_from_external_api(self) -> List[Dict[str, Any]]:
        """
        外部APIからデータを取得

        Returns:
            パース済みのデータリスト
        """
        pass
