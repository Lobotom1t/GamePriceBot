import sqlite3
import json
import time
import logging
import os

logger = logging.getLogger(__name__)

CACHE_TTL = 86400  # 24 часа
DB_PATH = os.path.join(os.path.dirname(__file__), "cache.db")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cache (
            key TEXT PRIMARY KEY,
            data TEXT NOT NULL,
            saved_at REAL NOT NULL
        )
    """)
    conn.commit()
    return conn


def get(key: str) -> dict | None:
    """Получить значение из кэша. Возвращает None если нет или устарело."""
    key = key.lower().strip()
    try:
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT data, saved_at FROM cache WHERE key = ?", (key,)
            ).fetchone()

            if not row:
                return None

            data_json, saved_at = row
            age = time.time() - saved_at

            if age > CACHE_TTL:
                conn.execute("DELETE FROM cache WHERE key = ?", (key,))
                conn.commit()
                logger.info(f"Cache expired: {key}")
                return None

            logger.info(f"Cache hit: {key} (age: {int(age)}s)")
            return json.loads(data_json)

    except Exception as e:
        logger.error(f"Cache get error: {e}")
        return None


def set(key: str, data: dict) -> None:
    """Сохранить значение в кэш."""
    key = key.lower().strip()
    try:
        with _get_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache (key, data, saved_at) VALUES (?, ?, ?)",
                (key, json.dumps(data, ensure_ascii=False), time.time())
            )
            conn.commit()
            logger.info(f"Cached: {key}")
    except Exception as e:
        logger.error(f"Cache set error: {e}")


def size() -> int:
    """Количество записей в кэше."""
    try:
        with _get_conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
    except Exception:
        return 0


def clear_expired() -> int:
    """Удалить устаревшие записи. Возвращает количество удалённых."""
    try:
        with _get_conn() as conn:
            cursor = conn.execute(
                "DELETE FROM cache WHERE ? - saved_at > ?",
                (time.time(), CACHE_TTL)
            )
            conn.commit()
            deleted = cursor.rowcount
            if deleted:
                logger.info(f"Cleared {deleted} expired cache entries")
            return deleted
    except Exception as e:
        logger.error(f"Cache clear error: {e}")
        return 0
