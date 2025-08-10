from config import DEFAULT_MODEL_PROVIDER

# Simplified list for selecting only the provider, not specific models
MODELS = [
    {"id": "openai", "name": "OpenAI", "provider": "openai"},
    {"id": "anthropic", "name": "Claude (Anthropic)", "provider": "anthropic"},
    {"id": "gemini", "name": "Gemini (Google)", "provider": "gemini"},
    {"id": "grok", "name": "Grok", "provider": "grok"},
]

# Default model from config
DEFAULT_MODEL = {
    "id": DEFAULT_MODEL_PROVIDER,
    "name": (
        "OpenAI" if DEFAULT_MODEL_PROVIDER == "openai" else
        "Claude (Anthropic)" if DEFAULT_MODEL_PROVIDER == "anthropic" else
        "Gemini (Google)" if DEFAULT_MODEL_PROVIDER == "gemini" else
        "Grok"
    ),
    "provider": DEFAULT_MODEL_PROVIDER
}