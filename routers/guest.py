"""Telegram Guest Mode router.

Handles ``guest_message`` updates (Bot API 10.0 / aiogram 3.28+): an allowed
user calling the bot via @mention from a chat where the bot is not a member.
Each guest request is a one-shot, isolated query answered exactly once via
``Message.answer_guest_query`` (never ``sendMessage``).
"""
import asyncio
import time

from aiogram import Router, F
from aiogram.types import Message, InlineQueryResultArticle, InputTextMessageContent

from config import (
    GUEST_ACCESS_MODE,
    GUEST_ALLOWED_USER_IDS,
    GUEST_MAX_RESPONSE_CHARS,
    GUEST_TIMEOUT_SECONDS,
)
from services.answer_service import (
    build_ephemeral_session,
    generate_text_answer,
    is_provider_error,
)
from utils.guest import (
    build_guest_session_key,
    extract_guest_caller_user_id,
    is_guest_allowed,
    trim_guest_response,
)
from utils.logging_config import logger

router = Router()

_FALLBACK_ANSWER = "Could not generate an answer, please try again later."
_RATE_LIMITED_ANSWER = "Too many requests, try later."
_NON_TEXT_ANSWER = "Guest Mode currently supports text requests only."
_ANSWER_RESULT_ID = "answer-1"
_ANSWER_TITLE = "AptenBot answer"


def _build_answer(text: str) -> InlineQueryResultArticle:
    """Wrap an answer string in a valid InlineQueryResultArticle."""
    return InlineQueryResultArticle(
        id=_ANSWER_RESULT_ID,
        title=_ANSWER_TITLE,
        input_message_content=InputTextMessageContent(message_text=text),
    )


async def _answer_once(message: Message, text: str) -> bool:
    """Send a guest answer, allowing at most one retry for transient failures.

    Returns True if the answer was delivered.
    """
    for attempt in range(2):
        try:
            await message.answer_guest_query(_build_answer(text))
            return True
        except Exception as e:  # noqa: BLE001
            if attempt == 0:
                logger.warning("answer_guest_query failed (retrying): %s", e)
                continue
            logger.error("answer_guest_query failed permanently: %s", e, exc_info=True)
            return False
    return False


@router.guest_message(F.text)
async def handle_guest_message(
    message: Message,
    session_manager,
    provider_clients,
    guest_rate_limiter,
):
    started = time.monotonic()
    guest_query_id = getattr(message, "guest_query_id", None)
    caller_user_id = extract_guest_caller_user_id(message)
    source_chat = getattr(message, "chat", None)
    source_chat_id = getattr(source_chat, "id", None)

    # Drop updates that cannot be answered or authorized.
    if not guest_query_id:
        logger.warning("guest_message dropped: missing guest_query_id")
        return
    if caller_user_id is None:
        logger.warning(
            "guest_message dropped: missing caller user id guest_query_id=%s", guest_query_id
        )
        return

    text = (message.text or "").strip()
    logger.info(
        "guest_message_received caller_user_id=%s source_chat_id=%s guest_query_id=%s text_len=%s",
        caller_user_id, source_chat_id, guest_query_id, len(text),
    )

    # Authorization is based ONLY on the caller user id (never the chat id).
    if not is_guest_allowed(caller_user_id, GUEST_ACCESS_MODE, GUEST_ALLOWED_USER_IDS):
        logger.info(
            "guest_message_denied caller_user_id=%s guest_query_id=%s mode=%s",
            caller_user_id, guest_query_id, GUEST_ACCESS_MODE,
        )
        return  # No LLM call, no answer.

    if not text:
        logger.info("guest_message ignored: empty text guest_query_id=%s", guest_query_id)
        return

    # Rate limit per caller user id.
    if not await guest_rate_limiter.allow(caller_user_id):
        logger.info(
            "guest_message_rate_limited caller_user_id=%s guest_query_id=%s",
            caller_user_id, guest_query_id,
        )
        await _answer_once(message, _RATE_LIMITED_ANSWER)
        return

    # Isolated, one-shot session (never stored in SessionManager.sessions).
    # Reuse the caller's provider preference if they have one; get_model_provider
    # returns the default without mutating sessions when absent.
    session_key = build_guest_session_key(caller_user_id, guest_query_id)
    provider = session_manager.get_model_provider(caller_user_id)
    session = build_ephemeral_session(provider)

    logger.info(
        "guest_message_llm_started caller_user_id=%s guest_query_id=%s provider=%s",
        caller_user_id, guest_query_id, provider,
    )
    try:
        answer = await asyncio.wait_for(
            generate_text_answer(
                prompt=text,
                user_id=caller_user_id,
                chat_id=source_chat_id,
                session_key=session_key,
                source="telegram_guest",
                session=session,
                provider_clients=provider_clients,
            ),
            timeout=GUEST_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.error(
            "guest_message_llm_started timed out caller_user_id=%s guest_query_id=%s timeout=%s",
            caller_user_id, guest_query_id, GUEST_TIMEOUT_SECONDS,
        )
        answer = _FALLBACK_ANSWER
    except Exception as e:  # noqa: BLE001
        logger.error(
            "guest LLM failed caller_user_id=%s guest_query_id=%s err=%s",
            caller_user_id, guest_query_id, e, exc_info=True,
        )
        answer = _FALLBACK_ANSWER

    # Session methods return raw error strings instead of raising; for one-shot
    # guest answers, replace them with a friendly fallback.
    if not answer or is_provider_error(answer):
        answer = _FALLBACK_ANSWER

    answer = trim_guest_response(answer, GUEST_MAX_RESPONSE_CHARS)

    if await _answer_once(message, answer):
        logger.info(
            "guest_message_answer_sent caller_user_id=%s guest_query_id=%s response_len=%s duration_ms=%s",
            caller_user_id, guest_query_id, len(answer), int((time.monotonic() - started) * 1000),
        )
    else:
        logger.error(
            "guest_message_answer_failed caller_user_id=%s guest_query_id=%s",
            caller_user_id, guest_query_id,
        )


@router.guest_message()
async def handle_guest_non_text(message: Message):
    """Fallback for non-text guest messages (registered after the text handler)."""
    guest_query_id = getattr(message, "guest_query_id", None)
    if not guest_query_id:
        return
    logger.info("guest_message ignored: non-text guest_query_id=%s", guest_query_id)
    # First version simply ignores non-text; optionally inform the caller.
    await _answer_once(message, _NON_TEXT_ANSWER)
