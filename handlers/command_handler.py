from telegram import Update
from telegram.ext import ContextTypes
from utils.logging_config import logger
from utils.telegram_utils import send_message_with_retry
from managers.session_manager import SessionManager
from managers.subscription_manager import SubscriptionManager
from clients.openai_client import OpenAIClient

class CommandHandler:
    def __init__(self, session_manager: SessionManager, subscription_manager: SubscriptionManager, openai_client: OpenAIClient):
        self.session_manager = session_manager
        self.subscription_manager = subscription_manager
        self.openai_client = openai_client

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await send_message_with_retry(update, 'Hi, I am a bot that uses ChatGPT. Use /ask followed by your question to get a response in groups. For private chats, just send your question directly.')

    async def ask(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.message.from_user.id

        if not await self.subscription_manager.is_subscriber(user_id, context.bot):
            await send_message_with_retry(update, "To use this bot, you need to be a subscriber of @korobo4ka_xoroni channel.")
            return

        if not context.args:
            await send_message_with_retry(update, "Usage: /ask <your question>")
            return

        user_message = ' '.join(context.args)
        logger.info(f"Received message from user: {user_message}")

        session = self.session_manager.get_or_create_session(user_id)
        reply = await self.openai_client.process_message(session, user_message)
        await send_message_with_retry(update, reply)

    async def reset_session(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.message.from_user.id
        logger.info(f"Resetting session for user: {user_id}")

        self.session_manager.reset_session(user_id)
        await send_message_with_retry(update, "Session reset. Let's start fresh!")
