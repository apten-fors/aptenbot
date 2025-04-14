from telegram.ext import ApplicationBuilder, CommandHandler as TelegramCommandHandler, MessageHandler as TelegramMessageHandler, filters
from config import TELEGRAM_BOT_TOKEN, BOT_USERNAME
from utils.logging_config import logger
from managers.session_manager import SessionManager
from managers.subscription_manager import SubscriptionManager
from clients.openai_client import OpenAIClient
from clients.claude_client import ClaudeClient
from clients.flux_client import FluxClient
from clients.instaloader import InstaloaderClient
from handlers.message_handler import MessageHandler
from handlers.command_handler import CommandHandler
from handlers.reply_handler import ReplyHandler
from telegram.ext import filters as ext_filters

class MentionFilter(ext_filters.MessageFilter):
    def __init__(self, username):
        super().__init__()
        self.username = username
        logger.debug(f"MentionFilter initialized for username: @{self.username}")

    def filter(self, message):
        target_mention = f"@{self.username}"
        text_to_check = None
        source = None

        if message.text:
            text_to_check = message.text
            source = "text"
        elif message.caption:
            text_to_check = message.caption
            source = "caption"

        if text_to_check:
            # Log before check
            logger.debug(f"MentionFilter checking message ({source}): '{text_to_check}' for '{target_mention}' (case-insensitive)")
            # Perform case-insensitive check
            result = target_mention.lower() in text_to_check.lower()
            # Log after check
            logger.debug(f"MentionFilter result: {result}")
            return result
        else:
            # Log if no text/caption
            logger.debug("MentionFilter: Message has no text or caption to check.")
            return False

class BotApp:
    def __init__(self):
        self.session_manager = SessionManager()
        self.subscription_manager = SubscriptionManager()
        self.openai_client = OpenAIClient()
        self.claude_client = ClaudeClient()
        self.flux_client = FluxClient()
        self.instaloader_client = InstaloaderClient()
        self.message_handler = MessageHandler(self.session_manager, self.subscription_manager,
                                             self.openai_client, self.claude_client)
        self.command_handler = CommandHandler(self.session_manager,
                                              self.subscription_manager,
                                              self.openai_client,
                                              self.claude_client,
                                              self.flux_client,
                                              self.instaloader_client)
        self.reply_handler = ReplyHandler(self.session_manager, self.subscription_manager,
                                          self.openai_client, self.claude_client)
        self.application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    def register_handlers(self):
        # Get bot username from config
        bot_username = BOT_USERNAME
        logger.info(f"Using bot username from config: @{bot_username}")

        # Register handlers that don't need bot username first
        self.application.add_handler(TelegramCommandHandler(["start", "help"], self.command_handler.start))
        self.application.add_handler(TelegramCommandHandler("ask", self.command_handler.ask, filters=filters.COMMAND))
        self.application.add_handler(TelegramCommandHandler("img", self.command_handler.img))
        self.application.add_handler(TelegramCommandHandler("insta", self.command_handler.insta))
        self.application.add_handler(TelegramCommandHandler("reset", self.command_handler.reset_session))
        self.application.add_handler(TelegramCommandHandler("set", self.command_handler.set_model))
        self.application.add_handler(TelegramMessageHandler(filters.TEXT & filters.REPLY, self.reply_handler.handle_reply))

        self.application.add_handler(TelegramMessageHandler(filters.TEXT & filters.ChatType.PRIVATE, self.message_handler.handle_message))
        self.application.add_handler(TelegramMessageHandler(filters.PHOTO & filters.ChatType.PRIVATE, self.message_handler.handle_image))
        self.application.add_handler(
            TelegramMessageHandler(
                filters.PHOTO & filters.CaptionRegex(r'^/ask') & filters.ChatType.GROUPS,
                self.command_handler.ask_with_image,
                block=False
            )
        )
        self.application.add_handler(
            TelegramMessageHandler(
                filters.PHOTO & filters.ChatType.GROUPS & filters.ALL,
                self.command_handler.ask_with_image,
                block=False
            )
        )

        # Register mention handlers
        # Create filter for bot mentions
        mention_filter = MentionFilter(bot_username)

        # Handler for bot mentions in groups
        self.application.add_handler(TelegramMessageHandler(
            mention_filter & (filters.TEXT | filters.CAPTION) & filters.ChatType.GROUPS,
            self.message_handler.handle_group_message,
            block=True # Make sure this handler blocks if mention found
        ))

        logger.info("All handlers registered")

    def run(self):
        # Register handlers
        self.register_handlers()

        # Run the bot using the standard blocking polling method
        logger.info("Starting the bot application using run_polling")
        self.application.run_polling()

if __name__ == "__main__":
    try:
        app = BotApp()
        app.run()
    except Exception as e:
        logger.error(f"Error in main application: {e}", exc_info=True)
