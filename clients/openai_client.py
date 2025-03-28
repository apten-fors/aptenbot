from contextlib import asynccontextmanager
from typing import List, Dict
from openai import AsyncOpenAI, OpenAIError, RateLimitError
from utils.logging_config import logger
from config import OPENAI_API_KEY, OPENAI_MODEL, OPENAI_MODELS, DEFAULT_OPENAI_MODEL

class OpenAIClient:
    def __init__(self):
        self.api_key = OPENAI_API_KEY

        if OPENAI_MODEL not in OPENAI_MODELS:
            logger.warning(f"Model {OPENAI_MODEL} specified in environment variables is not valid. Falling back to {DEFAULT_OPENAI_MODEL}")
            self.model = DEFAULT_OPENAI_MODEL
        else:
            self.model = OPENAI_MODEL

    @asynccontextmanager
    async def get_client(self):
        async with AsyncOpenAI(api_key=self.api_key) as client:
            yield client

    async def process_message(self, session: List[Dict[str, str]], user_message: str) -> str:
        session.append({"role": "user", "content": user_message})

        try:
            logger.info("Sending request to OpenAI API")
            async with self.get_client() as client:
                response = await client.chat.completions.create(
                    model=self.model,
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

    async def process_message_with_image(self, session: List[Dict[str, str]], user_message: str, image_urls: List[str]) -> str:
        # Format the content as a list with text and images
        message_content = [{"type": "text", "text": user_message}]

        # Add all image URLs to the content
        for url in image_urls:
            message_content.append({
                "type": "image_url",
                "image_url": {
                    "url": url
                }
            })

        # if model name starts with o1 use gpt-4o instead
        if self.model.startswith("o1"):
            self.model = "gpt-4o"

        session.append({"role": "user", "content": message_content})

        try:
            logger.info(f"Sending request to OpenAI Vision API with {len(image_urls)} images")
            async with self.get_client() as client:
                response = await client.chat.completions.create(
                    model=self.model,
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
