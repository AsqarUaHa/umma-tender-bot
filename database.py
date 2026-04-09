"""MySQL database layer using aiomysql."""

import logging
import os
from typing import List, Optional, Tuple
from urllib.parse import urlparse

import aiomysql

logger = logging.getLogger(__name__)


def _resolve_mysql_config() -> dict:
    """Resolve MySQL connection config from env, supporting Railway-style vars."""
    url = os.getenv("MYSQL_URL") or os.getenv("MYSQL_PUBLIC_URL") or os.getenv("DATABASE_URL")
    if url:
        parsed = urlparse(url)
        return {
            "host": parsed.hostname or "localhost",
            "port": parsed.port or 3306,
            "user": parsed.username or "root",
            "password": parsed.password or "",
            "db": (parsed.path or "/railway").lstrip("/") or "railway",
        }
    return {
        "host": os.getenv("MYSQLHOST", os.getenv("DB_HOST", "localhost")),
        "port": int(os.getenv("MYSQLPORT", os.getenv("DB_PORT", "3306"))),
        "user": os.getenv("MYSQLUSER", os.getenv("DB_USER", "root")),
        "password": os.getenv("MYSQLPASSWORD", os.getenv("DB_PASSWORD", "")),
        "db": os.getenv("MYSQLDATABASE", os.getenv("DB_NAME", "umma_bot")),
    }


class Database:
    def __init__(self) -> None:
        self.pool: Optional[aiomysql.Pool] = None
        self.config = _resolve_mysql_config()

    async def init(self) -> None:
        self.pool = await aiomysql.create_pool(
            host=self.config["host"],
            port=self.config["port"],
            user=self.config["user"],
            password=self.config["password"],
            db=self.config["db"],
            autocommit=True,
            minsize=1,
            maxsize=5,
            charset="utf8mb4",
        )
        await self._create_tables()

    async def close(self) -> None:
        if self.pool is not None:
            self.pool.close()
            await self.pool.wait_closed()

    async def _create_tables(self) -> None:
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT PRIMARY KEY,
                        username VARCHAR(255),
                        first_name VARCHAR(255),
                        last_name VARCHAR(255),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                    ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
                    """
                )
                await cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS messages (
                        id BIGINT AUTO_INCREMENT PRIMARY KEY,
                        user_id BIGINT NOT NULL,
                        role VARCHAR(16) NOT NULL,
                        content MEDIUMTEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        INDEX idx_user_created (user_id, created_at)
                    ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
                    """
                )

    async def upsert_user(
        self,
        user_id: int,
        username: Optional[str],
        first_name: Optional[str],
        last_name: Optional[str],
    ) -> None:
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO users (user_id, username, first_name, last_name)
                    VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        username = VALUES(username),
                        first_name = VALUES(first_name),
                        last_name = VALUES(last_name)
                    """,
                    (user_id, username, first_name, last_name),
                )

    async def add_message(self, user_id: int, role: str, content: str) -> None:
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "INSERT INTO messages (user_id, role, content) VALUES (%s, %s, %s)",
                    (user_id, role, content),
                )

    async def get_history(self, user_id: int, limit: int = 20) -> List[Tuple[str, str]]:
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT role, content FROM (
                        SELECT id, role, content
                        FROM messages
                        WHERE user_id = %s
                        ORDER BY id DESC
                        LIMIT %s
                    ) AS recent
                    ORDER BY id ASC
                    """,
                    (user_id, limit),
                )
                rows = await cur.fetchall()
                return [(row[0], row[1]) for row in rows]

    async def clear_history(self, user_id: int) -> None:
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM messages WHERE user_id = %s", (user_id,))
