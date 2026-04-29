"""
SQLite - БД для хранения Юзеров (Их Айди)
"""

import asyncio
import logging
import sqlite3
from pathlib import Path
from typing import Optional

logger = logging.getLogger("keeper.sqlite")

DB_PATH = Path("/app/data/owners.db")


class SQLiteClient:
    def __init__(self, db_path: Path = DB_PATH):
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> None:
        """Открываем Соединение с БД"""
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS owners (
                business_connection_id TEXT PRIMARY KEY,
                user_id                INTEGER NOT NULL,
                connected_at           TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """)
        self._conn.commit()
        logger.info("✅ SQLite подключён: %s", self._db_path)

    # ------------------------------------------------------------------ #
    #  CRUD
    # ------------------------------------------------------------------ #

    async def save_owner(self, business_connection_id: str, user_id: int) -> None:
        """Сохранить или обновить Юзера"""
        await asyncio.to_thread(self._save_owner_sync, business_connection_id, user_id)
        logger.info("User saved: conn=%s user_id=%d", business_connection_id, user_id)

    def _save_owner_sync(self, business_connection_id: str, user_id: int) -> None:
        self._conn.execute(
            """
            INSERT INTO owners (business_connection_id, user_id)
            VALUES (?, ?)
            ON CONFLICT(business_connection_id) DO UPDATE SET user_id = excluded.user_id
            """,
            (business_connection_id, user_id),
        )
        self._conn.commit()

    async def get_owner(self, business_connection_id: str) -> Optional[int]:
        """Получить user_id по connection_id"""
        row = await asyncio.to_thread(self._get_owner_sync, business_connection_id)
        return row["user_id"] if row else None

    def _get_owner_sync(self, business_connection_id: str):
        cur = self._conn.execute(
            "SELECT user_id FROM owners WHERE business_connection_id = ?",
            (business_connection_id,),
        )
        return cur.fetchone()

    async def delete_owner(self, business_connection_id: str) -> None:
        """Удалить запись при отключении бота Юзером"""
        await asyncio.to_thread(self._delete_owner_sync, business_connection_id)
        logger.info("User removed: conn=%s", business_connection_id)

    def _delete_owner_sync(self, business_connection_id: str) -> None:
        self._conn.execute(
            "DELETE FROM owners WHERE business_connection_id = ?",
            (business_connection_id,),
        )
        self._conn.commit()

    # ------------------------------------------------------------------ #
    #  Graceful shutdown
    # ------------------------------------------------------------------ #

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            logger.info("SQLite закрыт")