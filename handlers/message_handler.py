from telegram import Update
from telegram.ext import ContextTypes
from utils.logging_config import logger
from utils.telegram_utils import send_message_with_retry
from managers.session_manager import SessionManager
from managers.subscription_manager import SubscriptionManager
from clients.openai_client import OpenAIClient
import asyncio
from asyncio import Lock

class MessageHandler:
    def __init__(self, session_manager: SessionManager, subscription_manager: SubscriptionManager, openai_client: OpenAIClient):
        self.session_manager = session_manager
        self.subscription_manager = subscription_manager
        self.openai_client = openai_client
        self.media_groups = {}  # Store media groups at class level
        self.media_group_locks = {}

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

    async def handle_group_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle all text messages in group chats and check for bot mentions"""
        user_id = update.message.from_user.id
        message_text = update.message.text
        bot_username = context.bot.username
        
        logger.debug(f"Received group message: '{message_text}', checking for mention of @{bot_username}")
        
        # Check if the bot is mentioned in the message
        if f"@{bot_username}" not in message_text:
            return
            
        logger.info(f"Bot was mentioned in a group chat by user {user_id}")
        
        if not await self.subscription_manager.is_subscriber(user_id, update.get_bot()):
            await send_message_with_retry(update, "To use this bot, you need to be a subscriber of @korobo4ka_xoroni channel.")
            return
            
        # Remove the bot mention from the message
        user_message = message_text.replace(f"@{bot_username}", "").strip()
        
        # If this is a reply to another message, include that message's text as context
        replied_text = ""
        if update.message.reply_to_message and update.message.reply_to_message.text:
            replied_text = update.message.reply_to_message.text
            user_message = f"Context: {replied_text}\n\nQuestion: {user_message}"
            
        logger.info(f"Processing mention with message: {user_message}")
        
        # Get or create a session for the user
        session = self.session_manager.get_or_create_session(user_id)
        
        # Process the message with OpenAI
        reply = await self.openai_client.process_message(session, user_message)
        
        # Reply to the message that mentioned the bot
        await send_message_with_retry(update, reply)

    async def handle_image(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.message.from_user.id
        chat_type = update.message.chat.type
        logger.debug(f"Media group ID: {update.message.media_group_id}")
        logger.debug(f"Message: {update.message.to_dict()}")

        if chat_type in ['group', 'supergroup']:
            await send_message_with_retry(update, "Please use /ask command to interact with the bot in this group.")
            return

        # Check if message is part of a media group
        if update.message.media_group_id:
            media_group_id = update.message.media_group_id

            # Create lock for this media group if it doesn't exist
            if media_group_id not in self.media_group_locks:
                self.media_group_locks[media_group_id] = Lock()

            async with self.media_group_locks[media_group_id]:
                if media_group_id not in self.media_groups:
                    logger.debug(f"Creating new media group entry for {media_group_id}")
                    self.media_groups[media_group_id] = {
                        'messages': [update.message],
                        'caption': update.message.caption,  # Store caption from first message
                        'processed': False
                    }

                    # Schedule processing after a delay
                    async def process_media_group():
                        await asyncio.sleep(2)  # Wait for 2 seconds
                        async with self.media_group_locks[media_group_id]:
                            if media_group_id in self.media_groups and not self.media_groups[media_group_id]['processed']:
                                group_data = self.media_groups[media_group_id]
                                messages = group_data['messages']
                                caption = group_data['caption'] or ''

                                logger.debug(f"Processing media group {media_group_id}. Messages count: {len(messages)}")
                                logger.debug(f"Caption: {caption}")

                                if not caption:
                                    await send_message_with_retry(update, "Please add a caption to your images.")
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
            caption = update.message.caption or ''
            if not caption:
                await send_message_with_retry(update, "Please add a caption to your image.")
                return

            photo = update.message.photo[-1]
            file = await context.bot.get_file(photo.file_id)
            file_urls = [file.file_path]

            logger.info(f"Processing single image with caption: {caption}")
            session = self.session_manager.get_or_create_session(user_id)
            reply = await self.openai_client.process_message_with_image(session, caption, file_urls)
            await send_message_with_retry(update, reply)
