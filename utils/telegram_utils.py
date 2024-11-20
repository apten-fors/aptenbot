import asyncio
from telegram import Update
from telegram.error import TelegramError, BadRequest
from utils.logging_config import logger
from config import MAX_RETRIES, RETRY_DELAY

async def send_message_with_retry(update: Update, text: str) -> None:
    for attempt in range(MAX_RETRIES):
        try:
            await update.message.reply_text(text, parse_mode='MarkdownV2')
            return
        except TelegramError as e:
            if isinstance(e, BadRequest):
                logger.error(f"Bad request error: {e}")
                return
            if attempt == MAX_RETRIES - 1:
                logger.error(f"Failed to send message after {MAX_RETRIES} attempts: {e}")
                raise
            await asyncio.sleep(RETRY_DELAY)
