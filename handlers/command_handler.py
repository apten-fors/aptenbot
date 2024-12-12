import re
from telegram import Update
from telegram.ext import ContextTypes
from utils.logging_config import logger
from utils.telegram_utils import send_message_with_retry, send_pic_with_retry, send_video_with_retry
from managers.session_manager import SessionManager
from managers.subscription_manager import SubscriptionManager
from clients.openai_client import OpenAIClient
from clients.flux_client import FluxClient
from clients.instaloader import InstaloaderClient
from config import OPENAI_MODEL

class CommandHandler:
    def __init__(self, session_manager: SessionManager, subscription_manager: SubscriptionManager, openai_client: OpenAIClient, flux_client: FluxClient, instaloader_client: InstaloaderClient):
        self.session_manager = session_manager
        self.subscription_manager = subscription_manager
        self.openai_client = openai_client
        self.flux_client = flux_client
        self.instaloader_client = instaloader_client

    @staticmethod
    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await send_message_with_retry(update, f'Hi, I am an useful ChatGPT bot. I use {OPENAI_MODEL} from OpenAI. \
                                      Use /ask followed by your question to get a response in groups. \
                                      For private chats, just send your question directly. \
                                      When you reply to bot it will initiate a new session with storing context. \
                                      Use /reset to reset the session or session will expire after 1 hour. \
                                      Use /insta to download instagram video.')

    async def ask(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.message.from_user.id

        if not await self.subscription_manager.is_subscriber(user_id, context.bot):
            await send_message_with_retry(update, "To use this bot, you need to be a subscriber of @korobo4ka_xoroni channel.")
            return

        if not context.args:
            await send_message_with_retry(update, "Usage: /ask <your question>")
            return

        user_message = ' '.join(context.args)
        logger.debug(f'Full message: {update.to_dict()}')
        logger.info(f"Received message from user: {user_message}")

        session = self.session_manager.get_or_create_session(user_id)
        reply = await self.openai_client.process_message(session, user_message)
        await send_message_with_retry(update, reply)

    async def reset_session(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.message.from_user.id
        logger.info(f"Resetting session for user: {user_id}")

        self.session_manager.reset_session(user_id)
        await send_message_with_retry(update, "Session reset. Let's start fresh!")

    ### similar as ask but send request to black forest api
    async def img(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.message.from_user.id

        if not await self.subscription_manager.is_subscriber(user_id, context.bot):
            await send_message_with_retry(update, "To use this bot, you need to be a subscriber of @korobo4ka_xoroni channel.")
            return

        if not context.args:
            await send_message_with_retry(update, "Usage: /img <your prompt>")
            return

        user_message = ' '.join(context.args)
        logger.info(f"Received message from user: {user_message}")

        reply = await self.flux_client.generate_image(user_message)
        await send_pic_with_retry(update, reply)

    async def insta(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.message.from_user.id

        if not await self.subscription_manager.is_subscriber(user_id, context.bot):
            await send_message_with_retry(update, "To use this bot, you need to be a subscriber of @korobo4ka_xoroni channel.")
            return

        if not context.args:
            await send_message_with_retry(update, "Usage: /insta <link to instagram video>")
            return

        user_message = ' '.join(context.args)
        logger.info(f"Received message from user: {user_message}")

        # Extract URL using regex
        url_pattern = r'https?://(?:www\.)?instagram\.com/[^\s]+'
        match = re.search(url_pattern, user_message)

        if not match:
            await send_message_with_retry(update, "Please provide a valid Instagram URL")
            return

        instagram_url = match.group(0)
        ok, path = self.instaloader_client.download_video(instagram_url)
        if not ok:
            await send_message_with_retry(update, f"Something went wrong: {path}")
            return

        await send_video_with_retry(update, path)

    async def ask_with_image(self, update, context):
        user_id = update.message.from_user.id
        chat_type = update.message.chat.type

        if chat_type in ['group', 'supergroup']:
            await send_message_with_retry(update, "Please use /ask command to interact with the bot in this group.")
            return

        if not await self.subscription_manager.is_subscriber(user_id, context.bot):
            await send_message_with_retry(update, "To use this bot, you need to be a subscriber of @korobo4ka_xoroni channel.")
            return

        logger.debug(f"Full message: {update.to_dict()}")
        # Extract the caption without the command
        caption = update.message.caption.replace('/ask', '').strip()
        logger.info(f"Received message from user: {caption}")
        if not caption:
            await send_message_with_retry(update, "Usage: /ask <your question>")
            return

        # Initialize list for file URLs
        file_urls = []

        # Check if message is part of a media group
        if update.message.media_group_id:
            media_group_id = update.message.media_group_id
            media_messages = context.chat_data.get(media_group_id, [])

            # Add the current message to the group
            media_messages.append(update.message)
            context.chat_data[media_group_id] = media_messages

            # Wait for the complete media group
            if len(media_messages) == update.message.media_group_count:
                for message in media_messages:
                    if message.photo:
                        file = await context.bot.get_file(message.photo[-1].file_id)
                        file_urls.append(file.file_path)
                del context.chat_data[media_group_id]  # Cleanup after processing
            else:
                return  # Wait for the remaining messages

        else:
            # Single photo case
            photo = update.message.photo[-1]
            file = await context.bot.get_file(photo.file_id)
            file_urls.append(file.file_path)

        logger.info(f"File URLs: {file_urls}")

        session = self.session_manager.get_or_create_session(user_id)
        reply = await self.openai_client.process_message_with_image(session, caption, file_urls)

        await send_message_with_retry(update, reply)
