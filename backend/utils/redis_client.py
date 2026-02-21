"""
Redis client for message queue and caching.

This module provides a Redis connection manager for:
- Message queue operations
- Caching
- Pub/Sub messaging
"""

import redis.asyncio as redis
from typing import Optional, Any
import json
import os
from utils.logger import logger


class RedisClient:
    """Async Redis client wrapper"""
    
    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self._client: Optional[redis.Redis] = None
        self._pubsub: Optional[redis.client.PubSub] = None
    
    async def connect(self):
        """Establish Redis connection"""
        if self._client is None:
            self._client = await redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            logger.info("Redis connection established", extra={"redis_url": self.redis_url})
    
    async def disconnect(self):
        """Close Redis connection"""
        if self._client:
            await self._client.close()
            self._client = None
            logger.info("Redis connection closed")
    
    async def ping(self) -> bool:
        """Check Redis connection"""
        try:
            if self._client:
                return await self._client.ping()
            return False
        except Exception as e:
            logger.error("Redis ping failed", extra={"error": str(e)})
            return False
    
    # Queue Operations
    
    async def enqueue(self, queue_name: str, data: dict) -> int:
        """
        Add item to queue (FIFO using list)
        
        Args:
            queue_name: Name of the queue
            data: Data to enqueue (will be JSON serialized)
        
        Returns:
            Length of queue after enqueue
        """
        if not self._client:
            await self.connect()
        
        serialized = json.dumps(data)
        length = await self._client.rpush(queue_name, serialized)
        
        logger.debug(
            "Item enqueued",
            extra={
                "queue": queue_name,
                "queue_length": length,
                "data_keys": list(data.keys())
            }
        )
        
        return length
    
    async def dequeue(self, queue_name: str, timeout: int = 0) -> Optional[dict]:
        """
        Remove and return item from queue (blocking)
        
        Args:
            queue_name: Name of the queue
            timeout: Timeout in seconds (0 = block indefinitely)
        
        Returns:
            Dequeued data or None if timeout
        """
        if not self._client:
            await self.connect()
        
        result = await self._client.blpop(queue_name, timeout=timeout)
        
        if result:
            _, serialized = result
            data = json.loads(serialized)
            
            logger.debug(
                "Item dequeued",
                extra={
                    "queue": queue_name,
                    "data_keys": list(data.keys())
                }
            )
            
            return data
        
        return None
    
    async def queue_length(self, queue_name: str) -> int:
        """Get current queue length"""
        if not self._client:
            await self.connect()
        
        return await self._client.llen(queue_name)
    
    async def peek_queue(self, queue_name: str, start: int = 0, end: int = -1) -> list:
        """
        View queue items without removing them
        
        Args:
            queue_name: Name of the queue
            start: Start index
            end: End index (-1 for all)
        
        Returns:
            List of items in queue
        """
        if not self._client:
            await self.connect()
        
        items = await self._client.lrange(queue_name, start, end)
        return [json.loads(item) for item in items]
    
    # Pub/Sub Operations
    
    async def publish(self, channel: str, message: dict) -> int:
        """
        Publish message to channel
        
        Args:
            channel: Channel name
            message: Message to publish
        
        Returns:
            Number of subscribers that received the message
        """
        if not self._client:
            await self.connect()
        
        serialized = json.dumps(message)
        count = await self._client.publish(channel, serialized)
        
        logger.debug(
            "Message published",
            extra={
                "channel": channel,
                "subscribers": count,
                "message_keys": list(message.keys())
            }
        )
        
        return count
    
    async def subscribe(self, *channels: str):
        """
        Subscribe to channels
        
        Args:
            channels: Channel names to subscribe to
        """
        if not self._client:
            await self.connect()
        
        if not self._pubsub:
            self._pubsub = self._client.pubsub()
        
        await self._pubsub.subscribe(*channels)
        
        logger.info(
            "Subscribed to channels",
            extra={"channels": list(channels)}
        )
    
    async def unsubscribe(self, *channels: str):
        """Unsubscribe from channels"""
        if self._pubsub:
            await self._pubsub.unsubscribe(*channels)
            logger.info(
                "Unsubscribed from channels",
                extra={"channels": list(channels)}
            )
    
    async def get_message(self, timeout: float = 1.0) -> Optional[dict]:
        """
        Get message from subscribed channels
        
        Args:
            timeout: Timeout in seconds
        
        Returns:
            Message dict or None
        """
        if not self._pubsub:
            return None
        
        message = await self._pubsub.get_message(timeout=timeout)
        
        if message and message["type"] == "message":
            data = json.loads(message["data"])
            
            logger.debug(
                "Message received",
                extra={
                    "channel": message["channel"],
                    "data_keys": list(data.keys())
                }
            )
            
            return {
                "channel": message["channel"],
                "data": data
            }
        
        return None
    
    # Caching Operations
    
    async def set(
        self,
        key: str,
        value: Any,
        expire: Optional[int] = None
    ) -> bool:
        """
        Set key-value pair with optional expiration
        
        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
            expire: Expiration in seconds
        
        Returns:
            True if successful
        """
        if not self._client:
            await self.connect()
        
        serialized = json.dumps(value)
        
        if expire:
            return await self._client.setex(key, expire, serialized)
        else:
            return await self._client.set(key, serialized)
    
    async def get(self, key: str) -> Optional[Any]:
        """
        Get value by key
        
        Args:
            key: Cache key
        
        Returns:
            Cached value or None
        """
        if not self._client:
            await self.connect()
        
        value = await self._client.get(key)
        
        if value:
            return json.loads(value)
        
        return None
    
    async def delete(self, *keys: str) -> int:
        """
        Delete keys
        
        Args:
            keys: Keys to delete
        
        Returns:
            Number of keys deleted
        """
        if not self._client:
            await self.connect()
        
        return await self._client.delete(*keys)
    
    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        if not self._client:
            await self.connect()
        
        return await self._client.exists(key) > 0
    
    async def expire(self, key: str, seconds: int) -> bool:
        """Set expiration on key"""
        if not self._client:
            await self.connect()
        
        return await self._client.expire(key, seconds)
    
    async def ttl(self, key: str) -> int:
        """Get time to live for key"""
        if not self._client:
            await self.connect()
        
        return await self._client.ttl(key)
    
    # Hash Operations (for structured data)
    
    async def hset(self, name: str, key: str, value: Any) -> int:
        """Set hash field"""
        if not self._client:
            await self.connect()
        
        serialized = json.dumps(value)
        return await self._client.hset(name, key, serialized)
    
    async def hget(self, name: str, key: str) -> Optional[Any]:
        """Get hash field"""
        if not self._client:
            await self.connect()
        
        value = await self._client.hget(name, key)
        
        if value:
            return json.loads(value)
        
        return None
    
    async def hgetall(self, name: str) -> dict:
        """Get all hash fields"""
        if not self._client:
            await self.connect()
        
        data = await self._client.hgetall(name)
        
        return {k: json.loads(v) for k, v in data.items()}
    
    async def hdel(self, name: str, *keys: str) -> int:
        """Delete hash fields"""
        if not self._client:
            await self.connect()
        
        return await self._client.hdel(name, *keys)


# Global Redis client instance
redis_client = RedisClient()
