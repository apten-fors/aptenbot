import os

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@korobo4ka_xoroni")
CHANNEL_USER_ID = os.getenv("CHANNEL_USER_ID", "777000")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
FLUX_MODEL = os.getenv("FLUX_MODEL", "flux-pro-1.1")
BFL_API_KEY = os.getenv("BFL_API_KEY")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

MAX_RETRIES = 3
RETRY_DELAY = 1
SESSION_EXPIRY = 3600  # 1 hour
SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", "You are a helpful assistant.")
OPENAI_MODELS = ['gpt-4.5-preview', 'gpt-4o', 'gpt-4o-mini', 'o1', 'o1-pro', 'o3-mini', 'o1-mini']
OPENAI_MODELS_REASONING = ['o1', 'o1-pro', 'o3-mini', 'o1-mini']
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
