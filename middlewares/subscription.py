from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject
from utils.logging_config import logger
from config import CHANNEL_ID

import asyncio # For Lock if needed, though simple flag used here
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

class SubscriptionMiddleware(BaseMiddleware):
    def __init__(self, subscription_manager):
        self.subscription_manager = subscription_manager
        self.resolved_numeric_channel_id = None
        self.resolving_started = False # Simple flag for one-time resolution attempt
        # For scenarios with many concurrent first messages, a Lock might be better:
        # self.resolve_lock = asyncio.Lock()
        super().__init__()

    async def _resolve_channel_id(self, bot: Bot, channel_id_str: str):
        """Helper to resolve CHANNEL_ID to its numeric form."""
        try:
            # Try to convert to int directly first
            self.resolved_numeric_channel_id = int(channel_id_str)
            logger.info(f"CHANNEL_ID '{channel_id_str}' is already a numeric ID: {self.resolved_numeric_channel_id}")
        except ValueError:
            # Not a numeric ID, assume it's a username like "@mychannel"
            logger.info(f"CHANNEL_ID '{channel_id_str}' is not numeric, attempting to resolve via bot.get_chat().")
            try:
                chat_info = await bot.get_chat(chat_id=channel_id_str)
                self.resolved_numeric_channel_id = chat_info.id
                logger.info(f"Successfully resolved CHANNEL_ID '{channel_id_str}' to numeric ID: {self.resolved_numeric_channel_id}")
            except TelegramAPIError as e:
                logger.error(f"Failed to resolve CHANNEL_ID '{channel_id_str}' via bot.get_chat(): {e}. Bypass for channel messages will not work.")
                # Keep self.resolved_numeric_channel_id as None or set to a non-matchable value
                self.resolved_numeric_channel_id = -1 # Explicitly non-matchable
            except Exception as e:
                logger.error(f"An unexpected error occurred while resolving CHANNEL_ID '{channel_id_str}': {e}. Bypass for channel messages will not work.")
                self.resolved_numeric_channel_id = -1 # Explicitly non-matchable

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        bot = data.get("bot")
        if bot and self.resolved_numeric_channel_id is None and not self.resolving_started:
            self.resolving_started = True # Mark that resolution process has started
            # In a high concurrency scenario, self.resolve_lock might be used here
            # async with self.resolve_lock:
            #    if self.resolved_numeric_channel_id is None: # Double check after acquiring lock
            #        await self._resolve_channel_id(bot, str(CHANNEL_ID))
            await self._resolve_channel_id(bot, str(CHANNEL_ID))
            logger.info(f"CHANNEL_ID resolution attempt finished. Resolved ID: {self.resolved_numeric_channel_id}")


        if isinstance(event, Message):
            # Case 1: Message sent by the configured CHANNEL_ID (via sender_chat)
            if event.sender_chat and \
               self.resolved_numeric_channel_id is not None and \
               self.resolved_numeric_channel_id != -1 and \
               event.sender_chat.id == self.resolved_numeric_channel_id:
                logger.info(f"Message from configured channel (ID: {self.resolved_numeric_channel_id}), chat_id={event.chat.id}, sender_chat_id={event.sender_chat.id}. Bypassing user subscription check.")
                return await handler(event, data)

            # Case 2: Message from a regular user
            elif event.from_user:
                user_id = event.from_user.id
                # logger.info(f"Checking subscription for user_id {user_id} in chat_id {event.chat.id}.") # Can be noisy
                if not await self.subscription_manager.is_subscriber(user_id, data["bot"]):
                    logger.info(f"User {user_id} is not subscribed. Blocking message in chat {event.chat.id}.")
                    try:
                        # Use self.resolved_numeric_channel_id for the message, but fall back to CHANNEL_ID string if resolution failed
                        display_channel_name = str(CHANNEL_ID) # Default to original config string
                        # We don't have an easy way to get the channel *username* from the resolved numeric ID without another API call.
                        # So, for the denial message, using the original CHANNEL_ID string (which might be @username or numeric) is clearest.
                        await event.answer(f"To use this bot, you need to be a subscriber of the {display_channel_name} channel.")
                    except Exception as e:
                        logger.error(f"Error sending subscription denial message to {user_id}: {e}")
                    return # Block message
                else:
                    logger.debug(f"User {user_id} is subscribed. Allowing message.")
                    # Fall through to return await handler(event, data) at the end

            # Case 3: Other message types (e.g., not from user, not from sender_chat matching resolved channel)
            else:
                logger.debug(f"Message event (type: {type(event)}, chat_id: {event.chat.id}, sender_chat: {event.sender_chat}) is not from a specific user and not the configured channel. Allowing to pass.")
                # Fall through to return await handler(event, data) at the end

        # Default: Allow event to proceed if none of the above conditions resulted in a return
        return await handler(event, data)
