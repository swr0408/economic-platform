"""
Redisクライアント
キャッシュ層として使用
"""
import os
import json
import redis
from typing import Optional, Any

# 環境変数からRedis URLを取得
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# キャッシュTTL設定（秒）
# 注: 経済指標データはlast_updated判定方式を使用するため、TTLは主にダッシュボードキャッシュ用
CACHE_TTL_SHORT = 60        # 1分（リアルタイムデータ用）
CACHE_TTL_MEDIUM = 300      # 5分（ダッシュボード集約キャッシュ用）
CACHE_TTL_LONG = 3600       # 1時間（汎用）
CACHE_TTL_DAY = 86400       # 1日


class RedisClient:
    """Redis接続クライアント（同期版）"""

    def __init__(self):
        self._client: Optional[redis.Redis] = None

    @property
    def client(self) -> redis.Redis:
        """遅延初期化でRedisクライアントを取得"""
        if self._client is None:
            self._client = redis.from_url(
                REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
        return self._client

    def ping(self) -> bool:
        """接続テスト"""
        try:
            return self.client.ping()
        except Exception as e:
            print(f"Redis ping failed: {e}")
            return False

    def get(self, key: str) -> Optional[Any]:
        """キャッシュ取得"""
        try:
            value = self.client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            print(f"Redis get error: {e}")
            return None

    def set(self, key: str, value: Any, expire: int = CACHE_TTL_LONG) -> bool:
        """
        キャッシュ保存

        Args:
            key: キャッシュキー
            value: 保存する値
            expire: TTL（秒）、0の場合はTTLなし（永続化）
        """
        try:
            if expire > 0:
                self.client.set(
                    key,
                    json.dumps(value, default=str),
                    ex=expire
                )
            else:
                # TTLなし（last_updated判定方式用）
                self.client.set(
                    key,
                    json.dumps(value, default=str)
                )
            return True
        except Exception as e:
            print(f"Redis set error: {e}")
            return False

    def delete(self, key: str) -> bool:
        """キャッシュ削除"""
        try:
            self.client.delete(key)
            return True
        except Exception as e:
            print(f"Redis delete error: {e}")
            return False

    def delete_pattern(self, pattern: str) -> int:
        """パターンマッチでキャッシュ一括削除"""
        try:
            keys = list(self.client.scan_iter(match=pattern))
            if keys:
                return self.client.delete(*keys)
            return 0
        except Exception as e:
            print(f"Redis delete_pattern error: {e}")
            return 0

    def exists(self, key: str) -> bool:
        """キャッシュ存在確認"""
        try:
            return self.client.exists(key) > 0
        except Exception as e:
            print(f"Redis exists error: {e}")
            return False

    def ttl(self, key: str) -> int:
        """残りTTLを取得"""
        try:
            return self.client.ttl(key)
        except Exception as e:
            print(f"Redis ttl error: {e}")
            return -1


# シングルトンインスタンス
redis_client = RedisClient()


def get_redis() -> RedisClient:
    """RedisClientを取得（FastAPI Dependency用）"""
    return redis_client
