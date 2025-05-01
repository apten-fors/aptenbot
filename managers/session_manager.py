import time
from typing import Dict, List, Union, Optional
from config import SESSION_EXPIRY, OPENAI_MODEL, ANTHROPIC_MODEL, SYSTEM_PROMPT, DEFAULT_MODEL_PROVIDER
from models.models_list import MODELS, DEFAULT_MODEL
from utils.logging_config import logger

class SessionManager:
    def __init__(self):
        self.sessions: Dict[int, Dict[str, Union[List[Dict[str, str]], float, str]]] = {}

    def get_or_create_session(self, user_id: int) -> 'Session':
        current_time = time.time()
        if user_id not in self.sessions or current_time - self.sessions[user_id]['last_activity'] > SESSION_EXPIRY:
            self.sessions[user_id] = {
                'messages': [{"role": "developer", "content": SYSTEM_PROMPT}],
                'last_activity': current_time,
                'model_provider': DEFAULT_MODEL_PROVIDER,
                'model': OPENAI_MODEL if DEFAULT_MODEL_PROVIDER == 'openai' else ANTHROPIC_MODEL,
                'image_model': 'openai',  # Default image model
                'state': None
            }
        else:
            self.sessions[user_id]['last_activity'] = current_time

        return Session(self.sessions[user_id])

    def create_new_session(self, user_id: int) -> None:
        # Preserve model preferences when creating a new session
        model_provider = self.sessions.get(user_id, {}).get('model_provider', DEFAULT_MODEL_PROVIDER)
        model = self.sessions.get(user_id, {}).get('model',
                                                  OPENAI_MODEL if model_provider == 'openai' else ANTHROPIC_MODEL)
        image_model = self.sessions.get(user_id, {}).get('image_model', 'openai')

        self.sessions[user_id] = {
            'messages': [{"role": "developer", "content": SYSTEM_PROMPT}],
            'last_activity': time.time(),
            'model_provider': model_provider,
            'model': model,
            'image_model': image_model,
            'state': None
        }

    def get_model_provider(self, user_id: int) -> str:
        """Get the current model provider for a user session"""
        if user_id not in self.sessions:
            return DEFAULT_MODEL_PROVIDER
        return self.sessions[user_id].get('model_provider', DEFAULT_MODEL_PROVIDER)

    def set_model_provider(self, user_id: int, provider: str) -> None:
        """Set the model provider for a user session"""
        if user_id in self.sessions:
            self.sessions[user_id]['model_provider'] = provider
            # Set default model for the provider
            if provider == 'openai':
                self.sessions[user_id]['model'] = OPENAI_MODEL
            else:  # anthropic
                self.sessions[user_id]['model'] = ANTHROPIC_MODEL
        else:
            self.sessions[user_id] = {
                'messages': [{"role": "developer", "content": SYSTEM_PROMPT}],
                'last_activity': time.time(),
                'model_provider': provider,
                'model': OPENAI_MODEL if provider == 'openai' else ANTHROPIC_MODEL,
                'image_model': 'openai',
                'state': None
            }

    def get_model(self, user_id: int) -> dict:
        """Get the current provider model for a user session"""
        if user_id not in self.sessions:
            return DEFAULT_MODEL

        provider = self.sessions[user_id].get('model_provider', DEFAULT_MODEL_PROVIDER)

        # Find the model in MODELS list by provider
        for model in MODELS:
            if model['provider'] == provider:
                return model

        # If model not found, return default
        return DEFAULT_MODEL

class Session:
    def __init__(self, session_data):
        self.data = session_data

    def update_state(self, state: str) -> None:
        """Update the state of the session"""
        self.data['state'] = state

    def get_state(self) -> Optional[str]:
        """Get the current state of the session"""
        return self.data.get('state')

    def clear_state(self) -> None:
        """Clear the state of the session"""
        self.data['state'] = None

    def update_model(self, provider_id: str) -> None:
        """Update the provider for this session"""
        logger.info(f"Updating model provider to: {provider_id}")
        self.data['model_provider'] = provider_id
        # Set default model for the provider
        if provider_id == 'openai':
            self.data['model'] = OPENAI_MODEL
        else:  # anthropic
            self.data['model'] = ANTHROPIC_MODEL

    def update_specific_model(self, model_id: str) -> None:
        """Update the specific model for this session"""
        logger.info(f"Updating specific model to: {model_id}")
        self.data['model'] = model_id

    def get_provider(self) -> str:
        """Get the provider for the current model"""
        provider = self.data.get('model_provider', DEFAULT_MODEL_PROVIDER)
        logger.info(f"Current provider is: {provider}")
        return provider

    def get_model(self) -> str:
        """Get the current specific model"""
        provider = self.get_provider()
        default_model = OPENAI_MODEL if provider == 'openai' else ANTHROPIC_MODEL
        return self.data.get('model', default_model)

    def update_image_model(self, model_id: str) -> None:
        """Update the image generation model for this session"""
        self.data['image_model'] = model_id

    def get_image_model(self) -> str:
        """Get the current image generation model"""
        return self.data.get('image_model', 'openai')

    async def process_openai_message(self, message: str, openai_client):
        """Process a message using OpenAI"""
        messages = self.data.get('messages', [])

        # Add user message
        messages.append({"role": "user", "content": message})

        # Use model from session or client config
        model_id = self.get_model()

        try:
            # Call OpenAI API using the get_client method
            async with openai_client.get_client() as client:
                response = await client.chat.completions.create(
                    model=model_id,
                    messages=[
                        {"role": m["role"], "content": m["content"]}
                        for m in messages
                    ]
                )

            # Get assistant's response
            assistant_message = response.choices[0].message.content

            # Add assistant message to history
            messages.append({"role": "assistant", "content": assistant_message})

            # Update messages in session data
            self.data['messages'] = messages

            return assistant_message

        except Exception as e:
            return f"Error processing message with OpenAI: {str(e)}"

    async def process_claude_message(self, message: str, claude_client):
        """Process a message using Claude"""
        messages = self.data.get('messages', [])

        # Add user message
        messages.append({"role": "user", "content": message})

        # Use model from session or client config
        model_id = self.get_model()

        try:
            # Convert messages to Claude format
            claude_messages = []
            for m in messages:
                role = "user" if m["role"] == "user" else "assistant"
                if m["role"] == "developer":
                    # Handle system message
                    continue  # Claude has a different way of handling system messages
                claude_messages.append({"role": role, "content": m["content"]})

            # Call Claude API
            async with claude_client.get_client() as client:
                response = await client.messages.create(
                    model=model_id,
                    max_tokens=4096,
                    messages=claude_messages,
                    system=SYSTEM_PROMPT
                )

            # Get assistant's response
            assistant_message = response.content[0].text

            # Add assistant message to history
            messages.append({"role": "assistant", "content": assistant_message})

            # Update messages in session data
            self.data['messages'] = messages

            return assistant_message

        except Exception as e:
            return f"Error processing message with Claude: {str(e)}"
