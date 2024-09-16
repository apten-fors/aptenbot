import os
import logging
import logging.config
import json
import time
import asyncio
from contextlib import asynccontextmanager
from typing import Dict, List, Union

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import TelegramError, BadRequest
from openai import AsyncOpenAI
from openai import OpenAIError, RateLimitError
from pythonjsonlogger import jsonlogger
from logging_config import logger


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@korobo4ka_xoroni")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

MAX_RETRIES = 3
RETRY_DELAY = 1
SESSION_EXPIRY = 3600  # 1 hour

# Configure logging
class UnicodeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, str):
            return obj.encode('utf-8').decode('utf-8')
        return super().default(obj)

class UnicodeJsonFormatter(jsonlogger.JsonFormatter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, json_ensure_ascii=False, json_encoder=UnicodeEncoder, **kwargs)


# Storage for user sessions
sessions: Dict[int, Dict[str, Union[List[Dict[str, str]], float]]] = {}

@asynccontextmanager
async def get_openai_client():
    async with AsyncOpenAI(api_key=OPENAI_API_KEY) as client:
        yield client

def get_or_create_session(user_id: int) -> List[Dict[str, str]]:
    current_time = time.time()
    if user_id not in sessions or current_time - sessions[user_id]['last_activity'] > SESSION_EXPIRY:
        sessions[user_id] = {
            'messages': [{"role": "system", "content": "You are a helpful assistant."}],
            'last_activity': current_time
        }
    else:
        sessions[user_id]['last_activity'] = current_time
    return sessions[user_id]['messages']

async def send_message_with_retry(update: Update, text: str) -> None:
    for attempt in range(MAX_RETRIES):
        try:
            await update.message.reply_text(text)
            return
        except TelegramError as e:
            if isinstance(e, BadRequest):
                logger.error(f"Bad request error: {e}")
                return
            if attempt == MAX_RETRIES - 1:
                logger.error(f"Failed to send message after {MAX_RETRIES} attempts: {e}")
                raise
            await asyncio.sleep(RETRY_DELAY)

async def is_subscriber(user_id: int, bot) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        logger.info(f"Member status: {member.status}")
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.error(f"Error checking subscription status: {e}")
        return False

async def process_message(user_message: str, session: List[Dict[str, str]]) -> str:
    session.append({"role": "user", "content": user_message})

    try:
        logger.info("Sending request to OpenAI API")
        async with get_openai_client() as client:
            response = await client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=session
            )
        reply = response.choices[0].message.content.strip()
        session.append({"role": "assistant", "content": reply})
        logger.info(f"Received response from OpenAI API: {reply}")
        return reply
    except RateLimitError as e:
        logger.error(f"Rate limit exceeded: {e}")
        return "API rate limit reached. Please try again later."
    except OpenAIError as e:
        logger.error(f"OpenAI API Error: {e}")
        return "Sorry, there was a problem with OpenAI. Please try again."
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return "An unexpected error occurred."

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    chat_type = update.message.chat.type

    if chat_type in ['group', 'supergroup']:
        await send_message_with_retry(update, "Please use /ask command to interact with the bot in this group.")
        return

    if not await is_subscriber(user_id, update.get_bot()):
        await send_message_with_retry(update, "To use this bot, you need to be a subscriber of @korobo4ka_xoroni channel.")
        return

    user_message = update.message.text
    logger.info(f"Received message from user: {user_message}")

    session = get_or_create_session(user_id)
    reply = await process_message(user_message, session)
    await send_message_with_retry(update, reply)

async def handle_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    chat_type = update.message.chat.type

    if chat_type in ['group', 'supergroup']:
        if not await is_subscriber(user_id, update.get_bot()):
            await send_message_with_retry(update, "To use this bot, you need to be a subscriber of @korobo4ka_xoroni channel.")
            return

    # Something weird is going on here
    if not update.message.reply_to_message:
        await send_message_with_retry(update, "Please reply to a bot's message to continue the conversation.")
        return

    # Check if the reply is to a bot's message
    if update.message.reply_to_message.from_user.id != context.bot.id:
        return

    user_message = update.message.text
    logger.info(f"Received reply from user: {user_message}")

    session = get_or_create_session(user_id)
    reply = await process_message(user_message, session)
    await send_message_with_retry(update, reply)

async def ask(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id

    if not await is_subscriber(user_id, context.bot):
        await send_message_with_retry(update, "To use this bot, you need to be a subscriber of @korobo4ka_xoroni channel.")
        return

    if not context.args:
        await send_message_with_retry(update, "Usage: /ask <your question>")
        return

    user_message = ' '.join(context.args)
    logger.info(f"Received message from user: {user_message}")

    session = get_or_create_session(user_id)
    reply = await process_message(user_message, session)
    await send_message_with_retry(update, reply)

async def reset_session(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    logger.info(f"Resetting session for user: {user_id}")

    if user_id in sessions:
        logger.info(f"User {user_id} has an active session. Resetting...")
        sessions[user_id] = {
            'messages': [{"role": "system", "content": "You are a helpful assistant."}],
            'last_activity': time.time()
        }
        await send_message_with_retry(update, "Session reset. Let's start fresh!")
    else:
        logger.info(f"User {user_id} does not have an active session.")
        await send_message_with_retry(update, "You don't have an active session to reset.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_message_with_retry(update, 'Hi, I am a bot that uses ChatGPT. Use /ask followed by your question to get a response in groups. For private chats, just send your question directly.')

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Register command handlers first
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ask", ask))
    app.add_handler(CommandHandler("reset", reset_session))

    # Register message handlers
    app.add_handler(MessageHandler(filters.TEXT & filters.REPLY, handle_reply))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle_message))

    logger.info("Starting the bot application")
    app.run_polling()
