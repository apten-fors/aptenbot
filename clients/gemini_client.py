from contextlib import asynccontextmanager
from typing import Any, List
import asyncio
import os

import google.generativeai as genai
from utils.logging_config import logger
from config import GEMINI_API_KEY, TELEGRAM_BOT_TOKEN


class GeminiClient:
    def __init__(self):
        self.api_key = GEMINI_API_KEY
        self.telegram_bot_token = TELEGRAM_BOT_TOKEN
        genai.configure(api_key=self.api_key)

    @asynccontextmanager
    async def get_client(self):
        # The google.generativeai library does not require a persistent client
        yield genai

    async def process_message(self, session: Any, user_message: str) -> str:
        try:
            logger.info("Sending request to Gemini API")
            response = await session.process_gemini_message(user_message, self)
            logger.info(f"Received response from Gemini API: {response}")
            return response
        except Exception as e:
            logger.error(f"Gemini API Error: {e}")
            return f"Sorry, there was a problem with Gemini. Error: {e}"

    async def process_message_with_image(self, session: Any, user_message: str, image_urls: List[str]) -> str:
        try:
            logger.info("Sending request to Gemini Vision API")
            response = await session.process_gemini_message_with_image(user_message, image_urls, self)
            logger.info(f"Received response from Gemini API: {response}")
            return response
        except Exception as e:
            logger.error(f"Gemini API Error: {e}")
            return f"Sorry, there was a problem with Gemini. Error: {e}"
