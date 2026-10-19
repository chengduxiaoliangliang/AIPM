import json
import logging
from typing import Any, Optional
import redis
from app.config import settings

logger = logging.getLogger(__name__)

class RedisClient:
    def __init__(self):
        self._pool = None
        self._client: Optional[redis.Redis] = None

    def get_client(self) -> redis.Redis:
        if self._client is None:
            try:
                self._pool = redis.ConnectionPool(
                    host=settings.REDIS_HOST,
                    port=settings.REDIS_PORT,
                    password=settings.REDIS_PASSWORD or None,
                    db=settings.REDIS_DB,
                    decode_responses=True,
                    socket_connect_timeout=3,
                    socket_timeout=3
                )
                self._client = redis.Redis(connection_pool=self._pool)
                self._client.ping()
                logger.info("Connected to Redis successfully.")
            except Exception as e:
                logger.warning(f"Failed to connect to Redis: {e}")
                self._client = None
        return self._client

    def set(self, key: str, value: Any, expire_seconds: Optional[int] = None, ex: Optional[int] = None) -> bool:
        client = self.get_client()
        if not client:
            return False
        try:
            exp = expire_seconds or ex
            val_str = json.dumps(value, ensure_ascii=False) if not isinstance(value, (str, int, float, bool)) else str(value)
            if exp:
                return bool(client.setex(key, exp, val_str))
            return bool(client.set(key, val_str))
        except Exception as e:
            logger.warning(f"Redis set failed for {key}: {e}")
            return False

    def get(self, key: str) -> Optional[Any]:
        client = self.get_client()
        if not client:
            return None
        try:
            val = client.get(key)
            if val is None:
                return None
            try:
                return json.loads(val)
            except Exception:
                return val
        except Exception as e:
            logger.warning(f"Redis get failed for {key}: {e}")
            return None

    def delete(self, key: str) -> bool:
        client = self.get_client()
        if not client:
            return False
        try:
            return bool(client.delete(key))
        except Exception as e:
            logger.warning(f"Redis delete failed for {key}: {e}")
            return False

    def is_connected(self) -> bool:
        client = self.get_client()
        if not client:
            return False
        try:
            return bool(client.ping())
        except Exception:
            return False

redis_client = RedisClient()
