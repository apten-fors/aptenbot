import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.types import Message, User, Chat
from middlewares.subscription import SubscriptionMiddleware
from config import CHANNEL_ID # Assuming CHANNEL_ID is accessible for tests

# Ensure CHANNEL_ID is a string for consistent comparison in tests
TEST_CHANNEL_ID = str(CHANNEL_ID)

@pytest.fixture
def mock_bot():
    bot = MagicMock()
    # If bot.id is accessed, ensure it's available
    bot.id = 123456789 # Example bot ID
    return bot

@pytest.fixture
def mock_subscription_manager():
    manager = AsyncMock()
    manager.is_subscriber = AsyncMock()
    return manager

@pytest.fixture
def mock_handler():
    handler = AsyncMock(return_value="handler_called")
    return handler

@pytest.fixture
def subscription_middleware(mock_subscription_manager):
    return SubscriptionMiddleware(subscription_manager=mock_subscription_manager)

@pytest.mark.asyncio
async def test_scenario_1_1_user_not_subscribed(subscription_middleware, mock_subscription_manager, mock_handler, mock_bot):
    """Scenario 1.1: User Not Subscribed"""
    user = User(id=123, is_bot=False, first_name="Test")
    chat = Chat(id=456, type="private")
    event_message = Message(
        message_id=1,
        chat=chat,
        from_user=user,
        text="Hello",
        bot=mock_bot # Pass the bot mock here
    )
    event_message.answer = AsyncMock() # Mock the answer method on the message instance

    mock_subscription_manager.is_subscriber.return_value = False
    data = {"bot": mock_bot} # Simulate data passed by dispatcher

    result = await subscription_middleware(handler=mock_handler, event=event_message, data=data)

    mock_subscription_manager.is_subscriber.assert_called_once_with(user.id, mock_bot)
    expected_denial_message = f"To use this bot, you need to be a subscriber of the {TEST_CHANNEL_ID} channel."
    event_message.answer.assert_called_once_with(expected_denial_message)
    mock_handler.assert_not_called()
    assert result is None # Middleware should return, not the handler's result

@pytest.mark.asyncio
async def test_scenario_1_2_user_subscribed(subscription_middleware, mock_subscription_manager, mock_handler, mock_bot):
    """Scenario 1.2: User Subscribed"""
    user = User(id=123, is_bot=False, first_name="Test")
    chat = Chat(id=456, type="private")
    event_message = Message(
        message_id=1,
        chat=chat,
        from_user=user,
        text="Hello",
        bot=mock_bot
    )
    event_message.answer = AsyncMock()
    mock_subscription_manager.is_subscriber.return_value = True
    data = {"bot": mock_bot}

    result = await subscription_middleware(handler=mock_handler, event=event_message, data=data)

    mock_subscription_manager.is_subscriber.assert_called_once_with(user.id, mock_bot)
    event_message.answer.assert_not_called()
    mock_handler.assert_called_once_with(event_message, data)
    assert result == "handler_called"

@pytest.mark.asyncio
async def test_scenario_1_3_message_from_configured_channel(subscription_middleware, mock_subscription_manager, mock_handler, mock_bot):
    """Scenario 1.3: Message from Configured Channel via sender_chat"""
    # Case 1.3a: sender_chat.id is CHANNEL_ID, from_user is also present (e.g. admin)
    admin_user = User(id=789, is_bot=False, first_name="ChannelAdmin")
    sender_chat_obj = Chat(id=int(TEST_CHANNEL_ID), type="channel", title="Test Channel") # Ensure ID is int if CHANNEL_ID is str
    group_chat = Chat(id=987, type="group", title="Linked Group") # Message is in a group, but sent by channel

    event_message_admin_sent = Message(
        message_id=1,
        chat=group_chat, # Message appears in the group
        sender_chat=sender_chat_obj, # Identifies actual sender as the channel
        from_user=admin_user, # Telegram also provides user if admin sends on behalf of channel
        text="Channel Update",
        bot=mock_bot
    )
    event_message_admin_sent.answer = AsyncMock()
    data = {"bot": mock_bot}

    # Even if is_subscriber would return False for admin_user.id, it shouldn't be checked, or its result ignored
    mock_subscription_manager.is_subscriber.return_value = False 

    result = await subscription_middleware(handler=mock_handler, event=event_message_admin_sent, data=data)

    # is_subscriber should NOT be called for the admin_user.id in this specific flow
    # because the sender_chat check takes precedence.
    # Or, if it is called due to from_user being present before sender_chat is checked,
    # the bypass must still occur. The current middleware logic checks sender_chat first.
    mock_subscription_manager.is_subscriber.assert_not_called() # Ideal, assuming sender_chat is checked first
    event_message_admin_sent.answer.assert_not_called()
    mock_handler.assert_called_once_with(event_message_admin_sent, data)
    assert result == "handler_called"

    # Reset mocks for next sub-case
    mock_handler.reset_mock()
    mock_subscription_manager.reset_mock() # reset all mocks on manager
    mock_subscription_manager.is_subscriber = AsyncMock(return_value=False) # re-assign async mock

    # Case 1.3b: sender_chat.id is CHANNEL_ID, from_user is None (e.g. automated channel message)
    event_message_channel_sent = Message(
        message_id=2,
        chat=group_chat,
        sender_chat=sender_chat_obj,
        from_user=None, # No specific user, just the channel
        text="Automated Channel Post",
        bot=mock_bot
    )
    event_message_channel_sent.answer = AsyncMock() # Not strictly needed here as no denial expected

    result = await subscription_middleware(handler=mock_handler, event=event_message_channel_sent, data=data)
    
    mock_subscription_manager.is_subscriber.assert_not_called()
    mock_handler.assert_called_once_with(event_message_channel_sent, data)
    assert result == "handler_called"

@pytest.mark.asyncio
async def test_non_message_event_passes(subscription_middleware, mock_handler, mock_bot):
    """Test that non-Message events are passed through without checks."""
    non_message_event = MagicMock() # Simulate some other TelegramObject
    data = {"bot": mock_bot}

    result = await subscription_middleware(handler=mock_handler, event=non_message_event, data=data)
    
    mock_handler.assert_called_once_with(non_message_event, data)
    assert result == "handler_called"

@pytest.mark.asyncio
async def test_message_without_from_user_or_sender_chat_passes(subscription_middleware, mock_handler, mock_bot):
    """Test that Message events without from_user and not matching CHANNEL_ID sender_chat pass."""
    chat = Chat(id=456, type="private")
    event_message = Message(
        message_id=1,
        chat=chat,
        from_user=None, # No from_user
        sender_chat=None, # No sender_chat
        text="System Message?",
        bot=mock_bot
    )
    data = {"bot": mock_bot}

    result = await subscription_middleware(handler=mock_handler, event=event_message, data=data)
    
    mock_handler.assert_called_once_with(event_message, data)
    assert result == "handler_called"

@pytest.mark.asyncio
async def test_message_from_other_channel_acts_as_user_message(subscription_middleware, mock_subscription_manager, mock_handler, mock_bot):
    """Message from another channel (not THE CHANNEL_ID) should be treated like a user message,
       but since from_user is None and sender_chat.id != CHANNEL_ID, it passes through.
       This confirms the logic of the 'else' case in the middleware for messages.
    """
    other_channel_sender = Chat(id=int(TEST_CHANNEL_ID) + 1, type="channel", title="Another Channel")
    group_chat = Chat(id=987, type="group", title="Linked Group")
    event_message = Message(
        message_id=1,
        chat=group_chat,
        sender_chat=other_channel_sender, # Message from a channel, but not THE configured one
        from_user=None, # No specific user
        text="Post from other channel",
        bot=mock_bot
    )
    data = {"bot": mock_bot}
    event_message.answer = AsyncMock()

    result = await subscription_middleware(handler=mock_handler, event=event_message, data=data)

    # It should not call is_subscriber because from_user is None
    mock_subscription_manager.is_subscriber.assert_not_called()
    # It should not send a denial message
    event_message.answer.assert_not_called()
    # It should pass to the handler
    mock_handler.assert_called_once_with(event_message, data)
    assert result == "handler_called"

# To run these tests, you would typically use `pytest` in the terminal.
# Example: `pytest tests/middlewares/test_subscription.py`
# Ensure config.py with CHANNEL_ID is in a place accessible by PYTHONPATH
# or mock/patch CHANNEL_ID directly in tests if it's problematic.
# For simplicity, this test assumes CHANNEL_ID can be imported.
# One way to ensure TEST_CHANNEL_ID is used:
# with patch('middlewares.subscription.CHANNEL_ID', TEST_CHANNEL_ID):
#    # run test
# This is more robust if config.py is complex or has side effects.
# For this example, direct import is assumed to work.
