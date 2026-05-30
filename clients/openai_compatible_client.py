from contextlib import asynccontextmanager
from typing import Any, List

from openai import AsyncOpenAI, OpenAIError, RateLimitError

from utils.logging_config import logger
from config import TELEGRAM_BOT_TOKEN


class OpenAICompatibleClient:
    """Client for any OpenAI-compatible ``/v1/chat/completions`` endpoint.

    Used for Grok and for self-hosted providers (kimi, glm, deepseek, ...). Each
    instance is bound to a single provider's ``api_key`` + ``base_url``; the
    actual request logic lives in
    ``Session.process_openai_chat_message`` so history handling stays shared.
    """

    def __init__(
        self,
        api_key,
        base_url,
        provider_name: str = "OpenAI-compatible",
        supports_images: bool = False,
        telegram_bot_token: str = TELEGRAM_BOT_TOKEN,
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.provider_name = provider_name
        self.supports_images = supports_images
        self.telegram_bot_token = telegram_bot_token

    @asynccontextmanager
    async def get_client(self):
        async with AsyncOpenAI(api_key=self.api_key, base_url=self.base_url) as client:
            yield client

    async def process_message(self, session: Any, user_message: str) -> str:
        try:
            logger.info("Sending request to %s API", self.provider_name)
            response = await session.process_openai_chat_message(user_message, self)
            logger.info("Received response from %s API", self.provider_name)
            return response
        except RateLimitError as e:
            logger.error("Rate limit exceeded (%s): %s", self.provider_name, e)
            return "API rate limit reached. Please try again later."
        except OpenAIError as e:
            logger.error("%s API Error: %s", self.provider_name, e)
            return f"Sorry, there was a problem with {self.provider_name}. Please try again."
        except Exception as e:
            logger.error("Unexpected error (%s): %s", self.provider_name, e)
            return "An unexpected error occurred."

    async def process_message_with_image(self, session: Any, user_message: str, image_urls: List[str]) -> str:
        # OpenAI-compatible vision request; only reached for image-capable providers.
        return await session.process_openai_chat_message_with_image(user_message, image_urls, self)
