import time
from typing import Dict, List, Union
from config import SESSION_EXPIRY, OPENAI_MODEL, SYSTEM_PROMPT, OPENAI_MODELS_REASONING

class SessionManager:
    def __init__(self):
        self.sessions: Dict[int, Dict[str, Union[List[Dict[str, str]], float]]] = {}

    def get_or_create_session(self, user_id: int) -> List[Dict[str, str]]:
        current_time = time.time()
        if user_id not in self.sessions or current_time - self.sessions[user_id]['last_activity'] > SESSION_EXPIRY:
            self.sessions[user_id] = {
                'messages': [{"role": "developer", "content": SYSTEM_PROMPT}],
                'last_activity': current_time
            }
        else:
            self.sessions[user_id]['last_activity'] = current_time
        return self.sessions[user_id]['messages']

    def reset_session(self, user_id: int) -> None:
        self.sessions[user_id] = {
            'messages': [{"role": "developer", "content": SYSTEM_PROMPT}],
            'last_activity': time.time()
        }
