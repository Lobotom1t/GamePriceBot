import sqlite3
import logging
import os
import time

logger = logging.getLogger(__name__)
DB_PATH = os.path.join(os.path.dirname(__file__), "cache.db")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            first_seen REAL NOT NULL,
            last_seen REAL NOT NULL,
            search_count INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS searches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            query TEXT NOT NULL,
            searched_at REAL NOT NULL
        )
    """)
    conn.commit()
    return conn


def track_user(user_id: int, username: str, first_name: str):
    """Регистрируем пользователя или обновляем время визита."""
    try:
        now = time.time()
        with _get_conn() as conn:
            conn.execute("""
                INSERT INTO users (user_id, username, first_name, first_seen, last_seen, search_count)
                VALUES (?, ?, ?, ?, ?, 0)
                ON CONFLICT(user_id) DO UPDATE SET
                    username=excluded.username,
                    first_name=excluded.first_name,
                    last_seen=excluded.last_seen
            """, (user_id, username or "", first_name or ""))
            conn.commit()
    except Exception as e:
        logger.error(f"Stats track_user error: {e}")


def track_search(user_id: int, query: str):
    """Логируем поисковый запрос."""
    try:
        with _get_conn() as conn:
            conn.execute(
                "INSERT INTO searches (user_id, query, searched_at) VALUES (?, ?, ?)",
                (user_id, query.lower().strip(), time.time())
            )
            conn.execute(
                "UPDATE users SET search_count = search_count + 1, last_seen = ? WHERE user_id = ?",
                (time.time(), user_id)
            )
            conn.commit()
    except Exception as e:
        logger.error(f"Stats track_search error: {e}")


def get_stats() -> dict:
    """Получаем общую статистику для админа."""
    try:
        with _get_conn() as conn:
            total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]

            # Новые за последние 7 дней
            week_ago = time.time() - 7 * 86400
            new_users_week = conn.execute(
                "SELECT COUNT(*) FROM users WHERE first_seen > ?", (week_ago,)
            ).fetchone()[0]

            # Активные за последние 24 часа
            day_ago = time.time() - 86400
            active_today = conn.execute(
                "SELECT COUNT(DISTINCT user_id) FROM searches WHERE searched_at > ?", (day_ago,)
            ).fetchone()[0]

            # Всего поисков
            total_searches = conn.execute("SELECT COUNT(*) FROM searches").fetchone()[0]

            # Поиски за сегодня
            searches_today = conn.execute(
                "SELECT COUNT(*) FROM searches WHERE searched_at > ?", (day_ago,)
            ).fetchone()[0]

            # Подписки на цены
            total_watchlist = conn.execute("SELECT COUNT(*) FROM watchlist").fetchone()[0]

            # Топ-10 запросов
            top_queries = conn.execute("""
                SELECT query, COUNT(*) as cnt
                FROM searches
                GROUP BY query
                ORDER BY cnt DESC
                LIMIT 10
            """).fetchall()

            return {
                "total_users": total_users,
                "new_users_week": new_users_week,
                "active_today": active_today,
                "total_searches": total_searches,
                "searches_today": searches_today,
                "total_watchlist": total_watchlist,
                "top_queries": top_queries,
            }
    except Exception as e:
        logger.error(f"Stats get_stats error: {e}")
        return {}
