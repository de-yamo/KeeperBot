"""
Обработчики событий Telegram Business Bot
"""

import logging
from datetime import datetime, timezone

from aiogram import Bot, Router
from aiogram.types import (
    BusinessConnection,
    BusinessMessagesDeleted,
    Message,
)

from aiogram.filters import CommandStart

from redis_client import RedisClient
from sqlite_client import SQLiteClient

logger = logging.getLogger("keeper.handlers")
router = Router()

@router.message(CommandStart())
async def on_start(msg: Message):
    await msg.answer(
        "👋 <b>Привет, я Keeper и давай расскажу как со мной Работать!</b>\n\n"
        "<b>Что нужно для работы:</b>\n"
        "<blockquote>⚠️ Только Подписка <b>Telegram Premium</b></blockquote>\n\n"
        "<b>Как подключить:</b>\n"
        "<blockquote>1️⃣ - Откройте <b>Настройки</b> в Telegram\n"
        "2️⃣ - Перейдите в <b>Telegram Business</b>\n"
        "3️⃣ - Выберите <b>Чат-боты</b>\n"
        "4️⃣ - Нажмите <b>Добавить бота</b> и введите <code>@safe_and_keep_bot</code>\n"
        "5️⃣ - Готово! Бот пришлёт подтверждение и вам останется только Начать его Работу!</blockquote>\n\n"
        "<b>Как отключить:</b>\n"
        "<blockquote>⛓️‍💥 Зайдите туда же и удалите бота из Чат-ботов!</blockquote>\n\n"
        "🌐 Хотите иметь полный Доступ? Создайте своего бота и Установите его свои Сервера! Скопировав репозиторий - https://github.com/de-yamo/KeeperBot",
        parse_mode="HTML",
    )


#  Вспомогательные

def _now() -> str:
    return datetime.now(tz=timezone.utc).strftime("%d.%m.%Y %H:%M UTC")


def _sender_name(msg: Message) -> str:
    user = msg.from_user
    if not user:
        return "Аноним"
    parts = []
    if user.first_name:
        parts.append(user.first_name)
    if user.last_name:
        parts.append(user.last_name)
    name = " ".join(parts) or "Аноним"
    if user.username:
        name += f" (@{user.username})"
    return name


def _msg_text(msg: Message) -> str:
    if msg.text:
        return msg.text
    if msg.caption:
        return f"[медиа] {msg.caption}"
    for attr in ("photo", "video", "audio", "voice", "document",
                 "sticker", "animation", "video_note", "contact",
                 "location", "poll"):
        if getattr(msg, attr, None):
            return f"[{attr}]"
    return "[сообщение без текста]"


# Логика Бота и обработка событий Telegram Business API

@router.business_connection()
async def on_business_connection(
    event: BusinessConnection,
    bot: Bot,
    db: SQLiteClient,
):
    user_id = event.user.id
    conn_id = event.id

    if event.is_enabled:
        await db.save_owner(conn_id, user_id)
        logger.info("✅ Connected: user_id=%d conn=%s", user_id, conn_id)

        await bot.send_message(
            user_id,
            "✅ <b>Keeper подключён к вашему бизнес-аккаунту!</b>\n\n"
            "Теперь я буду отслеживать <b>Удаленные</b> и <b>Измененные</b> "
            "сообщения в ваших личных чатах и мгновенно уведомлять вас\n\n"
            "⏱ Для вашей же безопастности я буду присылать сообщения которые были Изменены или Удалены в течении <b>24 часов</b>",
        )
    else:
        await db.delete_owner(conn_id)
        logger.info("❌ Disconnected: user_id=%d conn=%s", user_id, conn_id)

        await bot.send_message(
            user_id,
            "❌ <b>Keeper отключён от вашего бизнес-аккаунта!</b>\n"
            "Отслеживание остановлено! Все данные о ваших сообщениях удалятся через 24 часа!",
        )

@router.business_message()
async def on_business_message(
    msg: Message,
    redis: RedisClient,
):
    if not msg.business_connection_id:
        return

    await redis.save_message(
        business_connection_id=msg.business_connection_id,
        chat_id=msg.chat.id,
        msg_id=msg.message_id,
        sender_id=msg.from_user.id if msg.from_user else 0,
        sender_name=_sender_name(msg),
        text=_msg_text(msg),
    )

@router.edited_business_message()
async def on_edited_business_message(
    msg: Message,
    bot: Bot,
    redis: RedisClient,
    db: SQLiteClient,
):
    if not msg.business_connection_id:
        return

    owner_id = await db.get_owner(msg.business_connection_id)
    if not owner_id:
        logger.warning("EDITED: no owner for conn=%s", msg.business_connection_id)
        return

    chat_id = msg.chat.id
    new_text = _msg_text(msg)
    sender_name = _sender_name(msg)

    old_data = await redis.get_message(msg.business_connection_id, chat_id, msg.message_id)
    old_text = old_data["text"] if old_data else "<i>Без Информации! (старше 24ч)</i>"

    # Обновляем кэш
    await redis.save_message(
        business_connection_id=msg.business_connection_id,
        chat_id=chat_id,
        msg_id=msg.message_id,
        sender_id=msg.from_user.id if msg.from_user else 0,
        sender_name=sender_name,
        text=new_text,
    )

    await bot.send_message(
        owner_id,
        f"✏️ <b>Сообщение изменено</b>\n"
        f"<blockquote>👤 от {sender_name}\n"
        f"🕐 Время: {_now()}\n\n"
        f"<b>Было:</b>\n{old_text}\n\n"
        f"<b>Стало:</b>\n{new_text}</blockquote>",
    )
    logger.info("EDITED: conn=%s chat=%d msg=%d owner=%d", msg.business_connection_id, chat_id, msg.message_id, owner_id)

@router.deleted_business_messages()
async def on_deleted_business_messages(
    event: BusinessMessagesDeleted,
    bot: Bot,
    redis: RedisClient,
    db: SQLiteClient,
):
    conn_id = event.business_connection_id
    chat_id = event.chat.id

    owner_id = await db.get_owner(conn_id)
    if not owner_id:
        logger.warning("DELETED: no owner for conn=%s", conn_id)
        return

    for msg_id in event.message_ids:
        old_data = await redis.get_message(conn_id, chat_id, msg_id)

        if old_data is None:
            await bot.send_message(
                owner_id,
                f"🗑 <b>Сообщение удалено</b>\n"
                f"<blockquote>💬 Чат: <code>{chat_id}</code>\n"
                f"🕐 Время: {_now()}\n\n"
                f"<i>Без Информации! (старше 24ч)</i></blockquote>",
            )
            continue

        sender_name = old_data.get("sender_name", "Аноним")
        old_text = old_data.get("text", "")

        await bot.send_message(
            owner_id,
            f"🗑 <b>Сообщение удалено</b>\n"
            f"<blockquote>👤 от {sender_name}\n"
            f"🕐 Время: {_now()}\n\n"
            f"<b>Текст:</b>\n{old_text}</blockquote>",
        )

        await redis.delete_message(conn_id, chat_id, msg_id)
        logger.info("DELETED: conn=%s chat=%d msg=%d owner=%d", conn_id, chat_id, msg_id, owner_id)