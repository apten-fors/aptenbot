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
import asyncio
from threading import Lock

class CommandHandler:
    def __init__(self, session_manager: SessionManager, subscription_manager: SubscriptionManager, openai_client: OpenAIClient, flux_client: FluxClient, instaloader_client: InstaloaderClient):
        self.session_manager = session_manager
        self.subscription_manager = subscription_manager
        self.openai_client = openai_client
        self.flux_client = flux_client
        self.instaloader_client = instaloader_client
        self.media_groups = {}  # Store media groups at class level
        self.media_group_locks = {}

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

    async def ask_with_image(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.message.from_user.id
        chat_type = update.message.chat.type

        if not await self.subscription_manager.is_subscriber(user_id, context.bot):
            await send_message_with_retry(update, "To use this bot, you need to be a subscriber of @korobo4ka_xoroni channel.")
            return

        logger.debug(f"Media group ID: {update.message.media_group_id}")
        logger.debug(f"Message: {update.message.to_dict()}")

        # Check if message is part of a media group
        if update.message.media_group_id:
            media_group_id = update.message.media_group_id

            # Create lock for this media group if it doesn't exist
            if media_group_id not in self.media_group_locks:
                self.media_group_locks[media_group_id] = Lock()

            async with self.media_group_locks[media_group_id]:
                if media_group_id not in self.media_groups:
                    logger.debug(f"Creating new media group entry for {media_group_id}")
                    caption = (update.message.caption or '').replace('/ask', '').strip()
                    self.media_groups[media_group_id] = {
                        'messages': [update.message],
                        'caption': caption,
                        'processed': False
                    }

                    # Schedule processing after a delay
                    async def process_media_group():
                        await asyncio.sleep(2)  # Wait for 2 seconds
                        async with self.media_group_locks[media_group_id]:
                            if media_group_id in self.media_groups and not self.media_groups[media_group_id]['processed']:
                                group_data = self.media_groups[media_group_id]
                                messages = group_data['messages']
                                caption = group_data['caption']

                                logger.debug(f"Processing media group {media_group_id}. Messages count: {len(messages)}")
                                logger.debug(f"Caption: {caption}")

                                if not caption:
                                    await send_message_with_retry(update, "Usage: /ask <your question>")
                                    return

                                # Process all photos
                                file_urls = []
                                for message in messages:
                                    if message.photo:
                                        file = await context.bot.get_file(message.photo[-1].file_id)
                                        file_urls.append(file.file_path)

                                if file_urls:
                                    logger.info(f"Processing {len(file_urls)} images with caption: {caption}")
                                    session = self.session_manager.get_or_create_session(user_id)
                                    reply = await self.openai_client.process_message_with_image(session, caption, file_urls)
                                    await send_message_with_retry(update, reply)

                                # Cleanup
                                del self.media_groups[media_group_id]
                                del self.media_group_locks[media_group_id]

                    # Start the delayed processing task
                    asyncio.create_task(process_media_group())
                else:
                    # Add to existing group
                    logger.debug(f"Adding message to existing group {media_group_id}")
                    self.media_groups[media_group_id]['messages'].append(update.message)
            return

        else:
            # Single photo case
            caption = (update.message.caption or '').replace('/ask', '').strip()
            if not caption:
                await send_message_with_retry(update, "Usage: /ask <your question>")
                return

            photo = update.message.photo[-1]
            file = await context.bot.get_file(photo.file_id)
            file_urls = [file.file_path]

            logger.info(f"Processing single image with caption: {caption}")
            session = self.session_manager.get_or_create_session(user_id)
            reply = await self.openai_client.process_message_with_image(session, caption, file_urls)
            await send_message_with_retry(update, reply)
