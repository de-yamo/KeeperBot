"""Конфигурация из переменных окружения."""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class Config:
    # Telegram Bot Token (@BotFather)
    BOT_TOKEN: str

    # Redis
    REDIS_HOST: str = "keeper_redis"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[str] = None
    REDIS_DB: int = 0

    # TTL хранения сообщений: 24 часа
    MESSAGE_TTL: int = 86400

    @classmethod
    def from_env(cls) -> "Config":
        token = os.environ.get("BOT_TOKEN")
        if not token:
            raise EnvironmentError("BOT_TOKEN не задан!")

        return cls(
            BOT_TOKEN=token,
            REDIS_HOST=os.environ.get("REDIS_HOST", "keeper_redis"),
            REDIS_PORT=int(os.environ.get("REDIS_PORT", 6379)),
            REDIS_PASSWORD=os.environ.get("REDIS_PASSWORD") or None,
            REDIS_DB=int(os.environ.get("REDIS_DB", 0)),
            MESSAGE_TTL=int(os.environ.get("MESSAGE_TTL", 86400)),
        )