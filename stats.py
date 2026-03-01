import time
import logging
from db import get_pool

logger = logging.getLogger(__name__)


async def track_user(user_id: int, username: str, first_name: str):
    try:
        now = time.time()
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO users (user_id, username, first_name, first_seen, last_seen, search_count)
                   VALUES ($1, $2, $3, $4, $4, 0)
                   ON CONFLICT (user_id) DO UPDATE SET
                       username=excluded.username,
                       first_name=excluded.first_name,
                       last_seen=excluded.last_seen""",
                user_id, username or "", first_name or "", now
            )
    except Exception as e:
        logger.error(f"Stats track_user error: {e}")


async def track_search(user_id: int, query: str):
    try:
        now = time.time()
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO searches (user_id, query, searched_at) VALUES ($1, $2, $3)",
                user_id, query.lower().strip(), now
            )
            await conn.execute(
                "UPDATE users SET search_count = search_count + 1, last_seen = $1 WHERE user_id = $2",
                now, user_id
            )
    except Exception as e:
        logger.error(f"Stats track_search error: {e}")


async def get_stats() -> dict:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            total_users = await conn.fetchval("SELECT COUNT(*) FROM users")
            week_ago = time.time() - 7 * 86400
            new_users_week = await conn.fetchval(
                "SELECT COUNT(*) FROM users WHERE first_seen > $1", week_ago
            )
            day_ago = time.time() - 86400
            active_today = await conn.fetchval(
                "SELECT COUNT(DISTINCT user_id) FROM searches WHERE searched_at > $1", day_ago
            )
            total_searches = await conn.fetchval("SELECT COUNT(*) FROM searches")
            searches_today = await conn.fetchval(
                "SELECT COUNT(*) FROM searches WHERE searched_at > $1", day_ago
            )
            total_watchlist = await conn.fetchval("SELECT COUNT(*) FROM watchlist")
            top_queries = await conn.fetch(
                """SELECT query, COUNT(*) as cnt FROM searches
                   GROUP BY query ORDER BY cnt DESC LIMIT 10"""
            )
            return {
                "total_users": total_users,
                "new_users_week": new_users_week,
                "active_today": active_today,
                "total_searches": total_searches,
                "searches_today": searches_today,
                "total_watchlist": total_watchlist,
                "top_queries": [(r["query"], r["cnt"]) for r in top_queries],
            }
    except Exception as e:
        logger.error(f"Stats get_stats error: {e}")
        return {}
