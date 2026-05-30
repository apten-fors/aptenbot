import asyncio
import sys
from colorama import init, Fore, Style
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from config import TELEGRAM_BOT_TOKEN, ALLOWED_UPDATES, GUEST_RATE_LIMIT_PER_USER_MINUTE
from managers.session_manager import SessionManager
from managers.subscription_manager import SubscriptionManager
from clients.openai_client import OpenAIClient
from clients.claude_client import ClaudeClient
from clients.gemini_client import GeminiClient
from clients.openai_compatible_client import OpenAICompatibleClient
from clients.flux_client import FluxClient
from clients.instagrapi_client import InstagrapiClient
from providers import (
    enabled_providers,
    OPENAI_RESPONSES,
    ANTHROPIC_STYLE,
    GEMINI_STYLE,
    OPENAI_CHAT,
)
from routers import commands_router, messages_router, media_router, guest_router
from middlewares.subscription import SubscriptionMiddleware
from middlewares.logging import LoggingMiddleware
from middlewares.dependencies import DependencyMiddleware
from utils.rate_limiter import create_guest_rate_limiter
from utils.logging_config import logger

# Initialize colorama for colored terminal output
init()

async def main():
    # Check if token is available
    if not TELEGRAM_BOT_TOKEN:
        print(f"\n{Fore.RED}ERROR: {Style.BRIGHT}Telegram Bot Token is missing!{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Please set the {Fore.GREEN}TG_BOT_TOKEN{Fore.YELLOW} environment variable.{Style.RESET_ALL}")
        print(f"\nExample: {Fore.CYAN}export TG_BOT_TOKEN='your_token_here'{Style.RESET_ALL}")
        print()
        sys.exit(1)

    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    session_manager = SessionManager()
    subscription_manager = SubscriptionManager()
    openai_client = OpenAIClient()
    claude_client = ClaudeClient()
    gemini_client = GeminiClient()
    flux_client = FluxClient()
    instagram_client = InstagrapiClient()
    guest_rate_limiter = await create_guest_rate_limiter(GUEST_RATE_LIMIT_PER_USER_MINUTE)

    # Build the provider -> chat-client map from the registry. Built-in styles
    # reuse their dedicated client; every OpenAI-compatible provider (grok and
    # any CUSTOM_PROVIDERS like kimi/glm/deepseek) gets its own client bound to
    # that provider's api_key + base_url. Adding a provider is config-only.
    provider_clients = {}
    for p in enabled_providers():
        if p.api_style == OPENAI_RESPONSES:
            provider_clients[p.id] = openai_client
        elif p.api_style == ANTHROPIC_STYLE:
            provider_clients[p.id] = claude_client
        elif p.api_style == GEMINI_STYLE:
            provider_clients[p.id] = gemini_client
        elif p.api_style == OPENAI_CHAT:
            provider_clients[p.id] = OpenAICompatibleClient(
                api_key=p.api_key,
                base_url=p.base_url,
                provider_name=p.name,
                supports_images=p.supports_images,
            )
    logger.info("Enabled chat providers: %s", ", ".join(provider_clients) or "<none>")

    # Register dependencies
    dp["session_manager"] = session_manager
    dp["subscription_manager"] = subscription_manager
    dp["openai_client"] = openai_client  # used by /img image generation
    dp["flux_client"] = flux_client
    dp["instagram_client"] = instagram_client
    dp["provider_clients"] = provider_clients

    # Middlewares
    dp.message.middleware(LoggingMiddleware())
    dp.message.middleware(SubscriptionMiddleware(subscription_manager))

    # DependencyMiddleware - register dependencies
    dependency_middleware = DependencyMiddleware(
        session_manager=session_manager,
        openai_client=openai_client,
        flux_client=flux_client,
        instagram_client=instagram_client,
        provider_clients=provider_clients,
    )
    dp.message.middleware(dependency_middleware)

    # Guest Mode dependency injection. Guest handlers need the session manager,
    # the provider-client map, and the rate limiter. Subscription/logging
    # middlewares are intentionally NOT applied here: subscription is chat-based
    # and must not gate guest callers.
    dp.guest_message.middleware(DependencyMiddleware(
        session_manager=session_manager,
        provider_clients=provider_clients,
        guest_rate_limiter=guest_rate_limiter,
    ))

    # Routers
    dp.include_router(commands_router)
    dp.include_router(messages_router)
    dp.include_router(media_router)
    dp.include_router(guest_router)

    # Verify Guest Mode is enabled for this bot (must not crash on failure).
    try:
        me = await bot.get_me()
        if not getattr(me, "supports_guest_queries", False):
            logger.warning(
                "Guest Mode is not enabled for this bot (supports_guest_queries is not true). "
                "Enable it in BotFather > Bot Settings > Guest Mode."
            )
    except Exception as e:
        logger.warning("Could not verify supports_guest_queries on startup: %s", e)

    print(f"\n{Fore.GREEN}Starting the bot...{Style.RESET_ALL}")
    logger.info("Starting the bot application")
    await dp.start_polling(bot, allowed_updates=ALLOWED_UPDATES)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Bot stopped.{Style.RESET_ALL}")
    except Exception as e:
        print(f"\n{Fore.RED}ERROR: {e}{Style.RESET_ALL}")
        logger.error(f"Error in main application: {e}", exc_info=True)
