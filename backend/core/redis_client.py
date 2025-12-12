import redis.asyncio as aioredis
from redis.asyncio.connection import ConnectionPool
from typing import Optional, Any
import json
from backend.config import settings

class RedisClient:
    def __init__(self):
        self.pool: Optional[ConnectionPool] = None
        self.client: Optional[aioredis.Redis] = None
    
    async def connect(self):
        """Redis接続初期化"""
        self.pool = ConnectionPool.from_url(
            settings.REDIS_URL,
            max_connections=settings.REDIS_MAX_CONNECTIONS,
            decode_responses=True
        )
        self.client = aioredis.Redis(connection_pool=self.pool)
        
        # 接続テスト
        await self.client.ping()
        print("Redis connected successfully!")
    
    async def close(self):
        """接続クローズ"""
        if self.client:
            await self.client.close()
        if self.pool:
            await self.pool.disconnect()
    
    async def get(self, key: str) -> Optional[Any]:
        """キャッシュ取得"""
        value = await self.client.get(key)
        if value:
            return json.loads(value)
        return None
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        expire: int = settings.CACHE_TTL_MEDIUM
    ):
        """キャッシュ保存"""
        await self.client.set(
            key, 
            json.dumps(value, default=str),
            ex=expire
        )
    
    async def delete(self, key: str):
        """キャッシュ削除"""
        await self.client.delete(key)
    
    async def delete_pattern(self, pattern: str):
        """パターンマッチでキャッシュ一括削除"""
        keys = []
        async for key in self.client.scan_iter(match=pattern):
            keys.append(key)
        
        if keys:
            await self.client.delete(*keys)
    
    async def exists(self, key: str) -> bool:
        """キャッシュ存在確認"""
        return await self.client.exists(key) > 0

# シングルトンインスタンス
redis_client = RedisClient()

# Dependency
async def get_redis() -> RedisClient:
    return redis_client
