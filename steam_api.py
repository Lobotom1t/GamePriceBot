import aiohttp
import asyncio
import logging
import re
import cache
from bs4 import BeautifulSoup
from plati_api import search_plati
from zakazaka_api import search_zakazaka
from igroshop_api import search_igroshop

logger = logging.getLogger(__name__)

STEAM_SEARCH_URL = "https://store.steampowered.com/api/storesearch/"
STEAM_STORE_URL = "https://store.steampowered.com/app/"
CBR_URL = "https://www.cbr-xml-daily.ru/daily_json.js"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9",
    "Cookie": "Steam_Language=russian; timezoneOffset=10800,0",
}


async def get_usd_rate(session: aiohttp.ClientSession) -> float:
    try:
        async with session.get(CBR_URL, timeout=aiohttp.ClientTimeout(total=8)) as resp:
            data = await resp.json(content_type=None)
            return data["Valute"]["USD"]["Value"]
    except Exception:
        return 90.0


async def search_game_price(query: str) -> dict | None:
    cached = await cache.get(query)
    if cached:
        return cached

    async with aiohttp.ClientSession(headers=HEADERS) as session:
        (app_id, name), usd_rate = await asyncio.gather(
            find_app_id(session, query),
            get_usd_rate(session)
        )

        if not app_id:
            logger.warning(f"App not found: {query}")
            return None

        logger.info(f"Found: {name} (id={app_id}), rate={usd_rate}")

        steam_result, plati_result, zakazaka_result, igroshop_result = await asyncio.gather(
            get_steam_details(session, app_id, name),
            search_plati(session, query, usd_rate),
            search_zakazaka(session, query),
            search_igroshop(session, query)
        )

        if not steam_result:
            return None

        prices = steam_result["prices"]
        if plati_result:
            prices.append(plati_result)
        if zakazaka_result:
            prices.append(zakazaka_result)
        if igroshop_result:
            prices.append(igroshop_result)

        result = {"name": steam_result["name"], "app_id": app_id, "prices": prices}
        await cache.set(query, result)
        return result


async def find_app_id(session: aiohttp.ClientSession, query: str) -> tuple:
    params = {"term": query, "l": "russian", "cc": "US", "count": 5}
    try:
        async with session.get(STEAM_SEARCH_URL, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                return None, None
            data = await resp.json(content_type=None)
            items = data.get("items", [])
            logger.info(f"Search results: {[i.get('name') for i in items]}")
            if not items:
                return None, None
            return items[0]["id"], items[0]["name"]
    except Exception as e:
        logger.error(f"Search error: {e}")
        return None, None


async def get_steam_details(session: aiohttp.ClientSession, app_id: int, name: str) -> dict | None:
    url = f"{STEAM_STORE_URL}{app_id}/"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                return None
            html = await resp.text()
            soup = BeautifulSoup(html, "html.parser")

            title_tag = soup.find("div", class_="apphub_AppName")
            if title_tag:
                name = title_tag.get_text(strip=True)

            price_rub = None
            original_rub = None

            discount_block = soup.find("div", class_="discount_final_price")
            if discount_block:
                price_rub = parse_rub_price(discount_block.get_text(strip=True))
                original_block = soup.find("div", class_="discount_original_price")
                if original_block:
                    original_rub = parse_rub_price(original_block.get_text(strip=True))

            if price_rub is None:
                game_purchase = soup.find("div", class_="game_purchase_price")
                if game_purchase:
                    price_rub = parse_rub_price(game_purchase.get_text(strip=True))

            logger.info(f"Steam price: {price_rub} RUB")
            return {"name": name, "prices": [{"store": "Steam", "price": price_rub, "original_price": original_rub, "url": url}]}
    except Exception as e:
        logger.error(f"Steam parse error: {e}")
        return None


def parse_rub_price(text: str) -> int | None:
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else None
