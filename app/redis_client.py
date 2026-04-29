"""Redis - БД для временного Хранения Сообщений (24 часа)"""

import json
import logging
from typing import Optional

import redis.asyncio as aioredis

logger = logging.getLogger("keeper.redis")


class RedisClient:
    def __init__(
        self,
        host: str = "keeper_redis",
        port: int = 6379,
        password: Optional[str] = None,
        db: int = 0,
        ttl: int = 86400,
    ):
        self._default_ttl = ttl
        self._pool = aioredis.ConnectionPool(
            host=host,
            port=port,
            password=password,
            db=db,
            decode_responses=True,
            max_connections=10,
        )
        self._redis = aioredis.Redis(connection_pool=self._pool)

    async def ping(self):
        await self._redis.ping()

    @staticmethod
    def _key(business_connection_id: str, chat_id: int, msg_id: int) -> str:
        return f"keeper:{business_connection_id}:{chat_id}:{msg_id}"

    async def save_message(
        self,
        business_connection_id: str,
        chat_id: int,
        msg_id: int,
        sender_id: int,
        sender_name: str,
        text: str,
    ) -> None:
        key = self._key(business_connection_id, chat_id, msg_id)
        payload = json.dumps(
            {
                "chat_id": chat_id,
                "msg_id": msg_id,
                "sender_id": sender_id,
                "sender_name": sender_name,
                "text": text,
            },
            ensure_ascii=False,
        )
        await self._redis.set(key, payload, ex=self._default_ttl)
        logger.debug("Saved msg %d chat %d", msg_id, chat_id)

    async def get_message(
        self,
        business_connection_id: str,
        chat_id: int,
        msg_id: int,
    ) -> Optional[dict]:
        key = self._key(business_connection_id, chat_id, msg_id)
        raw = await self._redis.get(key)
        return json.loads(raw) if raw else None

    async def delete_message(
        self,
        business_connection_id: str,
        chat_id: int,
        msg_id: int,
    ) -> None:
        key = self._key(business_connection_id, chat_id, msg_id)
        await self._redis.delete(key)

    async def close(self):
        await self._pool.aclose()