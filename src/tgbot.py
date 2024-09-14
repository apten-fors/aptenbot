import os
import logging
import json
from pythonjsonlogger import jsonlogger
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
import openai
from openai import OpenAI
client = OpenAI()

# Custom JSON encoder to handle Unicode characters
class UnicodeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, str):
            return obj.encode('utf-8').decode('utf-8')
        return super().default(obj)

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter(json_ensure_ascii=False, json_encoder=UnicodeEncoder)
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
# CHANNEL_ID = os.getenv("CHANNEL_ID")  # Add your channel ID here
CHANNEL_ID = "@korobo4ka_xoroni"

openai.api_key = OPENAI_API_KEY

async def is_subscriber(user_id, bot):
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        logger.info(f"Member status: {member.status}")
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.error(f"Error checking subscription status: {e}")
        return False

async def ask(update: Update, context):
    user_id = update.message.from_user.id
    if not await is_subscriber(user_id, context.bot):
        await update.message.reply_text("To use this bot, you need to be a subscriber of @korobo4ka_xoroni channel.")
        return

    user_message = ' '.join(context.args)
    logger.info(f"Received message from user: {user_message}")

    try:
        logger.info("Sending request to OpenAI API")
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": user_message}
            ]
        )
        reply = response.choices[0].message.content.strip()
        logger.info(f"Received response from OpenAI API: {reply}")
        await update.message.reply_text(reply)
    except Exception as e:
        logger.error(f"Error while communicating with OpenAI API: {e}")
        await update.message.reply_text("Sorry, there was an error processing your request.")

async def start(update: Update, context):
    await update.message.reply_text('Hi, I am a bot that uses ChatGPT. Use /ask followed by your question to get a response.')

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ask", ask))

    logger.info("Starting the bot application")
    app.run_polling()
