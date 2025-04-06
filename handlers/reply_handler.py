from telegram import Update
from telegram.ext import ContextTypes
from utils.logging_config import logger
from utils.telegram_utils import send_message_with_retry
from managers.session_manager import SessionManager
from managers.subscription_manager import SubscriptionManager
from clients.openai_client import OpenAIClient

class ReplyHandler:
    def __init__(self, session_manager: SessionManager, subscription_manager: SubscriptionManager, openai_client: OpenAIClient):
        self.session_manager = session_manager
        self.subscription_manager = subscription_manager
        self.openai_client = openai_client

    async def handle_reply(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.message.from_user.id
        message_text = update.message.text
        bot_username = context.bot.username

        # Check if the bot is mentioned in the reply
        bot_mentioned = f"@{bot_username}" in message_text

        # If this is a group chat and the bot is not mentioned, ignore the message
        if update.message.chat.type in ['group', 'supergroup'] and not bot_mentioned:
            return

        # If the bot is mentioned, process the message as a mention
        if bot_mentioned:
            # Remove the bot mention from the message
            user_message = message_text.replace(f"@{bot_username}", "").strip()

            # Get the text of the message being replied to
            replied_text = ""
            if update.message.reply_to_message and update.message.reply_to_message.text:
                replied_text = update.message.reply_to_message.text
                user_message = f"Context: {replied_text}\n\nQuestion: {user_message}"

            logger.info(f"Processing mention in reply with message: {user_message}")

            # Check the subscription
            if not await self.subscription_manager.is_subscriber(user_id, update.get_bot()):
                await send_message_with_retry(update, "To use this bot, you need to be a subscriber of @korobo4ka_xoroni channel.")
                return

            # Process the message
            session = self.session_manager.get_or_create_session(user_id)
            reply = await self.openai_client.process_message(session, user_message)
            await send_message_with_retry(update, reply)
            return

        # Original logic for processing replies without a mention
        if not update.message.reply_to_message:
            await send_message_with_retry(update, "Please reply to a bot's message to continue the conversation.")
            return

        user_message = update.message.text
        logger.debug(f"Full message: {update.to_dict()}")
        logger.info(f"Received reply from user: {user_message}")

        session = self.session_manager.get_or_create_session(user_id)
        reply = await self.openai_client.process_message(session, user_message)
        await send_message_with_retry(update, reply)
