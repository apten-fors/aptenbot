from contextlib import asynccontextmanager
from typing import List, Dict
import anthropic
from utils.logging_config import logger
from config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL, ANTHROPIC_MODELS, DEFAULT_ANTHROPIC_MODEL

class ClaudeClient:
    def __init__(self):
        self.api_key = ANTHROPIC_API_KEY

        if ANTHROPIC_MODEL not in ANTHROPIC_MODELS:
            logger.warning(f"Model {ANTHROPIC_MODEL} specified in environment variables is not valid. Falling back to {DEFAULT_ANTHROPIC_MODEL}")
            self.model = DEFAULT_ANTHROPIC_MODEL
        else:
            self.model = ANTHROPIC_MODEL

    @asynccontextmanager
    async def get_client(self):
        client = anthropic.AsyncAnthropic(api_key=self.api_key)
        try:
            yield client
        finally:
            pass

    async def process_message(self, session: List[Dict[str, str]], user_message: str) -> str:
        session.append({"role": "user", "content": user_message})

        try:
            logger.info("Sending request to Anthropic API")

            # Convert session format to match Anthropic's expected format
            messages = []
            for msg in session:
                if msg["role"] == "developer":
                    # Handle system prompt
                    continue
                elif msg["role"] == "assistant":
                    messages.append({"role": "assistant", "content": msg["content"]})
                else:
                    messages.append({"role": "user", "content": msg["content"]})

            async with self.get_client() as client:
                response = await client.messages.create(
                    model=self.model,
                    max_tokens=4000,
                    messages=messages
                )

            reply = response.content[0].text
            session.append({"role": "assistant", "content": reply})
            logger.info(f"Received response from Anthropic API: {reply}")
            return reply
        except Exception as e:
            logger.error(f"Anthropic API Error: {e}")
            return f"Sorry, there was a problem with Claude. Error: {e}"

    async def process_message_with_image(self, session: List[Dict[str, str]], user_message: str, image_urls: List[str]) -> str:
        # Format the content as a list for Anthropic API
        message_blocks = []

        # Add all image URLs to the content
        for url in image_urls:
            message_blocks.append({
                "type": "image",
                "source": {
                    "type": "url",
                    "url": url
                }
            })

        # Add the text content
        message_blocks.append({"type": "text", "text": user_message})

        # Convert the session to Anthropic's format
        messages = []
        for msg in session:
            if msg["role"] == "developer":
                # Handle system prompt
                continue
            elif msg["role"] == "assistant":
                messages.append({"role": "assistant", "content": msg["content"]})
            else:
                messages.append({"role": "user", "content": msg["content"]})

        # Add the current message with images
        messages.append({"role": "user", "content": message_blocks})

        try:
            logger.info(f"Sending request to Anthropic API with {len(image_urls)} images")
            async with self.get_client() as client:
                response = await client.messages.create(
                    model=self.model,
                    max_tokens=4000,
                    messages=messages
                )

            reply = response.content[0].text
            session.append({"role": "assistant", "content": reply})
            logger.info(f"Received response from Anthropic API: {reply}")
            return reply
        except Exception as e:
            logger.error(f"Anthropic API Error: {e}")
            return f"Sorry, there was a problem with Claude. Error: {e}"
