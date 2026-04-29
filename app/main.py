"""
Keeper — Telegram Business Bot
Отслеживает удалённые и изменённые сообщения в ЛС бизнес-аккаунта!
"""

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import Config
from redis_client import RedisClient
from sqlite_client import SQLiteClient
from handlers import router


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/keeper.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("keeper")


async def main():
    config = Config.from_env()

    # Redis - Хранение сообщений (На 24 часа)
    redis = RedisClient(
        host=config.REDIS_HOST,
        port=config.REDIS_PORT,
        password=config.REDIS_PASSWORD,
        db=config.REDIS_DB,
        ttl=config.MESSAGE_TTL,
    )
    await redis.ping()
    logger.info("✅ Redis подключён")

    # SQLite - Сохранение Юзеров Бота
    db = SQLiteClient()
    db.connect()

    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher()
    dp["redis"] = redis
    dp["db"] = db
    dp["config"] = config
    bot_info = await bot.get_me()
    dp["bot_username"] = bot_info.username
    dp.include_router(router)
    
    logger.info("🚀 Keeper запущен!")
    try:
        await dp.start_polling(bot, allowed_updates=[
            "message",
            "edited_message",
            "deleted_business_messages",
            "business_connection",
            "business_message",
            "edited_business_message",
        ])
    finally:
        db.close()
        await redis.close()


if __name__ == "__main__":
    asyncio.run(main())