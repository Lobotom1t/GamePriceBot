import asyncio
import logging
import os
import time
import re
import cache
import watchlist
import stats
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery, ReplyKeyboardRemove,
    BotCommand, BotCommandScopeDefault
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv
from steam_api import search_game_price

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()

ADMIN_ID = 805949459

ALIASES = {
    "gta 5": "Grand Theft Auto V",
    "gta v": "Grand Theft Auto V",
    "gta5": "Grand Theft Auto V",
    "gta 4": "Grand Theft Auto IV",
    "ведьмак 3": "The Witcher 3",
    "witcher 3": "The Witcher 3 Wild Hunt",
    "rdr2": "Red Dead Redemption 2",
    "rdr 2": "Red Dead Redemption 2",
    "киберпанк": "Cyberpunk 2077",
    "ds3": "Dark Souls III",
    "dark souls 3": "Dark Souls III",
    "re4": "Resident Evil 4",
    "re2": "Resident Evil 2",
    "hogwarts": "Hogwarts Legacy",
    "хогвартс": "Hogwarts Legacy",
    "элден ринг": "Elden Ring",
    "space marine": "Warhammer 40000 Space Marine 2",
}


def resolve_query(query: str) -> str:
    query = re.sub(r'[^\w\s\-\.\:\'\d]', '', query, flags=re.UNICODE).strip()
    query = re.sub(r'\s+', ' ', query).strip()
    return ALIASES.get(query.lower().strip(), query)


async def build_inline_buttons(prices: list, query: str, user_id: int):
    builder = InlineKeyboardBuilder()
    store_icons = {
        "Steam": "🎮",
        "Plati.ru ⚠️": "🔑",
        "Zaka-Zaka": "🛒",
        "IgroShop ⚠️": "🏪",
    }
    sorted_prices = sorted(
        [p for p in prices if p.get("price")],
        key=lambda x: x["price"]
    )
    for item in sorted_prices:
        icon = store_icons.get(item["store"], "🔗")
        price_str = f"{item['price']:,} ₽".replace(",", " ")
        builder.button(
            text=f"{icon} {item['store'].replace(' ⚠️', '')} — {price_str}",
            url=item["url"]
        )
    is_w = await watchlist.is_watching(user_id, query)
    if is_w:
        builder.button(text="🔕 Отписаться", callback_data=f"unwatch:{query}")
    else:
        builder.button(text="🔔 Следить за ценой", callback_data=f"watch:{query}")
    builder.adjust(1)
    return builder.as_markup()


def get_best_price(prices: list) -> int | None:
    valid = [p["price"] for p in prices if p.get("price")]
    return min(valid) if valid else None


def build_response(results: dict, from_cache: bool, elapsed: float = None) -> str:
    game_name = results["name"]
    prices = results["prices"]
    sorted_prices = sorted(
        prices, key=lambda x: x["price"] if x["price"] is not None else float("inf")
    )
    text = f"🎮 <b>{game_name}</b>\n\n💰 <b>Сравнение цен:</b>\n"
    emojis = ["🥇", "🥈", "🥉"]
    for i, item in enumerate(sorted_prices):
        prefix = emojis[i] if i < 3 else "  "
        price_str = f"{item['price']:,} ₽".replace(",", " ") if item["price"] else "Нет в продаже"
        if i == 0 and item["price"]:
            line = f"{prefix} <b>{item['store']}</b> — <b>{price_str}</b> ✅"
        else:
            line = f"{prefix} {item['store']} — {price_str}"
        if item.get("original_price") and item["original_price"] != item["price"] and item["price"]:
            original_str = f"{item['original_price']:,} ₽".replace(",", " ")
            discount = round((1 - item["price"] / item["original_price"]) * 100)
            line += f" <s>{original_str}</s> (-{discount}%)"
        text += line + "\n"
    if sorted_prices and sorted_prices[0].get("warning"):
        text += "\n⚠️ <i>Лучшая цена — ключ активации. Покупай на свой риск.</i>\n"
    if from_cache:
        text += "\n⚡️ <i>Из кэша · обновляется раз в сутки</i>"
    elif elapsed:
        text += f"\n⏱ <i>Найдено за {elapsed}с</i>"
    return text


async def setup_commands():
    commands = [
        BotCommand(command="start", description="🏠 Главное меню"),
        BotCommand(command="watchlist", description="📋 Мои подписки на цены"),
        BotCommand(command="popular", description="🔥 Популярные игры"),
        BotCommand(command="cache", description="🗄 Статистика кэша"),
        BotCommand(command="help", description="ℹ️ Помощь"),
    ]
    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())


@dp.message(Command("start"))
async def cmd_start(message: Message):
    await stats.track_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    await message.answer(
        "👋 Привет! Я сравниваю цены на игры в Steam, Plati.ru, Zaka-Zaka и IgroShop.\n\n"
        "📝 <b>Напиши название игры</b> и я найду лучшую цену:\n"
        "<code>Cyberpunk 2077</code>\n"
        "<code>Elden Ring</code>\n"
        "<code>GTA 5</code>\n\n"
        "Список команд — нажми /",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove()
    )


@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    data = await stats.get_stats()
    if not data:
        await message.answer("❌ Ошибка получения статистики.")
        return
    text = "📊 <b>Статистика бота</b>\n\n"
    text += f"👥 <b>Пользователи:</b>\n"
    text += f"  Всего: <b>{data['total_users']}</b>\n"
    text += f"  Новых за неделю: <b>{data['new_users_week']}</b>\n"
    text += f"  Активных сегодня: <b>{data['active_today']}</b>\n\n"
    text += f"🔍 <b>Поиски:</b>\n"
    text += f"  Всего: <b>{data['total_searches']}</b>\n"
    text += f"  Сегодня: <b>{data['searches_today']}</b>\n\n"
    text += f"🔔 <b>Подписок на цены:</b> {data['total_watchlist']}\n\n"
    if data['top_queries']:
        text += "🔥 <b>Топ запросов:</b>\n"
        for i, (query, cnt) in enumerate(data['top_queries'], 1):
            text += f"  {i}. {query} — {cnt} раз\n"
    await message.answer(text, parse_mode="HTML")


@dp.message(Command("popular"))
async def cmd_popular(message: Message):
    popular = ["Cyberpunk 2077", "GTA 5", "Elden Ring", "Red Dead Redemption 2",
               "Space Marine 2", "Hogwarts Legacy", "Dark Souls III", "Witcher 3"]
    text = "🔥 <b>Популярные игры:</b>\n\n"
    for game in popular:
        text += f"• <code>{game}</code>\n"
    text += "\nПросто скопируй название и отправь мне!"
    await message.answer(text, parse_mode="HTML")


@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "ℹ️ <b>Как пользоваться:</b>\n\n"
        "1. Напиши название игры на английском\n"
        "2. Получи сравнение цен из четырёх магазинов\n"
        "3. Нажми кнопку чтобы перейти в магазин\n"
        "4. Нажми 🔔 чтобы следить за снижением цены\n\n"
        "<b>Магазины:</b>\n"
        "🎮 Steam — официальный\n"
        "🔑 Plati.ru — ключи (дешевле, но риск)\n"
        "🛒 Zaka-Zaka — российский магазин\n"
        "🏪 IgroShop — российский магазин ключей\n\n"
        "<b>Работают сокращения:</b>\n"
        "<code>GTA 5</code>, <code>RDR2</code>, <code>Ведьмак 3</code> и др.",
        parse_mode="HTML"
    )


@dp.message(Command("watchlist"))
async def cmd_watchlist(message: Message):
    items = await watchlist.get_user_list(message.from_user.id)
    if not items:
        await message.answer("📋 Ты ни за чем не следишь.\n\nНайди игру и нажми 🔔 Следить за ценой.")
        return
    text = "📋 <b>Твои подписки:</b>\n\n"
    builder = InlineKeyboardBuilder()
    for item in items:
        price_str = f"{item['best_price']:,} ₽".replace(",", " ")
        text += f"🎮 {item['game_name']} — {price_str}\n"
        builder.button(text=f"❌ {item['game_name']}", callback_data=f"unwatch:{item['query']}")
    builder.adjust(1)
    await message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())



@dp.message(Command("clearcache"))
async def cmd_clearcache(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("❗ Укажи название: /clearcache The Evil Within 2")
        return
    key = args[1].lower().strip()
    pool = await __import__('db').get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM cache WHERE key = $1", key)
        deleted = result.split()[-1]
    if deleted == "1":
        await message.answer(f"✅ Кэш для <b>{args[1]}</b> очищен.", parse_mode="HTML")
    else:
        await message.answer(f"❌ Ключ <b>{args[1]}</b> не найден в кэше.", parse_mode="HTML")

@dp.message(Command("cache"))
async def cmd_cache(message: Message):
    n = await cache.size()
    await message.answer(f"🗄 В кэше: <b>{n}</b> игр\n⏱ Время жизни: 24 часа", parse_mode="HTML")


@dp.message(Command("search"))
async def cmd_search(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("❗ Укажи название: /search Cyberpunk 2077")
        return
    await process_search(message, args[1])


@dp.callback_query(F.data.startswith("watch:"))
async def handle_watch(callback: CallbackQuery):
    query = callback.data.split(":", 1)[1]
    cached = await cache.get(query)
    if not cached:
        await callback.answer("Сначала найди игру заново.", show_alert=True)
        return
    best_price = get_best_price(cached["prices"])
    if not best_price:
        await callback.answer("Нет актуальной цены.", show_alert=True)
        return
    added = await watchlist.add(callback.from_user.id, query, cached["name"], best_price)
    await callback.answer(f"🔔 Слежу за {cached['name']}!" if added else "Уже следишь.")
    buttons = await build_inline_buttons(cached["prices"], query, callback.from_user.id)
    await callback.message.edit_reply_markup(reply_markup=buttons)


@dp.callback_query(F.data.startswith("unwatch:"))
async def handle_unwatch(callback: CallbackQuery):
    query = callback.data.split(":", 1)[1]
    removed = await watchlist.remove(callback.from_user.id, query)
    await callback.answer("🔕 Подписка отменена." if removed else "Подписка не найдена.")
    cached = await cache.get(query)
    if cached:
        buttons = await build_inline_buttons(cached["prices"], query, callback.from_user.id)
        await callback.message.edit_reply_markup(reply_markup=buttons)


@dp.message(F.text & ~F.text.startswith("/"))
async def handle_text(message: Message):
    await stats.track_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    text = message.text.strip()
    question_words = ["сколько", "почём", "цена", "стоит", "стоимость", "как", "где", "что"]
    if any(text.lower().startswith(w) for w in question_words):
        await message.answer(
            "🎮 Напиши просто <b>название игры</b>:\n<code>Cyberpunk 2077</code>\n<code>GTA 5</code>",
            parse_mode="HTML"
        )
        return
    await process_search(message, text)


async def process_search(message: Message, query: str):
    user_id = message.from_user.id
    resolved = resolve_query(query)
    await stats.track_search(user_id, resolved)

    cached = await cache.get(resolved)
    if cached:
        text = build_response(cached, from_cache=True)
        buttons = await build_inline_buttons(cached["prices"], resolved, user_id)
        await message.answer(text, parse_mode="HTML", reply_markup=buttons, disable_web_page_preview=True)
        return

    searching_msg = await message.answer(f"🔍 Ищу <b>{resolved}</b>...", parse_mode="HTML")
    start = time.time()
    results = await search_game_price(resolved)
    elapsed = round(time.time() - start, 1)

    if not results:
        await searching_msg.edit_text(
            f"😔 Игра <b>{query}</b> не найдена.\n\nПопробуй написать полное название на английском.",
            parse_mode="HTML"
        )
        return

    await cache.set(resolved, results)
    text = build_response(results, from_cache=False, elapsed=elapsed)
    buttons = await build_inline_buttons(results["prices"], resolved, user_id)
    await searching_msg.edit_text(text, parse_mode="HTML", reply_markup=buttons, disable_web_page_preview=True)


async def check_prices():
    while True:
        await asyncio.sleep(86400)
        logger.info("Checking watchlist prices...")
        items = await watchlist.get_all()
        for item in items:
            try:
                results = await search_game_price(item["query"])
                if not results:
                    continue
                new_price = get_best_price(results["prices"])
                if not new_price:
                    continue
                old_price = item["best_price"]
                if new_price < old_price:
                    drop = old_price - new_price
                    pct = round(drop / old_price * 100)
                    await bot.send_message(
                        item["user_id"],
                        f"🔥 <b>Цена упала!</b>\n\n"
                        f"🎮 {results['name']}\n"
                        f"💰 Было: <s>{old_price:,} ₽</s>\n"
                        f"✅ Стало: <b>{new_price:,} ₽</b> (-{pct}%, -{drop:,} ₽)\n\n"
                        f"Напиши <code>{item['query']}</code> чтобы увидеть все цены".replace(",", " "),
                        parse_mode="HTML"
                    )
                    await watchlist.update_price(item["user_id"], item["query"], new_price)
                await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"Price check error for {item['query']}: {e}")


async def main():
    cleared = await cache.clear_expired()
    n = await cache.size()
    logger.info(f"Bot started! Cache: {n} entries, cleared {cleared} expired")
    await setup_commands()
    asyncio.create_task(check_prices())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
