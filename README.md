# 🎮 GamePriceBot

Telegram-бот для поиска лучших цен на игры среди российских магазинов.

## Быстрый старт

### 1. Установи зависимости

```bash
pip install -r requirements.txt
```

### 2. Создай файл .env

Скопируй `.env.example` в `.env` и вставь свой токен:

```bash
cp .env.example .env
```

Открой `.env` и замени `your_token_here` на токен от @BotFather.

### 3. Запусти бота

```bash
python bot.py
```

## Как получить токен

1. Открой Telegram и найди @BotFather
2. Напиши `/newbot`
3. Придумай имя и username для бота
4. Скопируй токен в файл `.env`

## Структура проекта

```
gamepricebot/
├── bot.py           # Основная логика бота
├── steam_api.py     # Интеграция со Steam
├── requirements.txt
├── .env.example
└── README.md
```

## Дальнейшее развитие

- [ ] Добавить парсинг Plati.ru
- [ ] Кэш цен (Redis/SQLite)
- [ ] Уведомления о снижении цены
- [ ] Inline-режим для поиска прямо в чате
