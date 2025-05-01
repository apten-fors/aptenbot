from contextlib import asynccontextmanager
from typing import List, Dict, Any
from openai import AsyncOpenAI, OpenAIError, RateLimitError
from utils.logging_config import logger
from config import OPENAI_API_KEY, TELEGRAM_BOT_TOKEN

class OpenAIClient:
    def __init__(self):
        self.api_key = OPENAI_API_KEY
        self.telegram_bot_token = TELEGRAM_BOT_TOKEN

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

        # Get model from session
        model_to_use = session.get_model()

        # if model name starts with o1 use gpt-4o instead for vision
        if model_to_use.startswith("o1"):
            model_to_use = "gpt-4o"

        try:
            logger.info(f"Sending request to OpenAI Vision API with {len(image_urls)} images using model {model_to_use}")
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

    async def generate_image(self, prompt: str):
        """Generate an image using OpenAI's DALL-E model.

        Args:
            prompt (str): The text prompt for image generation

        Returns:
            bytes: The generated image as bytes
        """
        logger.info(f"Generating image with OpenAI: {prompt}")
        try:
            async with self.get_client() as client:
                response = await client.images.generate(
                    model="gpt-image-1",
                    prompt=prompt,
                    size="1024x1024",
                    quality="medium",
                    n=1
                )
            # Return the base64 encoded image
            import base64
            return base64.b64decode(response.data[0].b64_json)
        except Exception as e:
            logger.error(f"Error generating image with OpenAI: {e}")
            raise
