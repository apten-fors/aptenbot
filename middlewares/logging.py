from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from utils.logging_config import logger

class LoggingMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: TelegramObject, data: dict):
        logger.info(f"Received event: {event}")
        return await handler(event, data)