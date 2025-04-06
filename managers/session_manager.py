import time
from typing import Dict, List, Union
from config import SESSION_EXPIRY, OPENAI_MODEL, SYSTEM_PROMPT, OPENAI_MODELS_REASONING, DEFAULT_MODEL_PROVIDER

class SessionManager:
    def __init__(self):
        self.sessions: Dict[int, Dict[str, Union[List[Dict[str, str]], float, str]]] = {}

    def get_or_create_session(self, user_id: int) -> List[Dict[str, str]]:
        current_time = time.time()
        if user_id not in self.sessions or current_time - self.sessions[user_id]['last_activity'] > SESSION_EXPIRY:
            self.sessions[user_id] = {
                'messages': [{"role": "developer", "content": SYSTEM_PROMPT}],
                'last_activity': current_time,
                'model_provider': DEFAULT_MODEL_PROVIDER
            }
        else:
            self.sessions[user_id]['last_activity'] = current_time
        return self.sessions[user_id]['messages']

    def reset_session(self, user_id: int) -> None:
        model_provider = self.sessions.get(user_id, {}).get('model_provider', DEFAULT_MODEL_PROVIDER)
        self.sessions[user_id] = {
            'messages': [{"role": "developer", "content": SYSTEM_PROMPT}],
            'last_activity': time.time(),
            'model_provider': model_provider
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
        else:
            self.sessions[user_id] = {
                'messages': [{"role": "developer", "content": SYSTEM_PROMPT}],
                'last_activity': time.time(),
                'model_provider': provider
            }
