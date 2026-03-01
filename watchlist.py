import time
import logging
from db import get_pool

logger = logging.getLogger(__name__)


async def add(user_id: int, query: str, game_name: str, best_price: int) -> bool:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                """INSERT INTO watchlist (user_id, query, game_name, best_price, added_at)
                   VALUES ($1, $2, $3, $4, $5) ON CONFLICT (user_id, query) DO NOTHING""",
                user_id, query.lower().strip(), game_name, best_price, time.time()
            )
            return result.split()[-1] == "1"
    except Exception as e:
        logger.error(f"Watchlist add error: {e}")
        return False


async def remove(user_id: int, query: str) -> bool:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM watchlist WHERE user_id=$1 AND query=$2",
                user_id, query.lower().strip()
            )
            return result.split()[-1] == "1"
    except Exception as e:
        logger.error(f"Watchlist remove error: {e}")
        return False


async def get_user_list(user_id: int) -> list[dict]:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT query, game_name, best_price FROM watchlist WHERE user_id=$1 ORDER BY added_at DESC",
                user_id
            )
            return [{"query": r["query"], "game_name": r["game_name"], "best_price": r["best_price"]} for r in rows]
    except Exception as e:
        logger.error(f"Watchlist get error: {e}")
        return []


async def get_all() -> list[dict]:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, user_id, query, game_name, best_price FROM watchlist"
            )
            return [{"id": r["id"], "user_id": r["user_id"], "query": r["query"],
                     "game_name": r["game_name"], "best_price": r["best_price"]} for r in rows]
    except Exception as e:
        logger.error(f"Watchlist get_all error: {e}")
        return []


async def update_price(user_id: int, query: str, new_price: int):
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE watchlist SET best_price=$1 WHERE user_id=$2 AND query=$3",
                new_price, user_id, query.lower().strip()
            )
    except Exception as e:
        logger.error(f"Watchlist update error: {e}")


async def is_watching(user_id: int, query: str) -> bool:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT 1 FROM watchlist WHERE user_id=$1 AND query=$2",
                user_id, query.lower().strip()
            )
            return row is not None
    except Exception:
        return False
