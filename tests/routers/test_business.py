from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.methods import SendMessage
from aiogram.types import Message

from config import ALLOWED_UPDATES
from routers.business import (
    build_business_session_key,
    handle_business_connection,
    handle_business_message,
    handle_deleted_business_messages,
    handle_edited_business_message,
)
from utils.telegram_utils import send_long_message


def test_business_update_types_are_allowed():
    assert {
        "business_connection",
        "business_message",
        "edited_business_message",
        "deleted_business_messages",
    }.issubset(ALLOWED_UPDATES)


def make_business_message(
    text="Hello",
    *,
    business_connection_id="business-123",
    chat_id=456,
    user_id=789,
    message_id=10,
):
    message = SimpleNamespace(
        business_connection_id=business_connection_id,
        chat=SimpleNamespace(id=chat_id),
        from_user=SimpleNamespace(id=user_id),
        message_id=message_id,
        text=text,
    )
    message.reply = AsyncMock(return_value=SimpleNamespace(message_id=11))
    return message


@pytest.mark.asyncio
async def test_business_message_uses_isolated_session_and_existing_pipeline():
    message = make_business_message()
    session_manager = MagicMock()
    session = MagicMock()
    session_manager.get_or_create_session.return_value = session
    session_manager.get_model_provider.return_value = "openai"
    client = AsyncMock()
    client.process_message.return_value = "Secretary reply"

    await handle_business_message(
        message,
        session_manager=session_manager,
        provider_clients={"openai": client},
    )

    session_key = build_business_session_key("business-123", 456)
    session_manager.get_or_create_session.assert_called_once_with(session_key)
    session_manager.get_model_provider.assert_called_once_with(session_key)
    client.process_message.assert_awaited_once_with(session, "Hello")
    message.reply.assert_awaited_once()


@pytest.mark.asyncio
async def test_business_reply_request_contains_business_connection_id():
    bot = AsyncMock()
    message = Message.model_validate(
        {
            "message_id": 10,
            "date": 0,
            "chat": {"id": 456, "type": "private"},
            "from": {"id": 789, "is_bot": False, "first_name": "Guest"},
            "text": "Hello",
            "business_connection_id": "business-123",
        },
        context={"bot": bot},
    )

    await send_long_message(message, "Secretary reply")

    request = bot.await_args.args[0]
    assert isinstance(request, SendMessage)
    assert request.chat_id == 456
    assert request.business_connection_id == "business-123"
    assert request.reply_parameters.message_id == 10


@pytest.mark.asyncio
async def test_business_message_without_connection_id_is_ignored():
    message = make_business_message(business_connection_id=None)
    session_manager = MagicMock()
    client = AsyncMock()

    await handle_business_message(
        message,
        session_manager=session_manager,
        provider_clients={"openai": client},
    )

    session_manager.get_or_create_session.assert_not_called()
    client.process_message.assert_not_awaited()
    message.reply.assert_not_awaited()


@pytest.mark.parametrize("is_enabled", [True, False])
@pytest.mark.asyncio
async def test_business_connection_lifecycle_is_safe(is_enabled):
    connection = SimpleNamespace(
        id="business-123",
        user=SimpleNamespace(id=321),
        user_chat_id=654,
        is_enabled=is_enabled,
        rights=SimpleNamespace(can_reply=True),
    )

    await handle_business_connection(connection)


@pytest.mark.asyncio
async def test_edited_and_deleted_business_updates_are_noops():
    edited = make_business_message()
    deleted = SimpleNamespace(
        business_connection_id="business-123",
        chat=SimpleNamespace(id=456),
        message_ids=[10, 11],
    )

    await handle_edited_business_message(edited)
    await handle_deleted_business_messages(deleted)

    edited.reply.assert_not_awaited()
