from contextlib import asynccontextmanager
from typing import List, Dict, Any
import anthropic
from utils.logging_config import logger
from config import ANTHROPIC_API_KEY, TELEGRAM_BOT_TOKEN

class ClaudeClient:
    def __init__(self):
        self.api_key = ANTHROPIC_API_KEY
        self.telegram_bot_token = TELEGRAM_BOT_TOKEN

    @asynccontextmanager
    async def get_client(self):
        client = anthropic.AsyncAnthropic(api_key=self.api_key)
        try:
            yield client
        finally:
            pass

    async def process_message(self, session: Any, user_message: str) -> str:
        # Use the updated Session class methods instead of direct list manipulation
        try:
            logger.info("Sending request to Anthropic API")

            # Use the process_claude_message method from Session class
            response = await session.process_claude_message(user_message, self)

            logger.info(f"Received response from Anthropic API: {response}")
            return response
        except Exception as e:
            logger.error(f"Anthropic API Error: {e}")
            return f"Sorry, there was a problem with Claude. Error: {e}"

    async def process_message_with_image(self, session: Any, user_message: str, image_urls: List[str]) -> str:
        # Format the content as a list for Anthropic API
        message_blocks = []

        # Add all image URLs to the content
        for url in image_urls:
            # Преобразуем относительные пути в полные URL для Telegram API
            if not url.startswith(('http://', 'https://')):
                full_url = f"https://api.telegram.org/file/bot{self.telegram_bot_token}/{url}"
                logger.debug(f"Converting relative path to full URL: {url} -> {full_url}")
                url = full_url

            message_blocks.append({
                "type": "image",
                "source": {
                    "type": "url",
                    "url": url
                }
            })

        # Add the text content
        message_blocks.append({"type": "text", "text": user_message})

        # Get messages from session
        messages = session.data.get('messages', [])

        # Convert the session to Anthropic's format
        claude_messages = []
        for msg in messages:
            if msg["role"] == "developer":
                # Handle system prompt
                continue
            elif msg["role"] == "assistant":
                claude_messages.append({"role": "assistant", "content": msg["content"]})
            else:
                claude_messages.append({"role": "user", "content": msg["content"]})

        # Add the current message with images
        claude_messages.append({"role": "user", "content": message_blocks})

        try:
            logger.info(f"Sending request to Anthropic API with {len(image_urls)} images")
            logger.debug(f"Final image URLs: {[block['source']['url'] for block in message_blocks if block['type'] == 'image']}")

            # Get model from session
            model_to_use = session.get_model()

            async with self.get_client() as client:
                response = await client.messages.create(
                    model=model_to_use,
                    max_tokens=4096,
                    messages=claude_messages,
                    system=self.system_prompt if hasattr(self, 'system_prompt') else None
                )

            reply = response.content[0].text

            # Add the message to history
            messages.append({"role": "user", "content": user_message + " [with images]"})
            messages.append({"role": "assistant", "content": reply})

            # Update messages in session
            session.data['messages'] = messages

            logger.info(f"Received response from Anthropic API: {reply}")
            return reply
        except Exception as e:
            logger.error(f"Anthropic API Error: {e}")
            return f"Sorry, there was a problem with Claude. Error: {e}"
