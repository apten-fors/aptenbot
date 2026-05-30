# Telegram AI Bot

A Telegram bot that integrates with OpenAI, Claude, Google Gemini and Grok AI models to provide intelligent responses, supporting both text and image processing.

## Features

- Text conversations with OpenAI, Claude, Gemini and Grok models
- Self-hosted / OpenAI-compatible providers via `CUSTOM_PROVIDERS` (config-only, no code changes)
- Image processing and analysis (multimodal)
- Image generation with OpenAI or Flux (`/img`)
- Configurable reasoning effort for OpenAI reasoning models
- Media group handling
- Instagram video downloading
- Automatic Instagram login with shared Redis session
- Group chat support with mention / `/ask` handling
- Guest Mode: allow chosen users to @mention the bot from arbitrary chats (Telegram Bot API 10.0)
- Per-user session management with model/provider switching

## Structure

The project uses aiogram 3.x with a clean architecture:

```
project/
├── bot.py                            # Main entry point
├── config.py                         # Configuration (env vars, model lists)
├── providers.py                      # Provider registry (single source of truth for chat providers)
├── clients/                          # API clients
│   ├── openai_client.py              # OpenAI Responses API
│   ├── claude_client.py              # Claude Messages API
│   ├── gemini_client.py              # Google Gemini
│   ├── openai_compatible_client.py   # Grok + self-hosted OpenAI-compatible providers
│   ├── flux_client.py                # Flux image generation (Black Forest Labs)
│   └── instagrapi_client.py          # Instagram content downloader
├── services/
│   └── answer_service.py             # Registry-driven provider/client dispatch
├── routers/                          # Message routers
│   ├── commands.py                   # Command handlers
│   ├── messages.py                   # Text message handlers
│   ├── media.py                      # Media file handlers
│   └── guest.py                      # Guest Mode handler (@mention from arbitrary chats)
├── middlewares/                      # Middleware components
│   ├── dependencies.py               # Dependency injection into handlers
│   ├── subscription.py               # Channel subscription checker
│   └── logging.py                    # Message logging
├── managers/                         # Business logic managers
│   ├── session_manager.py            # User session management
│   └── subscription_manager.py       # Subscription verification
├── models/
│   └── models_list.py                # Model list helpers
├── states/                           # FSM states
│   └── conversation.py               # Conversation states
└── utils/                            # Utility functions
    ├── logging_config.py             # Logging configuration
    ├── telegram_utils.py             # Telegram-specific utilities
    ├── redis_client.py               # Redis Sentinel connector
    ├── session_store.py              # Redis-based Instagram session cache
    ├── guest.py                      # Guest Mode helpers
    ├── rate_limiter.py               # Per-user rate limiting
    ├── metrics.py                    # Metrics
    └── settings.py                   # Settings helpers
```

## Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/tgbot.git
cd tgbot
```

2. Install [uv](https://docs.astral.sh/uv/) (if you don't have it):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

3. Install dependencies (uv reads `.python-version` → Python 3.14 and creates `.venv` automatically):
```bash
uv sync
```

4. Set up your environment variables:
```bash
# Set Telegram Bot token (required)
export TG_BOT_TOKEN='your_telegram_bot_token'

# Set API keys for AI providers (at least one required)
export OPENAI_API_KEY='your_openai_api_key'
export ANTHROPIC_API_KEY='your_anthropic_api_key'
export GEMINI_API_KEY='your_gemini_api_key'
export GROK_API_KEY='your_grok_api_key'

# Optional: Set other configuration variables
export OPENAI_MODEL='gpt-4o-mini'
export ANTHROPIC_MODEL='claude-3-5-haiku-20241022'
export DEFAULT_MODEL_PROVIDER='openai'
export BFL_API_KEY='your_bfl_api_key'  # For Flux image generation
export CHANNEL_ID='@channel1,@channel2'  # Comma-separated list for subscription checks
export LOG_LEVEL='INFO'
```

### Self-hosted / OpenAI-compatible providers (optional)

Add any number of OpenAI-compatible (chat/completions) providers via the
`CUSTOM_PROVIDERS` env var — no code changes required. Each provider is
text-only by default and only appears once its API key + base URL + models
are all set.

```bash
export CUSTOM_PROVIDERS='kimi,glm,deepseek'   # comma-separated prefixes
export KIMI_API_KEY='...'
export KIMI_BASE_URL='https://kimi.myinfra.example/v1'
export KIMI_MODELS='kimi26'                   # comma-separated model ids
export KIMI_NAME='Kimi'                        # optional display name
# export KIMI_DEFAULT_MODEL='kimi26'          # optional (defaults to first of *_MODELS)
# export KIMI_SUPPORTS_IMAGES='true'          # optional (default: text only)
```

5. Run the bot:
```bash
uv run python bot.py
```

## Required API Keys

- **Telegram Bot Token**: Obtain from [BotFather](https://t.me/botfather)
- **OpenAI API Key**: Get from [OpenAI Platform](https://platform.openai.com/account/api-keys)
- **Anthropic API Key**: Get from [Anthropic Console](https://console.anthropic.com/)
- **Google Gemini API Key** (optional): For Gemini models
- **Grok API Key** (optional): For Grok / OpenAI-compatible endpoint
- **Black Forest Labs API Key** (optional): For Flux image generation

At least one AI provider key is required.

## Environment Variables

All configuration is done through environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `TG_BOT_TOKEN` | Your Telegram bot token | *Required* |
| `OPENAI_API_KEY` | Your OpenAI API key | *Required for OpenAI* |
| `ANTHROPIC_API_KEY` | Your Anthropic API key | *Required for Claude* |
| `GEMINI_API_KEY` | Your Google Gemini API key | *Required for Gemini* |
| `GROK_API_KEY` | Your Grok API key | *Required for Grok* |
| `GROK_BASE_URL` | Base URL for the Grok (OpenAI-compatible) endpoint | https://api.groq.com/openai/v1 |
| `OPENAI_MODEL` | OpenAI model to use | gpt-4o-mini |
| `ANTHROPIC_MODEL` | Claude model to use | claude-3-5-haiku-20241022 |
| `GEMINI_MODEL` | Gemini model to use | gemini-pro |
| `GROK_MODEL` | Grok model to use | grok-1 |
| `FLUX_MODEL` | Flux image generation model | flux-pro-1.1 |
| `OPENAI_ALLOWED_MODELS` | Comma-separated allowlist of OpenAI models | *all built-in* |
| `ANTHROPIC_ALLOWED_MODELS` | Comma-separated allowlist of Claude models | *all built-in* |
| `GEMINI_ALLOWED_MODELS` | Comma-separated allowlist of Gemini models | *all built-in* |
| `GROK_ALLOWED_MODELS` | Comma-separated allowlist of Grok models | *all built-in* |
| `OPENAI_REASONING_EFFORT` | Reasoning effort for OpenAI reasoning models (none/minimal/low/medium/high/xhigh) | *unset* |
| `DEFAULT_MODEL_PROVIDER` | Default AI provider (falls back to first enabled) | openai |
| `SYSTEM_PROMPT` | System prompt sent to the models | You are a helpful assistant. |
| `BOT_USERNAME` | Bot username (for mention handling in groups) | TschatWitscha_bot |
| `BFL_API_KEY` | Black Forest Labs API key (Flux image generation) | *Optional* |
| `CHANNEL_ID` | Channel ID(s) for subscription check (comma-separated) | @korobo4ka_xoroni |
| `CHANNEL_USER_ID` | Telegram user id used for channel-post detection | 777000 |
| `LOG_LEVEL` | Logging level | INFO |
| `CUSTOM_PROVIDERS` | Comma-separated prefixes for self-hosted OpenAI-compatible providers | *Optional* |

### Guest Mode (Telegram Bot API 10.0)

Guest Mode lets allowed users @mention the bot from chats where it is not a
member. Access control is based on the **caller's user id**, never a chat
allowlist. Disabled by default.

| Variable | Description | Default |
|----------|-------------|---------|
| `TG_GUEST_ACCESS_MODE` | `disabled`, `allowlist`, or `public` | disabled |
| `TG_GUEST_ALLOWED_USER_IDS` | Comma-separated user ids allowed in `allowlist` mode | *empty* |
| `TG_GUEST_MAX_RESPONSE_CHARS` | Max characters in a guest response | 3500 |
| `TG_GUEST_TIMEOUT_SECONDS` | Timeout for guest responses | 45 |
| `TG_GUEST_RATE_LIMIT_PER_USER_MINUTE` | Max guest requests per user per minute | 3 |

## Commands

- `/start` - Start the bot and get help
- `/help` - Display available commands
- `/new` - Start a new conversation
- `/provider` - Select AI provider (OpenAI, Claude, Gemini, Grok, or any configured custom provider)
- `/model` - Choose a specific model from the current provider
- `/imgmodel` - Set the default image generation model
- `/img [openai|flux] <prompt>` - Generate an image from text
- `/insta <url>` - Download Instagram video
- `/ask <question>` - Ask a question in group chats

## License

[MIT License](LICENSE)
