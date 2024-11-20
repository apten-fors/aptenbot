from telegram.ext import ApplicationBuilder, CommandHandler as TelegramCommandHandler, MessageHandler as TelegramMessageHandler, filters
from config import TELEGRAM_BOT_TOKEN
from utils.logging_config import logger
from managers.session_manager import SessionManager
from managers.subscription_manager import SubscriptionManager
from clients.openai_client import OpenAIClient
from handlers.message_handler import MessageHandler
from handlers.command_handler import CommandHandler

class BotApp:
    def __init__(self):
        self.session_manager = SessionManager()
        self.subscription_manager = SubscriptionManager()
        self.openai_client = OpenAIClient()
        self.message_handler = MessageHandler(self.session_manager, self.subscription_manager, self.openai_client)
        self.command_handler = CommandHandler(self.session_manager, self.subscription_manager, self.openai_client)
        self.application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    def register_handlers(self):
        self.application.add_handler(TelegramCommandHandler("start", self.command_handler.start))
        self.application.add_handler(TelegramCommandHandler("ask", self.command_handler.ask))
        self.application.add_handler(TelegramCommandHandler("reset", self.command_handler.reset_session))
        self.application.add_handler(TelegramMessageHandler(filters.TEXT & filters.REPLY, self.message_handler.handle_reply))
        self.application.add_handler(TelegramMessageHandler(filters.TEXT & filters.ChatType.PRIVATE, self.message_handler.handle_message))
        self.application.add_handler(TelegramMessageHandler(filters.PHOTO, self.message_handler.handle_image))

    def run(self):
        self.register_handlers()
        logger.info("Starting the bot application")
        self.application.run_polling()

if __name__ == '__main__':
    bot = BotApp()
    bot.run()
