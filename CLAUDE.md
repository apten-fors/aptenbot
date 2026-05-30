# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Telegram bot built with aiogram 3.x that integrates multiple AI providers (OpenAI, Claude, Gemini, Grok) for intelligent conversations, image processing, and media handling. The bot supports both private chats and group conversations with per-user session management.

## Commands

### Development
The project is managed with [uv](https://docs.astral.sh/uv/) (`pyproject.toml` + `uv.lock`),
pinned to Python 3.14 via `.python-version`. There is no `requirements.txt`.
```bash
# Install dependencies (creates .venv on Python 3.14)
uv sync

# Run the bot
uv run python bot.py

# Run tests
uv run pytest
```

### Required Environment Variables
```bash
# Core
export TG_BOT_TOKEN='your_telegram_bot_token'

# AI Providers (at least one required)
export OPENAI_API_KEY='your_key'
export ANTHROPIC_API_KEY='your_key'
export GEMINI_API_KEY='your_key'
export GROK_API_KEY='your_key'

# Optional
export BFL_API_KEY='your_key'  # For Flux image generation
export CHANNEL_ID='@channel1,@channel2'  # Comma-separated list for subscription checks

# Self-hosted / OpenAI-compatible providers (chat/completions). Add any number
# of providers via CUSTOM_PROVIDERS (comma-separated prefixes); each is text-only
# by default and only appears once its API key + base URL + models are all set.
export CUSTOM_PROVIDERS='kimi,glm,deepseek'
export KIMI_API_KEY='...'
export KIMI_BASE_URL='https://kimi.myinfra.example/v1'
export KIMI_MODELS='kimi26'            # comma-separated model ids your server exposes
export KIMI_NAME='Kimi'                # optional display name
# export KIMI_DEFAULT_MODEL='kimi26'   # optional (defaults to first of *_MODELS)
# export KIMI_SUPPORTS_IMAGES='true'   # optional (default: text only)
```

## Architecture

### Core Components

**Entry Point (`bot.py`)**
- Initializes Bot and Dispatcher with MemoryStorage for FSM
- Creates singleton instances of all managers and clients
- Registers dependencies via `dp["key"] = instance` pattern
- Sets up middleware chain: LoggingMiddleware → SubscriptionMiddleware → DependencyMiddleware
- Includes routers in order: commands → messages → media

**Dependency Injection Pattern**
All handlers receive dependencies through middleware injection, not direct imports:
```python
async def handler(message: Message, session_manager, provider_clients):
    # Dependencies automatically injected by DependencyMiddleware
```

The `DependencyMiddleware` (middlewares/dependencies.py) injects managers and clients into handler parameters. Never instantiate clients directly in handlers.

Chat handlers receive `provider_clients` — a `dict[provider_id -> client]` built in `bot.py` from the provider registry (see below). Dispatch is registry-driven, not hardcoded: resolve the client with `select_client(provider_clients, provider)` (services/answer_service.py) and call `client.process_message(...)` / `process_message_with_image(...)`. `openai_client` (for `/img`), `flux_client`, and `instagram_client` are still injected individually for non-chat features.

**Session Management (`managers/session_manager.py`)**
- `SessionManager`: Manages per-user conversation state with in-memory dict storage
- `Session`: Wrapper class for individual user sessions with methods like:
  - `process_openai_message()`, `process_claude_message()`, `process_gemini_message()`, `process_openai_chat_message()` (the latter is shared by Grok and all OpenAI-compatible custom providers)
  - `update_state()`, `get_state()`, `clear_state()` for FSM state tracking
  - `update_model()`, `get_model()` for model selection
- Sessions expire after 1 hour (SESSION_EXPIRY in config.py)
- Model preferences persist across sessions for the same user
- Messages stored with roles: "developer" (system), "user", "assistant"

**Client Architecture (`clients/`)**
Each AI client follows the same async context manager pattern:
```python
@asynccontextmanager
async def get_client(self):
    async with ClientLibrary(...) as client:
        yield client
```

Key methods:
- `process_message(session, text)`: Text-only conversations
- `process_message_with_image(session, text, image_urls)`: Multimodal requests
- `generate_image(prompt)`: Image generation (OpenAI, Flux only)

**OpenAI Client (`clients/openai_client.py`)**
- Uses OpenAI Responses API (NOT Chat Completions API)
- Supports reasoning models (o1, o3-mini, etc.) without fallback
- Image handling: converts Telegram file paths to full URLs

**Claude Client (`clients/claude_client.py`)**
- Uses Anthropic Messages API
- System prompt passed separately (not in messages array)
- Image format: `{"type": "image", "source": {"type": "url", "url": "..."}}`

**OpenAI-Compatible Client (`clients/openai_compatible_client.py`)**
- Used by Grok AND all self-hosted custom providers (kimi, glm, deepseek, ...)
- Uses the Chat Completions API (`chat.completions.create`) via `AsyncOpenAI(api_key, base_url)`
- One instance per provider, bound to that provider's `api_key` + `base_url`
- Request logic lives in `Session.process_openai_chat_message()` (maps the internal
  "developer" system role to "system" for chat/completions servers)

**Other Clients**
- Gemini: Uses Google's generativeai library with sync wrapper
- Flux: Black Forest Labs API for image generation
- Instagrapi: Downloads Instagram videos with Redis session caching

**Provider Registry (`providers.py`)**
- Single source of truth for chat providers; built-ins (openai/anthropic/gemini/grok)
  come from `config.py`, custom ones from the `CUSTOM_PROVIDERS` env var
- `ProviderConfig` carries id, name, api_style, api_key, base_url, models, default_model, supports_images
- A provider is only *enabled* when its required credentials are present, so the
  `/provider` menu and dispatch reflect what is actually configured
- Helpers used across the app: `enabled_providers()`, `get_provider()`, `models_for()`,
  `default_model_for()`, `default_provider_id()`, `is_image_capable()`
- Adding a new OpenAI-compatible model is **config-only** — no code changes

**Router Structure (`routers/`)**
- `commands.py`: Handles all slash commands (/start, /help, /new, /provider, /model, /img, /insta, /ask)
- `messages.py`: Processes text messages in private and group chats
- `media.py`: Handles photo/video/document uploads with multimodal processing
- FSM states tracked in session for multi-step interactions (model selection, provider selection)

**Group Chat Handling**
Bot responds in groups when:
1. @username mentioned in message
2. Replying to bot's message
3. Message starts with /ask command

In group chats, numeric selections (for model/provider) must be replies to bot messages.

**Media Processing Flow**
1. User sends photo/document → media router handler
2. Handler gets file from Telegram API: `await message.bot.get_file(file_id)`
3. File path passed to appropriate client's `process_message_with_image()`
4. Client converts relative path to full URL: `https://api.telegram.org/file/bot{TOKEN}/{file_path}`
5. Response sent via multimodal API (OpenAI Responses API, Claude Messages API, etc.)

**Subscription Middleware (`middlewares/subscription.py`)**
- Checks if user is subscribed to configured channels (CHANNEL_IDS)
- Skips check for private chats
- Blocks non-subscribers in groups from using bot

**Configuration (`config.py` + `providers.py`)**
- All settings via environment variables
- Built-in model lists: OPENAI_MODELS, ANTHROPIC_MODELS, GEMINI_MODELS, GROK_MODELS
- Allowed models can be restricted via OPENAI_ALLOWED_MODELS env var (comma-separated)
- DEFAULT_MODEL_PROVIDER determines initial provider selection (falls back to the first
  enabled provider if it isn't configured)
- Special handling for reasoning models (OPENAI_MODELS_REASONING)
- `providers.py` composes all of the above into the provider registry and adds any
  `CUSTOM_PROVIDERS`; menus (`/provider`, `/model`) and dispatch are generated from it

### Message Flow

**Private Chat:**
1. User sends message → LoggingMiddleware logs it
2. SubscriptionMiddleware checks subscription (skips private chats)
3. DependencyMiddleware injects session_manager and clients
4. messages.py router matches based on chat type
5. Handler gets/creates session, determines provider, processes message
6. Response sent back via `message.reply()`

**Group Chat:**
1. Bot checks if it should respond (mentioned, replied to, /ask command)
2. Same middleware chain as private
3. Group message handler processes if conditions met
4. For /ask command, commands.py handler processes it

**State-Based Selection (Provider/Model):**
1. User sends /provider or /model command
2. Handler displays options and sets session state (e.g., "selecting_provider")
3. User replies with number
4. Number handler checks session state, processes selection, clears state
5. In groups: must be reply to bot message to avoid conflicts

## Important Patterns

**Never Create Client Instances in Handlers**
Always use injected dependencies. Clients are singletons created in bot.py.

**Image URL Handling**
Telegram file paths are relative. Always convert:
```python
if not url.startswith(('http://', 'https://')):
    url = f"https://api.telegram.org/file/bot{self.telegram_bot_token}/{url}"
```

**Session State Management**
- Use `session.update_state()` before showing selection menus
- Always call `session.clear_state()` in finally blocks after processing
- Check state before processing numeric inputs to avoid conflicts

**Two OpenAI API styles**
The built-in `openai` provider uses the OpenAI **Responses API**:
```python
input_items = [{"role": "system"|"user"|"assistant", "content": ...}]
response = await client.responses.create(model=model, input=input_items)
text = response.output_text
```
Grok and all self-hosted custom providers use the **Chat Completions API** via
`OpenAICompatibleClient` / `Session.process_openai_chat_message()`:
```python
response = await client.chat.completions.create(model=model, messages=messages)
text = response.choices[0].message.content
```

**Error Handling**
- Clients catch provider-specific errors (RateLimitError, OpenAIError, etc.)
- Return user-friendly error strings, not exceptions
- Log errors with logger.error() including exc_info=True for tracebacks

**FSM State in Sessions**
Don't use aiogram FSM states. Use session.data['state'] for state tracking:
- "selecting_provider"
- "selecting_specific_model"
- "selecting_img_model"

## Testing

Test structure mirrors source:
- `tests/routers/` for router tests
- `tests/middlewares/` for middleware tests
- Tests use module stubs (see test_telegram_utils.py) for external dependencies
