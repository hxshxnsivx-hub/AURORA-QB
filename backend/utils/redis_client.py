"""
Redis client utility for message queue and caching.

This module provides a Redis client wrapper with connection pooling,
error handling, and common operations for the agent orchestration system.
"""

import redis.asyncio as redis
from typing import Optional, Any, Dict
import json
import os
from utils.logger import logger


class RedisClient:
    """Async Redis client with connection pooling"""
    
    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.pool: Optional[redis.ConnectionPool] = None
        self.client: Optional[redis.Redis] = None
    
    async def connect(self):
        """Initialize Redis connection pool"""
        try:
            self.pool = redis.ConnectionPool.from_url(
                self.redis_url,
                decode_responses=True,
                max_connections=20
            )
            self.client = redis.Redis(connection_pool=self.pool)
            
            # Test connection
            await self.client.ping()
            logger.info("Redis connection established", extra={
                "redis_url": self.redis_url.split("@")[-1]  # Hide credentials
            })
        except Exception as e:
            logger.error("Failed to connect to Redis", extra={
                "error": str(e),
                "redis_url": self.redis_url.split("@")[-1]
            })
            raise
    
    async def disconnect(self):
        """Close Redis connection"""
        if self.client:
            await self.client.close()
        if self.pool:
            await self.pool.disconnect()
        logger.info("Redis connection closed")
    
    async def get(self, key: str) -> Optional[str]:
        """Get value by key"""
        try:
            return await self.client.get(key)
        except Exception as e:
            logger.error("Redis GET failed", extra={
                "key": key,
                "error": str(e)
            })
            return None
    
    async def set(
        self, 
        key: str, 
        value: str, 
        ex: Optional[int] = None
    ) -> bool:
        """
        Set key-value pair with optional expiration
        
        Args:
            key: Redis key
            value: Value to store
            ex: Expiration time in seconds
        
        Returns:
            True if successful, False otherwise
        """
        try:
            await self.client.set(key, value, ex=ex)
            return True
        except Exception as e:
            logger.error("Redis SET failed", extra={
                "key": key,
                "error": str(e)
            })
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key"""
        try:
            await self.client.delete(key)
            return True
        except Exception as e:
            logger.error("Redis DELETE failed", extra={
                "key": key,
                "error": str(e)
            })
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        try:
            return await self.client.exists(key) > 0
        except Exception as e:
            logger.error("Redis EXISTS failed", extra={
                "key": key,
                "error": str(e)
            })
            return False
    
    # Queue operations
    
    async def lpush(self, key: str, *values: str) -> int:
        """Push values to the left of list"""
        try:
            return await self.client.lpush(key, *values)
        except Exception as e:
            logger.error("Redis LPUSH failed", extra={
                "key": key,
                "error": str(e)
            })
            return 0
    
    async def rpush(self, key: str, *values: str) -> int:
        """Push values to the right of list"""
        try:
            return await self.client.rpush(key, *values)
        except Exception as e:
            logger.error("Redis RPUSH failed", extra={
                "key": key,
                "error": str(e)
            })
            return 0
    
    async def lpop(self, key: str) -> Optional[str]:
        """Pop value from the left of list"""
        try:
            return await self.client.lpop(key)
        except Exception as e:
            logger.error("Redis LPOP failed", extra={
                "key": key,
                "error": str(e)
            })
            return None
    
    async def rpop(self, key: str) -> Optional[str]:
        """Pop value from the right of list"""
        try:
            return await self.client.rpop(key)
        except Exception as e:
            logger.error("Redis RPOP failed", extra={
                "key": key,
                "error": str(e)
            })
            return None
    
    async def llen(self, key: str) -> int:
        """Get length of list"""
        try:
            return await self.client.llen(key)
        except Exception as e:
            logger.error("Redis LLEN failed", extra={
                "key": key,
                "error": str(e)
            })
            return 0
    
    async def lrange(self, key: str, start: int, end: int) -> list:
        """Get range of values from list"""
        try:
            return await self.client.lrange(key, start, end)
        except Exception as e:
            logger.error("Redis LRANGE failed", extra={
                "key": key,
                "error": str(e)
            })
            return []
    
    # Pub/Sub operations
    
    async def publish(self, channel: str, message: str) -> int:
        """Publish message to channel"""
        try:
            return await self.client.publish(channel, message)
        except Exception as e:
            logger.error("Redis PUBLISH failed", extra={
                "channel": channel,
                "error": str(e)
            })
            return 0
    
    async def subscribe(self, *channels: str):
        """Subscribe to channels"""
        try:
            pubsub = self.client.pubsub()
            await pubsub.subscribe(*channels)
            return pubsub
        except Exception as e:
            logger.error("Redis SUBSCRIBE failed", extra={
                "channels": channels,
                "error": str(e)
            })
            return None
    
    # Hash operations
    
    async def hset(self, name: str, key: str, value: str) -> int:
        """Set hash field"""
        try:
            return await self.client.hset(name, key, value)
        except Exception as e:
            logger.error("Redis HSET failed", extra={
                "name": name,
                "key": key,
                "error": str(e)
            })
            return 0
    
    async def hget(self, name: str, key: str) -> Optional[str]:
        """Get hash field"""
        try:
            return await self.client.hget(name, key)
        except Exception as e:
            logger.error("Redis HGET failed", extra={
                "name": name,
                "key": key,
                "error": str(e)
            })
            return None
    
    async def hgetall(self, name: str) -> Dict[str, str]:
        """Get all hash fields"""
        try:
            return await self.client.hgetall(name)
        except Exception as e:
            logger.error("Redis HGETALL failed", extra={
                "name": name,
                "error": str(e)
            })
            return {}
    
    async def hdel(self, name: str, *keys: str) -> int:
        """Delete hash fields"""
        try:
            return await self.client.hdel(name, *keys)
        except Exception as e:
            logger.error("Redis HDEL failed", extra={
                "name": name,
                "keys": keys,
                "error": str(e)
            })
            return 0
    
    # JSON helper methods
    
    async def set_json(
        self, 
        key: str, 
        value: Any, 
        ex: Optional[int] = None
    ) -> bool:
        """Set JSON-serialized value"""
        try:
            json_str = json.dumps(value)
            return await self.set(key, json_str, ex=ex)
        except Exception as e:
            logger.error("Redis SET_JSON failed", extra={
                "key": key,
                "error": str(e)
            })
            return False
    
    async def get_json(self, key: str) -> Optional[Any]:
        """Get JSON-deserialized value"""
        try:
            value = await self.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error("Redis GET_JSON failed", extra={
                "key": key,
                "error": str(e)
            })
            return None


# Global Redis client instance
redis_client = RedisClient()
