import os

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@korobo4ka_xoroni")
CHANNEL_USER_ID = os.getenv("CHANNEL_USER_ID", "777000")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

MAX_RETRIES = 3
RETRY_DELAY = 1
SESSION_EXPIRY = 3600  # 1 hour
