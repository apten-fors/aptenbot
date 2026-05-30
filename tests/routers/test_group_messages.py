import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from routers.messages import handle_group_message
from routers.commands import handle_ask_command

TEST_BOT_USERNAME = "TestBot"
TEST_BOT_ID = 987654321
MOCKED_AI_RESPONSE = "Mocked AI response"

# These tests use lightweight duck-typed stubs (matching tests/routers/test_guest.py)
# instead of real aiogram Message objects: aiogram's Message is a frozen pydantic
# model, so `message.reply` cannot be replaced with a mock on a real instance.


def make_message(text, *, user_id=12345, reply_to=None, caption=None):
    bot_user = SimpleNamespace(id=TEST_BOT_ID, username=TEST_BOT_USERNAME)
    bot = SimpleNamespace(me=AsyncMock(return_value=bot_user), get_file=AsyncMock())
    msg = SimpleNamespace(
        text=text,
        caption=caption,
        from_user=SimpleNamespace(id=user_id),
        chat=SimpleNamespace(id=-100123456789, type="group"),
        entities=None,
        reply_to_message=reply_to,
        bot=bot,
        photo=None,
    )
    msg.reply = AsyncMock()
    msg.answer = AsyncMock()
    return msg


@pytest.fixture
def mock_session_manager():
    manager = MagicMock()
    session = MagicMock()
    session.get_provider = MagicMock(return_value="openai")  # used by handle_ask_command
    manager.get_or_create_session = MagicMock(return_value=session)
    manager.get_model_provider = MagicMock(return_value="openai")
    return manager


@pytest.fixture
def mock_openai_client():
    client = AsyncMock()
    client.process_message = AsyncMock(return_value=MOCKED_AI_RESPONSE)
    return client


@pytest.fixture
def mock_claude_client():
    client = AsyncMock()
    client.process_message = AsyncMock(return_value="Mocked Claude response")
    return client


@pytest.fixture
def provider_clients(mock_openai_client, mock_claude_client):
    # Handlers now dispatch via a provider -> client map instead of individual kwargs.
    return {"openai": mock_openai_client, "anthropic": mock_claude_client}


# --- Tests for routers.messages.handle_group_message ---

@pytest.mark.asyncio
async def test_direct_mention_in_group_processed(mock_session_manager, mock_openai_client, mock_claude_client, provider_clients):
    """Direct @bot_username mention in a group message IS processed."""
    message = make_message(f"@{TEST_BOT_USERNAME} hello there!")

    await handle_group_message(message, session_manager=mock_session_manager, provider_clients=provider_clients)

    message.reply.assert_called_once()
    mock_openai_client.process_message.assert_called_once()
    args, _ = mock_openai_client.process_message.call_args
    assert args[1] == "hello there!"
    mock_claude_client.process_message.assert_not_called()


@pytest.mark.asyncio
async def test_reply_to_bot_in_group_processed(mock_session_manager, mock_openai_client, mock_claude_client, provider_clients):
    """Replying to the bot's own message IS processed (with context)."""
    bot_previous_message = SimpleNamespace(from_user=SimpleNamespace(id=TEST_BOT_ID), text="I am a bot.")
    message = make_message("Oh really?", reply_to=bot_previous_message)

    await handle_group_message(message, session_manager=mock_session_manager, provider_clients=provider_clients)

    message.reply.assert_called_once()
    mock_openai_client.process_message.assert_called_once()
    args, _ = mock_openai_client.process_message.call_args
    expected = "Context from my previous message: \"I am a bot.\"\n\nUser's question/reply: \"Oh really?\""
    assert args[1] == expected
    mock_claude_client.process_message.assert_not_called()


@pytest.mark.asyncio
async def test_mention_in_reply_to_another_user_processed(mock_session_manager, mock_openai_client, mock_claude_client, provider_clients):
    """Bot mention in a reply to another user's message IS processed (mention stripped)."""
    other_message = SimpleNamespace(from_user=SimpleNamespace(id=54321), text="This is User A's original message.")
    message = make_message(f"@{TEST_BOT_USERNAME} what do you think about this?", reply_to=other_message)

    await handle_group_message(message, session_manager=mock_session_manager, provider_clients=provider_clients)

    message.reply.assert_called_once()
    mock_openai_client.process_message.assert_called_once()
    # Only the mention is stripped; context from another user's message is not added.
    args, _ = mock_openai_client.process_message.call_args
    assert args[1] == "what do you think about this?"
    mock_claude_client.process_message.assert_not_called()


@pytest.mark.asyncio
async def test_general_group_message_ignored(mock_session_manager, mock_openai_client, mock_claude_client, provider_clients):
    """A general group message (no mention, no reply, not /ask) is IGNORED."""
    message = make_message("Just a random message.")

    await handle_group_message(message, session_manager=mock_session_manager, provider_clients=provider_clients)

    message.reply.assert_not_called()
    mock_openai_client.process_message.assert_not_called()
    mock_claude_client.process_message.assert_not_called()


@pytest.mark.asyncio
async def test_ask_command_in_group_ignored_by_message_handler(mock_session_manager, mock_openai_client, mock_claude_client, provider_clients):
    """/ask command in a group is IGNORED by handle_group_message (handled by the command handler)."""
    message = make_message("/ask How are you in a group?")

    await handle_group_message(message, session_manager=mock_session_manager, provider_clients=provider_clients)

    message.reply.assert_not_called()
    mock_openai_client.process_message.assert_not_called()
    mock_claude_client.process_message.assert_not_called()


# --- Tests for routers.commands.handle_ask_command ---

@pytest.mark.asyncio
async def test_ask_command_in_group_processed_by_command_handler(mock_session_manager, mock_openai_client, mock_claude_client, provider_clients):
    """/ask command IS processed by handle_ask_command, stripping the '/ask ' prefix."""
    mock_openai_client.process_message.return_value = "AI reply to /ask in group"
    message = make_message("/ask How are you in a group?")

    await handle_ask_command(message, session_manager=mock_session_manager, provider_clients=provider_clients)

    mock_openai_client.process_message.assert_called_once()
    args, _ = mock_openai_client.process_message.call_args
    assert args[1] == "How are you in a group?"
    message.reply.assert_called_once()
