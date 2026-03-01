import json
import time
import logging
from db import get_pool

logger = logging.getLogger(__name__)

CACHE_TTL = 86400  # 24 часа


async def get(key: str) -> dict | None:
    key = key.lower().strip()
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT data, saved_at FROM cache WHERE key = $1", key
            )
            if not row:
                return None
            age = time.time() - row["saved_at"]
            if age > CACHE_TTL:
                await conn.execute("DELETE FROM cache WHERE key = $1", key)
                return None
            logger.info(f"Cache hit: {key} (age: {int(age)}s)")
            return json.loads(row["data"])
    except Exception as e:
        logger.error(f"Cache get error: {e}")
        return None


async def set(key: str, data: dict):
    key = key.lower().strip()
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO cache (key, data, saved_at) VALUES ($1, $2, $3)
                   ON CONFLICT (key) DO UPDATE SET data=excluded.data, saved_at=excluded.saved_at""",
                key, json.dumps(data, ensure_ascii=False), time.time()
            )
        logger.info(f"Cached: {key}")
    except Exception as e:
        logger.error(f"Cache set error: {e}")


async def size() -> int:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            return await conn.fetchval("SELECT COUNT(*) FROM cache")
    except Exception:
        return 0


async def clear_expired() -> int:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM cache WHERE $1 - saved_at > $2",
                time.time(), CACHE_TTL
            )
            deleted = int(result.split()[-1])
            if deleted:
                logger.info(f"Cleared {deleted} expired cache entries")
            return deleted
    except Exception as e:
        logger.error(f"Cache clear error: {e}")
        return 0
