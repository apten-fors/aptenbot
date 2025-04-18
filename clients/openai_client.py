from contextlib import asynccontextmanager
from typing import List, Dict, Any
from openai import AsyncOpenAI, OpenAIError, RateLimitError
from utils.logging_config import logger
from config import OPENAI_API_KEY, OPENAI_MODEL, OPENAI_MODELS, DEFAULT_OPENAI_MODEL, TELEGRAM_BOT_TOKEN

class OpenAIClient:
    def __init__(self):
        self.api_key = OPENAI_API_KEY
        self.telegram_bot_token = TELEGRAM_BOT_TOKEN

        if OPENAI_MODEL not in OPENAI_MODELS:
            logger.warning(f"Model {OPENAI_MODEL} specified in environment variables is not valid. Falling back to {DEFAULT_OPENAI_MODEL}")
            self.model = DEFAULT_OPENAI_MODEL
        else:
            self.model = OPENAI_MODEL

    @asynccontextmanager
    async def get_client(self):
        async with AsyncOpenAI(api_key=self.api_key) as client:
            yield client

    async def process_message(self, session: Any, user_message: str) -> str:
        try:
            logger.info("Sending request to OpenAI API")

            response = await session.process_openai_message(user_message, self)

            logger.info(f"Received response from OpenAI API: {response}")
            return response
        except RateLimitError as e:
            logger.error(f"Rate limit exceeded: {e}")
            return "API rate limit reached. Please try again later."
        except OpenAIError as e:
            logger.error(f"OpenAI API Error: {e}")
            return "Sorry, there was a problem with OpenAI. Please try again."
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return "An unexpected error occurred."

    async def process_message_with_image(self, session: Any, user_message: str, image_urls: List[str]) -> str:
        # Format the content as a list with text and images
        message_content = [{"type": "text", "text": user_message}]

        # Add all image URLs to the content
        for url in image_urls:
            # Telegram file paths need to be converted to full URLs that are accessible from outside
            # For Telegram Bot API, we need to add the base URL
            if not url.startswith(('http://', 'https://')):
                full_url = f"https://api.telegram.org/file/bot{self.telegram_bot_token}/{url}"
                logger.debug(f"Converting relative path to full URL: {url} -> {full_url}")
                url = full_url

            message_content.append({
                "type": "image_url",
                "image_url": {
                    "url": url,
                    "detail": "auto"
                }
            })

        # if model name starts with o1 use gpt-4o instead
        model_to_use = self.model
        if model_to_use.startswith("o1"):
            model_to_use = "gpt-4o"

        try:
            logger.info(f"Sending request to OpenAI Vision API with {len(image_urls)} images")
            logger.debug(f"Final image URLs: {[item['image_url']['url'] for item in message_content if 'image_url' in item]}")

            # Get messages from session
            messages = session.data.get('messages', [])

            # Create a new list with only text messages for history
            history_messages = []
            for m in messages:
                if m["role"] == "user" or m["role"] == "assistant" or m["role"] == "developer":
                    if isinstance(m["content"], str):
                        history_messages.append({"role": m["role"], "content": m["content"]})
                    elif m["role"] == "developer":  # System message
                        history_messages.append({"role": "system", "content": m["content"]})

            # Add the current message with images
            history_messages.append({"role": "user", "content": message_content})

            async with self.get_client() as client:
                response = await client.chat.completions.create(
                    model=model_to_use,
                    messages=history_messages
                )
            reply = response.choices[0].message.content.strip()

            # Add messages to history (only storing the text part)
            messages.append({"role": "user", "content": user_message + " [with images]"})
            messages.append({"role": "assistant", "content": reply})

            # Update messages in session data
            session.data['messages'] = messages

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
