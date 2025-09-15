# bot/main.py
import asyncio
import os
import sys
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
from loguru import logger

from .handlers import router

# Загрузка переменных окружения
load_dotenv()

# --- Конфигурация ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
API_URL = os.getenv("API_URL")

# --- Логирование ---
logger.remove()
logger.add(sys.stderr, level="INFO")

async def main():
    """Основная функция запуска бота."""
    if not TOKEN or not API_URL:
        logger.error("TELEGRAM_TOKEN или API_URL не установлены в .env файле.")
        return

    bot = Bot(token=TOKEN, parse_mode="HTML")
    dp = Dispatcher(storage=MemoryStorage())
    
    # Подключаем роутер с хендлерами
    dp.include_router(router)

    logger.info("Starting Telegram bot...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
