import asyncio
from telegram import Update
from telegram.error import TelegramError, BadRequest
from utils.logging_config import logger
from config import MAX_RETRIES, RETRY_DELAY

def escape_markdown_v2(text: str) -> str:
    # First, escape backslashes
    text = text.replace('\\', '\\\\')

    # Then escape all special characters
    escape_chars = '_*[]()~`>#+-=|{}.!'
    return ''.join(f'\\{char}' if char in escape_chars else char for char in text)

async def send_message_with_retry(update: Update, text: str) -> None:
    escaped_text = escape_markdown_v2(text)
    for attempt in range(MAX_RETRIES):
        try:
            await update.message.reply_text(escaped_text, parse_mode='MarkdownV2')
            return
        except TelegramError as e:
            if isinstance(e, BadRequest):
                logger.error(f"Bad request error: {e}")
                return
            if attempt == MAX_RETRIES - 1:
                logger.error(f"Failed to send message after {MAX_RETRIES} attempts: {e}")
                raise
            await asyncio.sleep(RETRY_DELAY)
