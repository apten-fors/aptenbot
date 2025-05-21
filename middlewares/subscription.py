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
        # Ensure CHANNEL_ID is treated as a string for comparison, as Telegram IDs can be large numbers.
        # Sender chat ID and CHANNEL_ID from config might be int or str depending on source.
        config_channel_id_str = str(CHANNEL_ID)

        if isinstance(event, Message):
            # Case 1: Message sent by the configured CHANNEL_ID (e.g., admin posting in channel, or channel auto-forwarding to linked group)
            if event.sender_chat and str(event.sender_chat.id) == config_channel_id_str:
                logger.info(f"Message from configured CHANNEL_ID ({config_channel_id_str}), chat_id={event.chat.id}, sender_chat_id={event.sender_chat.id}. Bypassing user subscription check.")
                return await handler(event, data) # Allow message to proceed

            # Case 2: Message from a regular user (not the channel itself via sender_chat)
            elif event.from_user:
                user_id = event.from_user.id
                logger.info(f"Checking subscription for user_id {user_id} in chat_id {event.chat.id}.")
                if not await self.subscription_manager.is_subscriber(user_id, data["bot"]):
                    logger.info(f"User {user_id} is not subscribed. Blocking message in chat {event.chat.id}.")
                    await event.answer(f"To use this bot, you need to be a subscriber of the {CHANNEL_ID} channel.")
                    return # Block message
                else:
                    logger.info(f"User {user_id} is subscribed. Allowing message.")
                    # Fall through to return await handler(event, data) at the end
            
            # Case 3: Other message types or scenarios (e.g. message not from user, not from sender_chat, service messages)
            else:
                logger.debug(f"Message event (type: {type(event)}, chat_id: {event.chat.id}) is not from a specific user (event.from_user is None) and not from the configured CHANNEL_ID via sender_chat. Allowing to pass.")
                # Fall through to return await handler(event, data) at the end

        # Default: Allow event to proceed if none of the above conditions resulted in a return
        return await handler(event, data)
