from config import DEFAULT_MODEL_PROVIDER

# Упрощенный список для выбора только провайдера, а не конкретных моделей
MODELS = [
    {"id": "openai", "name": "OpenAI", "provider": "openai"},
    {"id": "anthropic", "name": "Claude (Anthropic)", "provider": "anthropic"},
]

# Дефолтный провайдер из конфига
DEFAULT_MODEL = {
    "id": DEFAULT_MODEL_PROVIDER,
    "name": "OpenAI" if DEFAULT_MODEL_PROVIDER == "openai" else "Claude (Anthropic)",
    "provider": DEFAULT_MODEL_PROVIDER
}