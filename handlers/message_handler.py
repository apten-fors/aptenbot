from telegram import Update
from telegram.ext import ContextTypes
from utils.logging_config import logger
from utils.telegram_utils import send_message_with_retry
from managers.session_manager import SessionManager
from managers.subscription_manager import SubscriptionManager
from clients.openai_client import OpenAIClient

class MessageHandler:
    def __init__(self, session_manager: SessionManager, subscription_manager: SubscriptionManager, openai_client: OpenAIClient):
        self.session_manager = session_manager
        self.subscription_manager = subscription_manager
        self.openai_client = openai_client

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.message.from_user.id
        chat_type = update.message.chat.type
        logger.info(f"Debug: {update.to_dict()}")

        if chat_type in ['group', 'supergroup']:
            await send_message_with_retry(update, "Please use /ask command to interact with the bot in this group.")
            return

        if not await self.subscription_manager.is_subscriber(user_id, update.get_bot()):
            await send_message_with_retry(update, "To use this bot, you need to be a subscriber of @korobo4ka_xoroni channel.")
            return

        user_message = update.message.text
        logger.info(f"Received message from user: {user_message}")

        session = self.session_manager.get_or_create_session(user_id)
        reply = await self.openai_client.process_message(session, user_message)
        await send_message_with_retry(update, reply)

    async def handle_reply(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.message.from_user.id
        chat_type = update.message.chat.type
        logger.info(f"Debug: {update.to_dict()}")

        if update.message.reply_to_message.from_user.id != context.bot.id:
            return

        if chat_type in ['group', 'supergroup']:
            if not await self.subscription_manager.is_subscriber(user_id, context.bot):
                await send_message_with_retry(update, "To use this bot, you need to be a subscriber of @korobo4ka_xoroni channel.")
                return

        if not update.message.reply_to_message:
            await send_message_with_retry(update, "Please reply to a bot's message to continue the conversation.")
            return

        user_message = update.message.text
        logger.info(f"Received reply from user: {user_message}")

        session = self.session_manager.get_or_create_session(user_id)
        reply = await self.openai_client.process_message(session, user_message)
        await send_message_with_retry(update, reply)

    async def handle_image(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        # Log the full update object for debugging
        logger.info(f"Received message with image. Full update: {update.to_dict()}")

        user_id = update.message.from_user.id
        chat_type = update.message.chat.type

        # Apply the same permission checks as text messages
        if chat_type in ['group', 'supergroup']:
            await send_message_with_retry(update, "Please use /ask command to interact with the bot in this group.")
            return

        if not await self.subscription_manager.is_subscriber(user_id, update.get_bot()):
            await send_message_with_retry(update, "To use this bot, you need to be a subscriber of @korobo4ka_xoroni channel.")
            return

        await send_message_with_retry(update, "I see you've sent an image! Image processing is currently under development. Stay tuned for updates!")
