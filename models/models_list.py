from config import DEFAULT_MODEL_PROVIDER

# Simplified list for selecting only the provider, not specific models
MODELS = [
    {"id": "openai", "name": "OpenAI", "provider": "openai"},
    {"id": "anthropic", "name": "Claude (Anthropic)", "provider": "anthropic"},
]

# Default model from config
DEFAULT_MODEL = {
    "id": DEFAULT_MODEL_PROVIDER,
    "name": "OpenAI" if DEFAULT_MODEL_PROVIDER == "openai" else "Claude (Anthropic)",
    "provider": DEFAULT_MODEL_PROVIDER
}