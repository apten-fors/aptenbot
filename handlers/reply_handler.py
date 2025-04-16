from telegram import Update
from telegram.ext import ContextTypes
from utils.logging_config import logger
from utils.telegram_utils import send_message_with_retry
from managers.session_manager import SessionManager
from managers.subscription_manager import SubscriptionManager
from clients.openai_client import OpenAIClient
from clients.claude_client import ClaudeClient

class ReplyHandler:
    def __init__(self, session_manager: SessionManager, subscription_manager: SubscriptionManager,
                 openai_client: OpenAIClient, claude_client: ClaudeClient):
        self.session_manager = session_manager
        self.subscription_manager = subscription_manager
        self.openai_client = openai_client
        self.claude_client = claude_client

    async def handle_reply(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.message.from_user.id
        message_text = update.message.text
        bot_username = context.bot.username

        # Check if the bot is mentioned in the reply
        bot_mentioned = f"@{bot_username}" in message_text

        # If this is a group chat and the bot is not mentioned, ignore the message
        if update.message.chat.type in ['group', 'supergroup'] and not bot_mentioned:
            return

        # If it's a reply to the bot's message, process it
        if update.message.reply_to_message and update.message.reply_to_message.from_user.username == bot_username:
            if not await self.subscription_manager.is_subscriber(user_id, context.bot):
                await send_message_with_retry(update, "To use this bot, you need to be a subscriber of @korobo4ka_xoroni channel.")
                return

            # If the bot is mentioned, remove the mention from the message text
            if bot_mentioned:
                message_text = message_text.replace(f"@{bot_username}", "").strip()

            logger.info(f"Processing reply to bot: {message_text}")

            # Get or create a session for this user
            session = self.session_manager.get_or_create_session(user_id)
            model_provider = self.session_manager.get_model_provider(user_id)

            # Process the message with the appropriate AI model
            if model_provider == "claude":
                reply = await self.claude_client.process_message(session, message_text)
            else:
                reply = await self.openai_client.process_message(session, message_text)

            await send_message_with_retry(update, reply)
