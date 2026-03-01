import aiohttp
import logging
import re
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

SEARCHANISE_API = "https://searchserverapi.com/getresults"
API_KEY = "9o5T0N3y8G"
BASE_URL = "https://www.igroshop.com"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9",
}


async def search_igroshop(session: aiohttp.ClientSession, query: str) -> dict | None:
    """Ищем игру на igroshop.com — сначала находим ссылку, потом берём рублёвую цену со страницы."""

    # Шаг 1: находим товар через Searchanise
    item_url, item_name = await find_item(session, query)
    if not item_url:
        return None

    # Шаг 2: парсим рублёвую цену со страницы товара
    price_rub, original_rub = await get_rub_price(session, item_url)
    if not price_rub:
        return None

    logger.info(f"IgroShop found: {item_name} — {price_rub} ₽")

    return {
        "store": "IgroShop ⚠️",
        "price": price_rub,
        "original_price": original_rub,
        "url": item_url,
        "warning": True,
    }


async def find_item(session: aiohttp.ClientSession, query: str) -> tuple[str, str] | tuple[None, None]:
    """Находим ссылку на товар через Searchanise."""
    params = {
        "api_key": API_KEY,
        "q": query,
        "maxResults": 5,
        "startIndex": 0,
        "items": "true",
        "pages": "false",
        "categories": "false",
        "suggestions": "false",
        "output": "json",
    }

    try:
        async with session.get(
            SEARCHANISE_API,
            params=params,
            headers=HEADERS,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            if resp.status != 200:
                return None, None

            data = await resp.json(content_type=None)
            items = data.get("items", [])

            if not items:
                return None, None

            query_words = query.lower().split()
            skip_words = ["dlc", "soundtrack", "season pass", "xbox", "playstation", "ps4", "ps5"]

            for item in items:
                name = item.get("title", "")
                name_lower = name.lower()

                if item.get("quantity", 0) == 0:
                    continue
                if any(w in name_lower for w in skip_words):
                    continue

                matches = sum(1 for w in query_words if w in name_lower)
                if matches < max(1, len(query_words) // 2):
                    continue

                url = item.get("link", "")
                if not url:
                    continue

                logger.info(f"IgroShop item: {name} -> {url}")
                return url, name

        return None, None

    except Exception as e:
        logger.error(f"IgroShop search error: {e}")
        return None, None


async def get_rub_price(session: aiohttp.ClientSession, url: str) -> tuple[int, int | None]:
    """Парсим рублёвую цену прямо со страницы товара."""
    try:
        async with session.get(
            url,
            headers=HEADERS,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            if resp.status != 200:
                return None, None

            html = await resp.text()
            soup = BeautifulSoup(html, "html.parser")

            # Основная цена: <span class="price-num">3545</span>
            price_tag = soup.find("span", class_="price-num")
            if not price_tag:
                return None, None

            price_text = re.sub(r"[^\d]", "", price_tag.get_text(strip=True))
            if not price_text:
                return None, None

            price_rub = int(price_text)

            # Оригинальная цена (до скидки)
            original_rub = None
            original_tag = soup.find("span", class_="price-num-old") or \
                           soup.find("span", class_=re.compile(r"old.price|list.price|original", re.I))
            if original_tag:
                original_text = re.sub(r"[^\d]", "", original_tag.get_text(strip=True))
                if original_text:
                    original_rub = int(original_text)

            logger.info(f"IgroShop price: {price_rub} RUB (original: {original_rub})")
            return price_rub, original_rub

    except Exception as e:
        logger.error(f"IgroShop price parse error: {e}")
        return None, None
