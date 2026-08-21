from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from utils.logging_config import logger


class LoggingMiddleware(BaseMiddleware):
    def __init__(self, redact_message_text: bool = False) -> None:
        self.redact_message_text = redact_message_text
        super().__init__()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if self.redact_message_text and isinstance(event, Message):
            logger.info(
                "Received business event without message text: "
                "business_connection_id=%s chat_id=%s message_id=%s",
                event.business_connection_id,
                event.chat.id,
                event.message_id,
            )
            return await handler(event, data)
        logger.info(f"Received event: {event}")
        return await handler(event, data)
