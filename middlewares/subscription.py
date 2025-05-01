from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject
from utils.logging_config import logger
from config import CHANNEL_ID

class SubscriptionMiddleware(BaseMiddleware):
    def __init__(self, subscription_manager):
        self.subscription_manager = subscription_manager
        super().__init__()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id
            if not await self.subscription_manager.is_subscriber(user_id, data["bot"]):
                await event.answer(f"To use this bot, you need to be a subscriber of {CHANNEL_ID} channel.")
                return

        return await handler(event, data)
