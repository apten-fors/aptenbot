"""Transport-agnostic answer generation.

This module deliberately does NOT import ``aiogram`` — it keeps Telegram
transport logic (routers) separate from answer generation, so the same
provider-dispatch logic can serve both normal chat and guest requests.

It reuses the existing per-provider logic in ``managers.session_manager.Session``
via each client's ``process_message`` and never instantiates clients itself.
"""
from typing import Dict, Optional

from config import SYSTEM_PROMPT
from providers import default_model_for, default_provider_id
from managers.session_manager import Session
from utils.logging_config import logger

# Prefix used by Session.process_*_message when the underlying call raised.
# Guest answers are one-shot and user-facing, so callers can detect this and
# substitute a friendly fallback instead of surfacing a raw error string.
PROVIDER_ERROR_PREFIX = "Error processing message with"


def is_provider_error(text: Optional[str]) -> bool:
    """True if ``text`` looks like a raw provider-error string from a Session."""
    return bool(text) and text.startswith(PROVIDER_ERROR_PREFIX)


def select_client(provider_clients: Dict[str, object], provider: str):
    """Resolve the chat client for ``provider`` from a ``provider_clients`` map.

    Falls back to the default provider's client if the session's provider is no
    longer configured (e.g. credentials removed between sessions).
    """
    return provider_clients.get(provider) or provider_clients.get(default_provider_id())


def build_ephemeral_session(
    provider: str,
    model: Optional[str] = None,
    *,
    extra_body: Optional[Dict] = None,
) -> Session:
    """Build a one-shot ``Session`` backed by a fresh dict.

    This session is NEVER stored in ``SessionManager.sessions`` — it carries only
    the developer/system prompt and the provider/model selection, and is
    discarded by the caller after use.

    ``extra_body`` is an optional per-request body merged into OpenAI-compatible
    chat/completions calls (e.g. ``{"chat_template_kwargs": {"thinking": False}}``
    to suppress chain-of-thought on the guest path).
    """
    data = {
        "messages": [{"role": "developer", "content": SYSTEM_PROMPT}],
        "model_provider": provider,
        "model": model or default_model_for(provider),
        "image_model": "openai",
        "state": None,
    }
    if extra_body:
        data["extra_body"] = extra_body
    return Session(data)


async def generate_text_answer(
    prompt: str,
    user_id: int,
    chat_id: Optional[int],
    session_key: str,
    source: str,
    *,
    session: Session,
    provider_clients: Dict[str, object],
) -> str:
    """Generate a text answer for ``prompt`` using the session's provider.

    ``session`` is supplied by the caller (ephemeral for guest requests, the
    persistent per-user session for normal chat) so this same dispatch can serve
    both transports. ``provider_clients`` maps provider id -> client singleton —
    this function never creates clients and holds no global state.

    ``source`` is "telegram_message" for normal messages and "telegram_guest"
    for guest requests; ``chat_id`` is optional and not required for guests.
    """
    provider = session.get_provider()
    logger.info(
        "answer_generate source=%s session_key=%s user_id=%s chat_id=%s provider=%s",
        source, session_key, user_id, chat_id, provider,
    )

    client = select_client(provider_clients, provider)
    if client is None:
        logger.error("No client configured for provider=%s", provider)
        return f"{PROVIDER_ERROR_PREFIX} {provider}: no client configured"
    return await client.process_message(session, prompt)
