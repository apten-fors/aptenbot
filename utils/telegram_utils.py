import re
import asyncio
from telegram import Update
from telegram.error import TelegramError, BadRequest
from utils.logging_config import logger
from config import MAX_RETRIES, RETRY_DELAY

def escape_markdown_v2(text: str) -> str:
    # Define the list of special characters to escape in regular text
    regular_escape_chars = '_*[]()~`>#+-=|{}.!'

    # Function to escape special characters in regular text
    def escape_regular_text(s):
        s = s.replace('\\', '\\\\')  # Escape backslashes
        pattern = f'([{re.escape(regular_escape_chars)}])'
        return re.sub(pattern, r'\\\1', s)

    # Function to escape backslashes and backticks in code
    def escape_code(s):
        s = s.replace('\\', '\\\\').replace('`', '\\`')
        return s

    # Split the text to handle code blocks
    parts = re.split(r'(```.*?```)', text, flags=re.DOTALL)
    for i in range(len(parts)):
        if parts[i].startswith('```') and parts[i].endswith('```'):
            # It's a code block
            parts[i] = escape_code(parts[i])
        else:
            # Handle inline code within regular text
            subparts = re.split(r'(`[^`]*?`)', parts[i])
            for j in range(len(subparts)):
                if subparts[j].startswith('`') and subparts[j].endswith('`'):
                    # It's inline code
                    subparts[j] = escape_code(subparts[j])
                else:
                    # Regular text
                    subparts[j] = escape_regular_text(subparts[j])
            parts[i] = ''.join(subparts)
    return ''.join(parts)


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
