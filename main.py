from telegram.ext import ApplicationBuilder, CommandHandler as TelegramCommandHandler, MessageHandler as TelegramMessageHandler, filters
from config import TELEGRAM_BOT_TOKEN
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
import asyncio

class MentionFilter(ext_filters.MessageFilter):
    def __init__(self, username):
        super().__init__()
        self.username = username

    def filter(self, message):
        if message.text:
            return f"@{self.username}" in message.text
        if message.caption:
            return f"@{self.username}" in message.caption
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
        self.bot_username = None

    async def get_bot_username(self):
        # Get bot info from Telegram API
        bot_info = await self.application.bot.get_me()
        self.bot_username = bot_info.username
        logger.info(f"Bot username retrieved from Telegram API: @{self.bot_username}")
        return self.bot_username

    def register_handlers(self):
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

    def register_mention_handlers(self):
        # Create filter for bot mentions
        mention_filter = MentionFilter(self.bot_username)

        # Handler for bot mentions in groups
        self.application.add_handler(TelegramMessageHandler(
            mention_filter & filters.ChatType.GROUPS,
            self.message_handler.handle_group_message,
            block=True
        ))

        # Handler for all messages in groups
        self.application.add_handler(TelegramMessageHandler(
            (filters.TEXT | filters.CAPTION) & filters.ChatType.GROUPS,
            self.message_handler.handle_group_message
        ))

    async def setup(self):
        # Register basic handlers
        self.register_handlers()

        # Get bot username and register mention handlers
        await self.get_bot_username()
        self.register_mention_handlers()

        logger.info("All handlers registered")

    async def run_async(self):
        # Set up all handlers and get bot info
        await self.setup()

        # Start the bot
        logger.info("Starting the bot application")
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()

        # Keep the application running
        try:
            await self.application.updater.stop_on_signal()
        finally:
            await self.application.stop()
            await self.application.shutdown()

    def run(self):
        # Run the async application in the event loop
        asyncio.run(self.run_async())

if __name__ == "__main__":
    try:
        app = BotApp()
        app.run()
    except Exception as e:
        logger.error(f"Error in main application: {e}", exc_info=True)
