import os
import sys
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from aiogram.types import Message, User, Chat
from aiogram.exceptions import TelegramAPIError

from middlewares.subscription import SubscriptionMiddleware

RESOLVED_CHANNEL_ID = -100987654321
_DATE = datetime(2024, 1, 1)


def make_message(*, from_user=None, sender_chat=None, chat=None, text="hello"):
    """Build a real aiogram Message (the middleware does isinstance(event, Message)).

    aiogram's Message is a frozen pydantic model, so `.answer` is attached via
    object.__setattr__ rather than normal assignment.
    """
    chat = chat or Chat(id=-1002, type="group")
    msg = Message(
        message_id=1,
        date=_DATE,
        chat=chat,
        from_user=from_user,
        sender_chat=sender_chat,
        text=text,
    )
    object.__setattr__(msg, "answer", AsyncMock())
    return msg


@pytest.fixture
def mock_bot():
    bot = MagicMock()
    bot.get_chat = AsyncMock()
    return bot


@pytest.fixture
def mock_subscription_manager():
    manager = MagicMock()
    manager.is_subscriber = AsyncMock()
    return manager


@pytest.fixture
def mock_handler():
    return AsyncMock(return_value="handler_called")


@pytest.fixture
def create_middleware(mock_subscription_manager):
    """Factory: a fresh middleware per test (it carries internal resolution state)."""
    def _create():
        return SubscriptionMiddleware(subscription_manager=mock_subscription_manager)
    return _create


# --- CHANNEL_IDS resolution + channel-message bypass ---

@pytest.mark.asyncio
@patch("middlewares.subscription.CHANNEL_IDS", ["@testchannel"])
async def test_channel_username_resolution_success_and_cache(
    create_middleware, mock_subscription_manager, mock_handler, mock_bot
):
    """Username resolves via get_chat once (cached), and channel messages bypass."""
    mw = create_middleware()
    mock_bot.get_chat.return_value = Chat(id=RESOLVED_CHANNEL_ID, type="channel", title="Test Channel")
    sender_chat = Chat(id=RESOLVED_CHANNEL_ID, type="channel")
    data = {"bot": mock_bot}

    msg1 = make_message(sender_chat=sender_chat, from_user=None)
    result = await mw(handler=mock_handler, event=msg1, data=data)

    mock_bot.get_chat.assert_called_once_with(chat_id="@testchannel")
    mock_handler.assert_called_once_with(msg1, data)
    assert result == "handler_called"
    assert mw.resolved_numeric_channel_ids["@testchannel"] == RESOLVED_CHANNEL_ID
    mock_subscription_manager.is_subscriber.assert_not_called()  # bypassed

    # Second call: resolution is cached, get_chat not called again.
    mock_handler.reset_mock()
    msg2 = make_message(sender_chat=sender_chat, from_user=None)
    result2 = await mw(handler=mock_handler, event=msg2, data=data)

    mock_bot.get_chat.assert_called_once()  # still just the first call
    mock_handler.assert_called_once_with(msg2, data)
    assert result2 == "handler_called"


@pytest.mark.asyncio
@patch("middlewares.subscription.CHANNEL_IDS", [str(RESOLVED_CHANNEL_ID)])
async def test_channel_numeric_string_direct_use(
    create_middleware, mock_subscription_manager, mock_handler, mock_bot
):
    """A numeric CHANNEL_IDS entry is used directly; get_chat is never called."""
    mw = create_middleware()
    sender_chat = Chat(id=RESOLVED_CHANNEL_ID, type="channel")
    data = {"bot": mock_bot}

    msg = make_message(sender_chat=sender_chat, from_user=None)
    result = await mw(handler=mock_handler, event=msg, data=data)

    mock_bot.get_chat.assert_not_called()
    mock_handler.assert_called_once_with(msg, data)
    assert result == "handler_called"
    assert mw.resolved_numeric_channel_ids[str(RESOLVED_CHANNEL_ID)] == RESOLVED_CHANNEL_ID
    mock_subscription_manager.is_subscriber.assert_not_called()


@pytest.mark.asyncio
@patch("middlewares.subscription.CHANNEL_IDS", ["@nonexistent"])
async def test_channel_resolution_fails_telegram_api_error(
    create_middleware, mock_subscription_manager, mock_handler, mock_bot
):
    """If resolution raises TelegramAPIError, the channel maps to -1 and the
    middleware falls back to a per-user subscription check."""
    mw = create_middleware()
    mock_bot.get_chat.side_effect = TelegramAPIError(method="getChat", message="Chat not found")
    user = User(id=789, is_bot=False, first_name="TestUser")
    msg = make_message(from_user=user, sender_chat=Chat(id=12345, type="channel"))
    data = {"bot": mock_bot}

    mock_subscription_manager.is_subscriber.return_value = False
    await mw(handler=mock_handler, event=msg, data=data)

    mock_bot.get_chat.assert_called_once_with(chat_id="@nonexistent")
    mock_subscription_manager.is_subscriber.assert_called_once_with(user.id, mock_bot)
    msg.answer.assert_called_once_with(
        "To use this bot, you need to be a subscriber of the @nonexistent channel."
    )
    mock_handler.assert_not_called()
    assert mw.resolved_numeric_channel_ids["@nonexistent"] == -1


@pytest.mark.asyncio
@patch("middlewares.subscription.CHANNEL_IDS", ["@brokenchannel"])
async def test_channel_resolution_fails_generic_exception(
    create_middleware, mock_subscription_manager, mock_handler, mock_bot
):
    """A generic exception during resolution also maps to -1 and falls back."""
    mw = create_middleware()
    mock_bot.get_chat.side_effect = Exception("Some generic error")
    user = User(id=789, is_bot=False, first_name="TestUser")
    msg = make_message(from_user=user, sender_chat=None)
    data = {"bot": mock_bot}

    mock_subscription_manager.is_subscriber.return_value = False
    await mw(handler=mock_handler, event=msg, data=data)

    mock_bot.get_chat.assert_called_once_with(chat_id="@brokenchannel")
    mock_subscription_manager.is_subscriber.assert_called_once_with(user.id, mock_bot)
    msg.answer.assert_called_once_with(
        "To use this bot, you need to be a subscriber of the @brokenchannel channel."
    )
    mock_handler.assert_not_called()
    assert mw.resolved_numeric_channel_ids["@brokenchannel"] == -1


# --- Per-user subscription check (no channel bypass) ---

@pytest.mark.asyncio
@patch("middlewares.subscription.CHANNEL_IDS", ["@some_other_channel"])
async def test_user_not_subscribed_regular_message(
    create_middleware, mock_subscription_manager, mock_handler, mock_bot
):
    """A non-subscribed user's message is blocked with a denial message."""
    mw = create_middleware()
    mock_bot.get_chat.return_value = Chat(id=-999, type="channel")  # won't match sender_chat
    user = User(id=123, is_bot=False, first_name="Test")
    msg = make_message(from_user=user, sender_chat=None, chat=Chat(id=456, type="private"))
    data = {"bot": mock_bot}

    mock_subscription_manager.is_subscriber.return_value = False
    result = await mw(handler=mock_handler, event=msg, data=data)

    mock_subscription_manager.is_subscriber.assert_called_once_with(user.id, mock_bot)
    msg.answer.assert_called_once_with(
        "To use this bot, you need to be a subscriber of the @some_other_channel channel."
    )
    mock_handler.assert_not_called()
    assert result is None


@pytest.mark.asyncio
@patch("middlewares.subscription.CHANNEL_IDS", ["@another_channel_configured"])
async def test_user_subscribed_regular_message(
    create_middleware, mock_subscription_manager, mock_handler, mock_bot
):
    """A subscribed user's message is allowed through to the handler."""
    mw = create_middleware()
    mock_bot.get_chat.return_value = Chat(id=-999, type="channel")
    user = User(id=123, is_bot=False, first_name="Test")
    msg = make_message(from_user=user, sender_chat=None, chat=Chat(id=456, type="private"))
    data = {"bot": mock_bot}

    mock_subscription_manager.is_subscriber.return_value = True
    result = await mw(handler=mock_handler, event=msg, data=data)

    mock_subscription_manager.is_subscriber.assert_called_once_with(user.id, mock_bot)
    msg.answer.assert_not_called()
    mock_handler.assert_called_once_with(msg, data)
    assert result == "handler_called"


@pytest.mark.asyncio
@patch("middlewares.subscription.CHANNEL_IDS", ["@some_other_channel", "@second_channel"])
async def test_multi_channel_denial_message(
    create_middleware, mock_subscription_manager, mock_handler, mock_bot
):
    """With several channels configured the denial lists all of them."""
    mw = create_middleware()
    mock_bot.get_chat.return_value = Chat(id=-999, type="channel")
    user = User(id=123, is_bot=False, first_name="Test")
    msg = make_message(from_user=user, sender_chat=None, chat=Chat(id=456, type="private"))
    data = {"bot": mock_bot}

    mock_subscription_manager.is_subscriber.return_value = False
    await mw(handler=mock_handler, event=msg, data=data)

    msg.answer.assert_called_once_with(
        "To use this bot, you need to be a subscriber of one of these channels: "
        "@some_other_channel, @second_channel."
    )
    mock_handler.assert_not_called()


# --- Pass-through cases ---

@pytest.mark.asyncio
@patch("middlewares.subscription.CHANNEL_IDS", [str(RESOLVED_CHANNEL_ID)])
async def test_non_message_event_passes(create_middleware, mock_handler, mock_bot):
    """A non-Message event is passed straight to the handler."""
    mw = create_middleware()
    non_message_event = MagicMock()  # not a Message instance
    data = {"bot": mock_bot}

    result = await mw(handler=mock_handler, event=non_message_event, data=data)

    mock_handler.assert_called_once_with(non_message_event, data)
    assert result == "handler_called"
    # CHANNEL_IDS is numeric, so resolution never needs get_chat.
    mock_bot.get_chat.assert_not_called()


@pytest.mark.asyncio
async def test_message_without_from_user_or_relevant_sender_chat_passes(
    create_middleware, mock_handler, mock_bot
):
    """A message with no from_user and a non-matching sender_chat passes through."""
    mw = create_middleware()
    # Pretend resolution already happened.
    mw.resolved_numeric_channel_ids = {"@x": RESOLVED_CHANNEL_ID}
    mw.resolving_started = True

    msg = make_message(
        from_user=None,
        sender_chat=Chat(id=RESOLVED_CHANNEL_ID + 1, type="channel"),
        chat=Chat(id=456, type="private"),
    )
    data = {"bot": mock_bot}

    result = await mw(handler=mock_handler, event=msg, data=data)

    mock_handler.assert_called_once_with(msg, data)
    assert result == "handler_called"
