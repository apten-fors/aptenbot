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

    # Function to escape special characters in code blocks and inline code
    def escape_code(s):
        # Escape backslashes, backticks, and '#' characters
        s = s.replace('\\', '\\\\').replace('`', '\\`').replace('#', '\\#')
        return s

    # Split the text to handle code blocks (including language identifiers)
    parts = re.split(r'(```.*?```)', text, flags=re.DOTALL)
    for i in range(len(parts)):
        part = parts[i]
        if part.startswith('```') and part.endswith('```'):
            # It's a code block
            parts[i] = escape_code(part)
        else:
            # Handle inline code within regular text
            subparts = re.split(r'(`[^`]*?`)', part)
            for j in range(len(subparts)):
                subpart = subparts[j]
                if subpart.startswith('`') and subpart.endswith('`'):
                    # It's inline code
                    subparts[j] = escape_code(subpart)
                else:
                    # Regular text
                    subparts[j] = escape_regular_text(subpart)
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
