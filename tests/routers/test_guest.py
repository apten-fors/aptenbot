import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from routers.guest import handle_guest_message


def make_message(text="hello", guest_query_id="q-1", user_id=123, chat_id=-100):
    """Build a lightweight duck-typed guest message stub.

    The handler accesses attributes via getattr, so a SimpleNamespace suffices
    and avoids constructing a full aiogram Message.
    """
    msg = SimpleNamespace(
        text=text,
        guest_query_id=guest_query_id,
        from_user=SimpleNamespace(id=user_id) if user_id is not None else None,
        chat=SimpleNamespace(id=chat_id) if chat_id is not None else None,
    )
    msg.answer_guest_query = AsyncMock()
    return msg


@pytest.fixture
def session_manager():
    mgr = MagicMock()
    mgr.get_model_provider = MagicMock(return_value="openai")
    return mgr


@pytest.fixture
def clients():
    # handle_guest_message now receives a single provider_clients map instead of
    # individual client kwargs. Content is irrelevant here because these tests
    # patch generate_text_answer.
    return {"provider_clients": {"openai": AsyncMock()}}


@pytest.fixture
def allow_limiter():
    limiter = MagicMock()
    limiter.allow = AsyncMock(return_value=True)
    return limiter


@pytest.fixture
def deny_limiter():
    limiter = MagicMock()
    limiter.allow = AsyncMock(return_value=False)
    return limiter


async def _run(message, session_manager, clients, limiter):
    await handle_guest_message(
        message,
        session_manager=session_manager,
        guest_rate_limiter=limiter,
        **clients,
    )


def _sent_text(message):
    """Extract the message_text from the InlineQueryResultArticle that was sent."""
    result = message.answer_guest_query.call_args.args[0]
    return result.input_message_content.message_text


# 1. disabled => guest_message ignored
@pytest.mark.asyncio
async def test_disabled_mode_ignored(session_manager, clients, allow_limiter):
    message = make_message()
    with patch("routers.guest.GUEST_ACCESS_MODE", "disabled"), \
         patch("routers.guest.generate_text_answer", new=AsyncMock()) as gen:
        await _run(message, session_manager, clients, allow_limiter)
    gen.assert_not_called()
    message.answer_guest_query.assert_not_called()


# 2. allowlist + allowed caller => LLM called once, answered once
@pytest.mark.asyncio
async def test_allowlist_allowed_calls_llm_once(session_manager, clients, allow_limiter):
    message = make_message(user_id=123)
    with patch("routers.guest.GUEST_ACCESS_MODE", "allowlist"), \
         patch("routers.guest.GUEST_ALLOWED_USER_IDS", {123}), \
         patch("routers.guest.generate_text_answer", new=AsyncMock(return_value="hi")) as gen:
        await _run(message, session_manager, clients, allow_limiter)
    gen.assert_called_once()
    message.answer_guest_query.assert_called_once()


# 3. allowlist + denied caller => LLM not called, no answer
@pytest.mark.asyncio
async def test_allowlist_denied_no_llm(session_manager, clients, allow_limiter):
    message = make_message(user_id=999)
    with patch("routers.guest.GUEST_ACCESS_MODE", "allowlist"), \
         patch("routers.guest.GUEST_ALLOWED_USER_IDS", {123}), \
         patch("routers.guest.generate_text_answer", new=AsyncMock()) as gen:
        await _run(message, session_manager, clients, allow_limiter)
    gen.assert_not_called()
    message.answer_guest_query.assert_not_called()


# 4. missing caller user id => update ignored
@pytest.mark.asyncio
async def test_missing_caller_id_ignored(session_manager, clients, allow_limiter):
    message = make_message(user_id=None)
    with patch("routers.guest.GUEST_ACCESS_MODE", "public"), \
         patch("routers.guest.generate_text_answer", new=AsyncMock()) as gen:
        await _run(message, session_manager, clients, allow_limiter)
    gen.assert_not_called()
    message.answer_guest_query.assert_not_called()


# 5. missing guest_query_id => update ignored
@pytest.mark.asyncio
async def test_missing_guest_query_id_ignored(session_manager, clients, allow_limiter):
    message = make_message(guest_query_id=None)
    with patch("routers.guest.GUEST_ACCESS_MODE", "public"), \
         patch("routers.guest.generate_text_answer", new=AsyncMock()) as gen:
        await _run(message, session_manager, clients, allow_limiter)
    gen.assert_not_called()
    message.answer_guest_query.assert_not_called()


# 6. empty text => update ignored
@pytest.mark.asyncio
async def test_empty_text_ignored(session_manager, clients, allow_limiter):
    message = make_message(text="   ")
    with patch("routers.guest.GUEST_ACCESS_MODE", "public"), \
         patch("routers.guest.generate_text_answer", new=AsyncMock()) as gen:
        await _run(message, session_manager, clients, allow_limiter)
    gen.assert_not_called()
    message.answer_guest_query.assert_not_called()


# 7. answer_guest_query called exactly once
@pytest.mark.asyncio
async def test_answer_called_exactly_once(session_manager, clients, allow_limiter):
    message = make_message()
    with patch("routers.guest.GUEST_ACCESS_MODE", "public"), \
         patch("routers.guest.generate_text_answer", new=AsyncMock(return_value="hi")):
        await _run(message, session_manager, clients, allow_limiter)
    assert message.answer_guest_query.call_count == 1


# 8. long answer trimmed to GUEST_MAX_RESPONSE_CHARS
@pytest.mark.asyncio
async def test_long_answer_trimmed(session_manager, clients, allow_limiter):
    message = make_message()
    long_text = "x" * 5000
    with patch("routers.guest.GUEST_ACCESS_MODE", "public"), \
         patch("routers.guest.GUEST_MAX_RESPONSE_CHARS", 100), \
         patch("routers.guest.generate_text_answer", new=AsyncMock(return_value=long_text)):
        await _run(message, session_manager, clients, allow_limiter)
    assert len(_sent_text(message)) == 100


# 9. rate limit exceeded => LLM not called
@pytest.mark.asyncio
async def test_rate_limited_no_llm(session_manager, clients, deny_limiter):
    message = make_message()
    with patch("routers.guest.GUEST_ACCESS_MODE", "public"), \
         patch("routers.guest.generate_text_answer", new=AsyncMock()) as gen:
        await _run(message, session_manager, clients, deny_limiter)
    gen.assert_not_called()
    # Optional courtesy reply is allowed, but the LLM must not run.
    assert message.answer_guest_query.call_count <= 1


# 10. source chat id not required for authorization
@pytest.mark.asyncio
async def test_source_chat_id_not_required(session_manager, clients, allow_limiter):
    message = make_message(chat_id=None)
    with patch("routers.guest.GUEST_ACCESS_MODE", "public"), \
         patch("routers.guest.generate_text_answer", new=AsyncMock(return_value="hi")) as gen:
        await _run(message, session_manager, clients, allow_limiter)
    gen.assert_called_once()
    message.answer_guest_query.assert_called_once()


# 12. public allows a valid caller without an allowlist
@pytest.mark.asyncio
async def test_public_allows_without_allowlist(session_manager, clients, allow_limiter):
    message = make_message(user_id=555)
    with patch("routers.guest.GUEST_ACCESS_MODE", "public"), \
         patch("routers.guest.GUEST_ALLOWED_USER_IDS", set()), \
         patch("routers.guest.generate_text_answer", new=AsyncMock(return_value="hi")) as gen:
        await _run(message, session_manager, clients, allow_limiter)
    gen.assert_called_once()
    message.answer_guest_query.assert_called_once()


# guest path suppresses thinking for self-hosted (custom) providers
@pytest.mark.asyncio
async def test_guest_disables_thinking_for_custom_provider(session_manager, clients, allow_limiter):
    session_manager.get_model_provider = MagicMock(return_value="kimi")
    message = make_message()
    with patch("routers.guest.GUEST_ACCESS_MODE", "public"), \
         patch("routers.guest.GUEST_DISABLE_THINKING", True), \
         patch("routers.guest.is_custom_provider", return_value=True), \
         patch("routers.guest.generate_text_answer", new=AsyncMock(return_value="hi")) as gen:
        await _run(message, session_manager, clients, allow_limiter)
    session = gen.call_args.kwargs["session"]
    assert session.data.get("extra_body") == {"chat_template_kwargs": {"thinking": False}}


# guest path leaves built-in providers (e.g. Grok) untouched
@pytest.mark.asyncio
async def test_guest_keeps_thinking_for_builtin_provider(session_manager, clients, allow_limiter):
    message = make_message()
    with patch("routers.guest.GUEST_ACCESS_MODE", "public"), \
         patch("routers.guest.GUEST_DISABLE_THINKING", True), \
         patch("routers.guest.is_custom_provider", return_value=False), \
         patch("routers.guest.generate_text_answer", new=AsyncMock(return_value="hi")) as gen:
        await _run(message, session_manager, clients, allow_limiter)
    session = gen.call_args.kwargs["session"]
    assert "extra_body" not in session.data


# provider-error string is replaced with the friendly fallback
@pytest.mark.asyncio
async def test_provider_error_string_replaced_with_fallback(session_manager, clients, allow_limiter):
    message = make_message()
    err = "Error processing message with OpenAI: boom"
    with patch("routers.guest.GUEST_ACCESS_MODE", "public"), \
         patch("routers.guest.generate_text_answer", new=AsyncMock(return_value=err)):
        await _run(message, session_manager, clients, allow_limiter)
    assert _sent_text(message) == "Could not generate an answer, please try again later."


# 11. normal private message handler still works (regression)
@pytest.mark.asyncio
async def test_normal_private_message_still_works():
    from routers.messages import handle_private_message

    message = SimpleNamespace(
        from_user=SimpleNamespace(id=1),
        text="hello there",
        chat=SimpleNamespace(type="private"),
    )
    message.reply = AsyncMock()

    mgr = MagicMock()
    mgr.get_or_create_session = MagicMock(return_value="session_obj")
    mgr.get_model_provider = MagicMock(return_value="openai")

    openai_client = AsyncMock()
    openai_client.process_message = AsyncMock(return_value="a reply")

    await handle_private_message(
        message,
        session_manager=mgr,
        provider_clients={"openai": openai_client},
    )

    openai_client.process_message.assert_called_once()
    message.reply.assert_called_once()
