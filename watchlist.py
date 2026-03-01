import sqlite3
import logging
import os
import time

logger = logging.getLogger(__name__)
DB_PATH = os.path.join(os.path.dirname(__file__), "cache.db")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            query TEXT NOT NULL,
            game_name TEXT NOT NULL,
            best_price INTEGER NOT NULL,
            added_at REAL NOT NULL,
            UNIQUE(user_id, query)
        )
    """)
    conn.commit()
    return conn


def add(user_id: int, query: str, game_name: str, best_price: int) -> bool:
    """Добавить игру в список слежения. Возвращает True если добавлено, False если уже есть."""
    try:
        with _get_conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO watchlist (user_id, query, game_name, best_price, added_at) VALUES (?,?,?,?,?)",
                (user_id, query.lower().strip(), game_name, best_price, time.time())
            )
            conn.commit()
            return conn.total_changes > 0
    except Exception as e:
        logger.error(f"Watchlist add error: {e}")
        return False


def remove(user_id: int, query: str) -> bool:
    """Удалить игру из списка слежения."""
    try:
        with _get_conn() as conn:
            conn.execute(
                "DELETE FROM watchlist WHERE user_id=? AND query=?",
                (user_id, query.lower().strip())
            )
            conn.commit()
            return conn.total_changes > 0
    except Exception as e:
        logger.error(f"Watchlist remove error: {e}")
        return False


def get_user_list(user_id: int) -> list[dict]:
    """Получить все подписки пользователя."""
    try:
        with _get_conn() as conn:
            rows = conn.execute(
                "SELECT query, game_name, best_price FROM watchlist WHERE user_id=? ORDER BY added_at DESC",
                (user_id,)
            ).fetchall()
            return [{"query": r[0], "game_name": r[1], "best_price": r[2]} for r in rows]
    except Exception as e:
        logger.error(f"Watchlist get error: {e}")
        return []


def get_all() -> list[dict]:
    """Получить все подписки (для фоновой проверки)."""
    try:
        with _get_conn() as conn:
            rows = conn.execute(
                "SELECT id, user_id, query, game_name, best_price FROM watchlist"
            ).fetchall()
            return [{"id": r[0], "user_id": r[1], "query": r[2], "game_name": r[3], "best_price": r[4]} for r in rows]
    except Exception as e:
        logger.error(f"Watchlist get_all error: {e}")
        return []


def update_price(user_id: int, query: str, new_price: int):
    """Обновить сохранённую цену после уведомления."""
    try:
        with _get_conn() as conn:
            conn.execute(
                "UPDATE watchlist SET best_price=? WHERE user_id=? AND query=?",
                (new_price, user_id, query.lower().strip())
            )
            conn.commit()
    except Exception as e:
        logger.error(f"Watchlist update error: {e}")


def is_watching(user_id: int, query: str) -> bool:
    """Проверить следит ли пользователь за игрой."""
    try:
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM watchlist WHERE user_id=? AND query=?",
                (user_id, query.lower().strip())
            ).fetchone()
            return row is not None
    except Exception:
        return False
