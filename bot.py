"""
Бот-обёртка для мини-приложения «Плеер».

Запуск:
    pip install "aiogram>=3.7"
    export BOT_TOKEN="123456:ABC..."          # токен от @BotFather
    export WEBAPP_URL="https://example.com/"  # HTTPS-адрес, где лежит index.html
    python bot.py
"""

import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    MenuButtonWebApp,
    ReplyKeyboardMarkup,
    WebAppInfo,
)

BOT_TOKEN = os.environ["BOT_TOKEN"]
WEBAPP_URL = os.environ["WEBAPP_URL"]  # обязательно https://

dp = Dispatcher()


def keyboards() -> tuple[ReplyKeyboardMarkup, InlineKeyboardMarkup]:
    web_app = WebAppInfo(url=WEBAPP_URL)
    reply = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🎧 Открыть плеер", web_app=web_app)]],
        resize_keyboard=True,
    )
    inline = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🎧 Слушать", web_app=web_app)]]
    )
    return reply, inline


@dp.message(CommandStart())
async def start(message: Message) -> None:
    reply, inline = keyboards()
    await message.answer(
        "Плеер готов. Нажмите кнопку — откроется мини-приложение "
        "с очередью, перемоткой и избранным.",
        reply_markup=reply,
    )
    await message.answer("Или запустите прямо отсюда:", reply_markup=inline)


@dp.message(F.web_app_data)
async def from_webapp(message: Message) -> None:
    """Сюда прилетает то, что мини-апп отправил через Telegram.WebApp.sendData()."""
    await message.answer(f"Мини-приложение прислало: {message.web_app_data.data}")


@dp.message()
async def fallback(message: Message) -> None:
    reply, _ = keyboards()
    await message.answer("Команда /start откроет плеер.", reply_markup=reply)


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    # Кнопка меню слева от поля ввода — открывает то же мини-приложение
    await bot.set_chat_menu_button(
        menu_button=MenuButtonWebApp(text="Плеер", web_app=WebAppInfo(url=WEBAPP_URL))
    )
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
