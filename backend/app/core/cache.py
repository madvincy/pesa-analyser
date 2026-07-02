import json
import logging
import os
from typing import Any, Optional

import redis

logger = logging.getLogger(__name__)


class RedisCache:
    def __init__(self) -> None:
        self.client: Optional[redis.Redis] = None
        self.host = os.getenv("REDIS_HOST", "localhost")
        self.port = int(os.getenv("REDIS_PORT", 6379))
        self.db = int(os.getenv("REDIS_DB", 0))
        self.password = os.getenv("REDIS_PASSWORD", None)

    def connect(self) -> bool:
        """Connect to Redis"""
        try:
            self.client = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            self.client.ping()
            return True
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            self.client = None
            return False

    def disconnect(self) -> None:
        """Disconnect from Redis"""
        if self.client:
            self.client.close()
            self.client = None

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if not self.client:
            return None
        try:
            value = self.client.get(key)
            return json.loads(value) if value else None
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            return None

    def set(self, key: str, value: Any, expire: int = 3600) -> bool:
        """Set value in cache with expiration"""
        if not self.client:
            logger.warning("Redis not connected — skipping cache set")
            return False
        try:
            self.client.setex(key, expire, json.dumps(value, default=str))
            return True
        except Exception as e:
            logger.error(f"Redis set error: {e}")
            return False

    def delete(self, key: str) -> bool:
        """Delete value from cache"""
        if not self.client:
            return False
        try:
            self.client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
            return False

    def exists(self, key: str) -> bool:
        """Check if key exists"""
        if not self.client:
            return False
        try:
            return bool(self.client.exists(key))
        except Exception as e:
            logger.error(f"Redis exists error: {e}")
            return False

    def increment(self, key: str, amount: int = 1) -> int:
        """Increment counter"""
        if not self.client:
            return 0
        try:
            return int(self.client.incr(key, amount))
        except Exception as e:
            logger.error(f"Redis increment error: {e}")
            return 0


# Singleton instance
redis_client = RedisCache()