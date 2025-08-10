from contextlib import asynccontextmanager
from typing import Any, List

from openai import AsyncOpenAI, OpenAIError, RateLimitError
from utils.logging_config import logger
from config import GROK_API_KEY, GROK_BASE_URL, TELEGRAM_BOT_TOKEN


class GrokClient:
    def __init__(self):
        self.api_key = GROK_API_KEY
        self.base_url = GROK_BASE_URL
        self.telegram_bot_token = TELEGRAM_BOT_TOKEN

    @asynccontextmanager
    async def get_client(self):
        async with AsyncOpenAI(api_key=self.api_key, base_url=self.base_url) as client:
            yield client

    async def process_message(self, session: Any, user_message: str) -> str:
        try:
            logger.info("Sending request to Grok API")
            response = await session.process_grok_message(user_message, self)
            logger.info(f"Received response from Grok API: {response}")
            return response
        except RateLimitError as e:
            logger.error(f"Rate limit exceeded: {e}")
            return "API rate limit reached. Please try again later."
        except OpenAIError as e:
            logger.error(f"Grok API Error: {e}")
            return "Sorry, there was a problem with Grok. Please try again."
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return "An unexpected error occurred."

    async def process_message_with_image(self, session: Any, user_message: str, image_urls: List[str]) -> str:
        # Use the same approach as OpenAI since Grok API is OpenAI-compatible
        return await session.process_grok_message_with_image(user_message, image_urls, self)
