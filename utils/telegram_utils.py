import asyncio
from telegram import Update
from telegram.error import TelegramError, BadRequest
from utils.logging_config import logger
from config import MAX_RETRIES, RETRY_DELAY
from pathlib import Path

def escape_markdown_v2(text: str) -> str:
    # First handle triple backticks (code blocks)
    parts = text.split("```")

    for i in range(len(parts)):
        if i % 2 == 0:  # Regular text parts
            # Handle single backticks in regular text
            subparts = parts[i].split("`")
            for j in range(len(subparts)):
                if j % 2 == 0:  # Non-code text
                    # Escape backslashes first
                    subparts[j] = subparts[j].replace('\\', '\\\\')
                    # Escape special characters except markdown formatting
                    escape_chars = '[]()~`>#+=|{}.!-'
                    subparts[j] = ''.join(f'\\{char}' if char in escape_chars else char
                                        for char in subparts[j])
                else:  # Inline code
                    # For inline code, escape only minimal characters
                    subparts[j] = subparts[j].replace('\\', '\\\\')
                    subparts[j] = subparts[j].replace('`', '\\`')

            parts[i] = '`'.join(subparts)
        else:  # Code blocks
            # For code blocks, escape only minimal characters
            parts[i] = parts[i].replace('\\', '\\\\')
            parts[i] = parts[i].replace('`', '\\`')

    # Rejoin everything
    return '```'.join(parts)

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

async def send_pic_with_retry(update: Update, pic: str) -> None:
    for attempt in range(MAX_RETRIES):
        try:
            await update.message.reply_photo(pic)
            return
        except TelegramError as e:
            if isinstance(e, BadRequest):
                logger.error(f"Bad request error: {e}")
                return
            if attempt == MAX_RETRIES - 1:
                logger.error(f"Failed to send message after {MAX_RETRIES} attempts: {e}")
                raise
            await asyncio.sleep(RETRY_DELAY)

async def send_video_with_retry(update: Update, video: str) -> None:
    for attempt in range(MAX_RETRIES):
        try:
            path = Path(video)
            if not path.exists():
                logger.error(f"File not found: {video}")
                return
            await update.message.reply_video(path)
            return
        except TelegramError as e:
            if isinstance(e, BadRequest):
                logger.error(f"Bad request error: {e}")
                return
            if attempt == MAX_RETRIES - 1:
                logger.error(f"Failed to send message after {MAX_RETRIES} attempts: {e}")
                raise
            await asyncio.sleep(RETRY_DELAY)
