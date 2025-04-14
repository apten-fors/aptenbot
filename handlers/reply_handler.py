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
        is_group = update.message.chat.type in ['group', 'supergroup']

        # Check if the bot is mentioned in the reply
        bot_mentioned = f"@{bot_username}" in message_text

        # --- Logic for Group Replies with Mention ---
        if is_group and bot_mentioned:
            logger.info(f"Processing reply with mention in group by user {user_id}")

            if not await self.subscription_manager.is_subscriber(user_id, context.bot):
                await send_message_with_retry(update, "To use this bot, you need to be a subscriber of @korobo4ka_xoroni channel.")
                return

            # Remove the bot mention from the reply text
            user_message = message_text.replace(f"@{bot_username}", "").strip()

            # Get context from the replied-to message
            replied_text = ""
            if update.message.reply_to_message:
                if update.message.reply_to_message.text:
                    replied_text = update.message.reply_to_message.text
                elif update.message.reply_to_message.caption:
                    replied_text = update.message.reply_to_message.caption

            if replied_text:
                # Combine context and the reply message
                user_message = f"Context: {replied_text}\n\nQuestion: {user_message}"
            else:
                 # If replied message has no text, just use the reply text
                 logger.debug("Replied-to message has no text/caption, using reply message directly.")

            logger.info(f"Processing mention reply with context: {user_message}")

            # Get or create a session for this user
            session = self.session_manager.get_or_create_session(user_id)
            model_provider = self.session_manager.get_model_provider(user_id)

            # Process the message with the appropriate AI model
            if model_provider == "claude":
                reply = await self.claude_client.process_message(session, user_message)
            else:
                reply = await self.openai_client.process_message(session, user_message)

            await send_message_with_retry(update, reply)
            return # Stop processing here

        # --- Logic for Private Replies or Replies to the Bot ---
        # Only process replies to the bot's message in private chats or if explicitly mentioned
        if update.message.reply_to_message and update.message.reply_to_message.from_user.username == bot_username:
            # Subscription check for replies to bot
            if not await self.subscription_manager.is_subscriber(user_id, context.bot):
                 await send_message_with_retry(update, "To use this bot, you need to be a subscriber of @korobo4ka_xoroni channel.")
                 return

            # Remove mention if present (it might be a reply to bot *with* mention)
            if bot_mentioned:
                message_text = message_text.replace(f"@{bot_username}", "").strip()

            logger.info(f"Processing direct reply to bot: {message_text}")

            session = self.session_manager.get_or_create_session(user_id)
            model_provider = self.session_manager.get_model_provider(user_id)

            if model_provider == "claude":
                reply = await self.claude_client.process_message(session, message_text)
            else:
                reply = await self.openai_client.process_message(session, message_text)

            await send_message_with_retry(update, reply)
        else:
            # Ignore replies in groups not mentioning the bot and not replying to the bot
            if is_group:
                 logger.debug("Ignoring reply in group: not to bot and no mention.")
                 return
