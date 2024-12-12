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

        logger.debug(f"Chat type: {chat_type}")

        if chat_type in ['group', 'supergroup']:
            await send_message_with_retry(update, "Please use /ask command to interact with the bot in this group.")
            return

        if not await self.subscription_manager.is_subscriber(user_id, update.get_bot()):
            await send_message_with_retry(update, "To use this bot, you need to be a subscriber of @korobo4ka_xoroni channel.")
            return

        user_message = update.message.text
        logger.debug(f"Full message: {update.to_dict()}")
        logger.info(f"Received message from user: {user_message}")

        session = self.session_manager.get_or_create_session(user_id)
        reply = await self.openai_client.process_message(session, user_message)
        await send_message_with_retry(update, reply)

    async def handle_image(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        logger.debug(f"Full message: {update.to_dict()}")

        user_id = update.message.from_user.id
        chat_type = update.message.chat.type

        if chat_type in ['group', 'supergroup']:
            await send_message_with_retry(update, "Please use /ask command to interact with the bot in this group.")
            return

        # Extract the caption without the command
        caption = update.message.caption or ''  # Handle None case
        caption = caption.replace('/ask', '').strip()
        logger.info(f"Received message from user: {caption}")
        if not caption:
            await send_message_with_retry(update, "Usage: /ask <your question>")
            return

        # Initialize list for file URLs
        file_urls = []

        # Check if message is part of a media group
        if update.message.media_group_id:
            # Get all messages from the media group
            media_group = await context.bot.get_media_group(
                update.message.chat.id,
                update.message.message_id
            )
            # Collect URLs for all photos in the group
            for message in media_group:
                if message.photo:
                    file = await context.bot.get_file(message.photo[-1].file_id)
                    file_urls.append(file.file_path)
        else:
            # Single photo case
            photo = update.message.photo[-1]
            file = await context.bot.get_file(photo.file_id)
            file_urls.append(file.file_path)

        logger.info(f"File URLs: {file_urls}")

        session = self.session_manager.get_or_create_session(user_id)
        reply = await self.openai_client.process_message_with_image(session, caption, file_urls)

        await send_message_with_retry(update, reply)
