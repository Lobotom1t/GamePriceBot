import aiohttp
import logging

logger = logging.getLogger(__name__)

DIGISELLER_API = "https://api.digiseller.com/api/cataloguer/front/products"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}


async def search_plati(session: aiohttp.ClientSession, query: str, usd_rate: float = 90.0) -> dict | None:
    """Ищем игру через Digiseller API (используется Plati.market)."""
    params = {
        "productName": query,
        "ownerId": "plati",
        "currency": "RUB",
        "page": 1,
        "count": 10,
        "sortBy": "popular",
        "lang": "ru-RU",
    }

    try:
        async with session.get(
            DIGISELLER_API,
            params=params,
            headers=HEADERS,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            logger.info(f"Digiseller status: {resp.status}")
            if resp.status != 200:
                return None

            data = await resp.json(content_type=None)
            items = data.get("content", {}).get("items", [])

            if not items:
                logger.info(f"Plati: no results for '{query}'")
                return None

            query_words = query.lower().split()

            for item in items:
                # Получаем русское название
                names = item.get("name", [])
                name_ru = next((n["value"] for n in names if n["locale"] == "ru-RU"), names[0]["value"] if names else "")
                name_lower = name_ru.lower()

                # Проверяем релевантность
                matches = sum(1 for w in query_words if w in name_lower)
                if matches < max(1, len(query_words) // 2):
                    continue

                price = item.get("price")
                product_id = item.get("product_id")

                if not price or not product_id:
                    continue

                # Оригинальная цена если есть скидка
                original_price = item.get("price_before_discount") or None
                if original_price == 0:
                    original_price = None

                logger.info(f"Plati found: {name_ru} — {price} ₽")

                return {
                    "store": "Plati.ru ⚠️",
                    "price": int(price),
                    "original_price": int(original_price) if original_price else None,
                    "url": f"https://plati.market/itm/{product_id}",
                    "warning": True,
                }

        return None

    except Exception as e:
        logger.error(f"Plati search error: {e}")
        return None
