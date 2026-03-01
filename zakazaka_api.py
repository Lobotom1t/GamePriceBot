import aiohttp
import logging
import re
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

SEARCH_URL = "https://zaka-zaka.com/search/?ask={query}"
BASE_URL = "https://zaka-zaka.com"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9",
}


async def search_zakazaka(session: aiohttp.ClientSession, query: str) -> dict | None:
    """Ищем игру на zaka-zaka.com."""
    url = SEARCH_URL.format(query=query.replace(" ", "+"))

    try:
        async with session.get(
            url,
            headers=HEADERS,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            logger.info(f"ZakaZaka status: {resp.status}")
            if resp.status != 200:
                return None

            html = await resp.text()
            return parse_zakazaka_html(html, query)

    except Exception as e:
        logger.error(f"ZakaZaka error: {e}")
        return None


def parse_zakazaka_html(html: str, query: str) -> dict | None:
    soup = BeautifulSoup(html, "html.parser")
    query_words = query.lower().split()

    cards = soup.find_all("a", class_="game-block")
    logger.info(f"ZakaZaka: found {len(cards)} cards")

    for card in cards:
        # Название
        name_tag = card.find("div", class_="game-block-name")
        if not name_tag:
            continue
        name = name_tag.get_text(strip=True)
        name_lower = name.lower()

        # Проверяем релевантность
        matches = sum(1 for w in query_words if w in name_lower)
        if matches < max(1, len(query_words) // 2):
            continue

        # Цена
        price_tag = card.find("div", class_="game-block-price")
        if not price_tag:
            continue

        price_text = price_tag.get_text(strip=True)
        digits = re.sub(r"[^\d]", "", price_text)
        if not digits:
            continue
        price = int(digits)

        # Оригинальная цена (до скидки)
        original_price = None
        discount_tag = card.find("div", class_="game-block-discount-sum")
        if discount_tag:
            discount_text = re.sub(r"[^\d]", "", discount_tag.get_text(strip=True))
            if discount_text:
                original_price = price + int(discount_text)

        # Ссылка
        href = card.get("href", "")
        item_url = href if href.startswith("http") else BASE_URL + href

        logger.info(f"ZakaZaka found: {name} — {price} ₽")

        return {
            "store": "Zaka-Zaka",
            "price": price,
            "original_price": original_price,
            "url": item_url,
        }

    logger.warning(f"ZakaZaka: no match for '{query}'")
    return None
