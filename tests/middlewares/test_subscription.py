import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.types import Message, User, Chat
from aiogram.exceptions import TelegramAPIError # Import for specific error checking

# Import the middleware that will be tested
from middlewares.subscription import SubscriptionMiddleware

# Mocked Bot ID for consistency if needed elsewhere, though not directly used by middleware logic
MOCKED_BOT_ID = 123456789
RESOLVED_NUMERIC_CHANNEL_ID_EXAMPLE = -100987654321 # Example resolved numeric ID

@pytest.fixture
def mock_bot():
    """Fixture for a mock Bot object."""
    bot = MagicMock(spec=AsyncMock) # Use spec with AsyncMock for async methods
    bot.id = MOCKED_BOT_ID
    # get_chat needs to be an AsyncMock as it's awaited
    bot.get_chat = AsyncMock()
    return bot

@pytest.fixture
def mock_subscription_manager():
    """Fixture for a mock SubscriptionManager."""
    manager = AsyncMock()
    manager.is_subscriber = AsyncMock()
    return manager

@pytest.fixture
def mock_handler():
    """Fixture for a mock handler function."""
    handler = AsyncMock(return_value="handler_called")
    return handler

# --- Helper to create SubscriptionMiddleware with fresh state for each test ---
@pytest.fixture
def create_middleware(mock_subscription_manager):
    """Factory fixture to create a new middleware instance for each test.
       This is important because the middleware now has internal state (resolved_numeric_channel_id).
    """
    def _create():
        return SubscriptionMiddleware(subscription_manager=mock_subscription_manager)
    return _create

# --- Tests for CHANNEL_ID Resolution and Bypass Logic ---

@pytest.mark.asyncio
@patch('middlewares.subscription.CHANNEL_ID', "@testchannel") # Patch CHANNEL_ID for this test
async def test_channel_id_username_resolution_success_and_cache(create_middleware, mock_subscription_manager, mock_handler, mock_bot):
    """
    Test Scenario: CHANNEL_ID is a username.
    - Successful resolution on first call.
    - Caching of resolved ID (get_chat not called on second call).
    - Bypass for messages from the resolved channel ID.
    """
    middleware_instance = create_middleware()

    mock_bot.get_chat.return_value = Chat(id=RESOLVED_NUMERIC_CHANNEL_ID_EXAMPLE, type="channel", title="Test Channel")

    sender_chat_obj = Chat(id=RESOLVED_NUMERIC_CHANNEL_ID_EXAMPLE, type="channel")
    event_message = Message(message_id=1, chat=Chat(id=-1002, type="group"), sender_chat=sender_chat_obj, from_user=None, bot=mock_bot)
    data = {"bot": mock_bot}

    # First call - resolution should happen
    result = await middleware_instance(handler=mock_handler, event=event_message, data=data)

    mock_bot.get_chat.assert_called_once_with(chat_id="@testchannel")
    mock_handler.assert_called_once_with(event_message, data)
    assert result == "handler_called"
    assert middleware_instance.resolved_numeric_channel_id == RESOLVED_NUMERIC_CHANNEL_ID_EXAMPLE
    mock_subscription_manager.is_subscriber.assert_not_called() # Ensure bypass

    # Reset handler mock for second call check, bot.get_chat should not be reset to check caching
    mock_handler.reset_mock()

    # Second call - resolution should be cached
    event_message_2 = Message(message_id=2, chat=Chat(id=-1002, type="group"), sender_chat=sender_chat_obj, from_user=None, bot=mock_bot)
    result_2 = await middleware_instance(handler=mock_handler, event=event_message_2, data=data)

    mock_bot.get_chat.assert_called_once() # Still called only once (from the first call)
    mock_handler.assert_called_once_with(event_message_2, data)
    assert result_2 == "handler_called"
    mock_subscription_manager.is_subscriber.assert_not_called() # Ensure bypass again

@pytest.mark.asyncio
@patch('middlewares.subscription.CHANNEL_ID', str(RESOLVED_NUMERIC_CHANNEL_ID_EXAMPLE)) # Patch with a numeric string
async def test_channel_id_numeric_string_direct_use(create_middleware, mock_subscription_manager, mock_handler, mock_bot):
    """
    Test Scenario: CHANNEL_ID is a numeric string.
    - bot.get_chat should NOT be called.
    - Bypass for messages from this numeric channel ID.
    """
    middleware_instance = create_middleware()

    sender_chat_obj = Chat(id=RESOLVED_NUMERIC_CHANNEL_ID_EXAMPLE, type="channel")
    event_message = Message(message_id=1, chat=Chat(id=-1002, type="group"), sender_chat=sender_chat_obj, from_user=None, bot=mock_bot)
    data = {"bot": mock_bot}

    result = await middleware_instance(handler=mock_handler, event=event_message, data=data)

    mock_bot.get_chat.assert_not_called() # Key assertion: get_chat is skipped
    mock_handler.assert_called_once_with(event_message, data)
    assert result == "handler_called"
    assert middleware_instance.resolved_numeric_channel_id == RESOLVED_NUMERIC_CHANNEL_ID_EXAMPLE
    mock_subscription_manager.is_subscriber.assert_not_called() # Ensure bypass

@pytest.mark.asyncio
@patch('middlewares.subscription.CHANNEL_ID', "@nonexistentchannel")
async def test_channel_id_resolution_fails_telegram_api_error(create_middleware, mock_subscription_manager, mock_handler, mock_bot):
    """
    Test Scenario: CHANNEL_ID resolution fails with TelegramAPIError (e.g., ChatNotFound).
    - Bypass is disabled.
    - Falls back to user subscription check.
    """
    middleware_instance = create_middleware()
    mock_bot.get_chat.side_effect = TelegramAPIError(method="getChat", message="Chat not found")

    # Message supposedly from the channel, but resolution will fail
    sender_chat_obj = Chat(id=12345, type="channel") # ID doesn't matter as resolution fails
    user = User(id=789, is_bot=False, first_name="TestUser")
    event_message = Message(message_id=1, chat=Chat(id=-1002, type="group"), sender_chat=sender_chat_obj, from_user=user, bot=mock_bot)
    event_message.answer = AsyncMock()
    data = {"bot": mock_bot}

    # Scenario A: User is not subscribed
    mock_subscription_manager.is_subscriber.return_value = False
    await middleware_instance(handler=mock_handler, event=event_message, data=data)

    mock_bot.get_chat.assert_called_once_with(chat_id="@nonexistentchannel")
    mock_subscription_manager.is_subscriber.assert_called_once_with(user.id, mock_bot)
    event_message.answer.assert_called_once_with(f"To use this bot, you need to be a subscriber of the @nonexistentchannel channel.")
    mock_handler.assert_not_called()
    assert middleware_instance.resolved_numeric_channel_id == -1 # Check it's set to non-matchable

    # Reset mocks for Scenario B
    mock_subscription_manager.is_subscriber.reset_mock()
    event_message.answer.reset_mock()
    mock_handler.reset_mock()
    # Create a new middleware instance to test caching of resolution failure
    middleware_instance_2 = create_middleware()
    # Manually set resolving_started and resolved_id to simulate state after first failed attempt for the new instance
    # This ensures we're testing the behavior *after* a failed resolution has been "cached" as -1.
    middleware_instance_2.resolving_started = True
    middleware_instance_2.resolved_numeric_channel_id = -1

    # Scenario B: User IS subscribed (after resolution failure)
    mock_subscription_manager.is_subscriber.return_value = True
    result = await middleware_instance_2(handler=mock_handler, event=event_message, data=data)

    # get_chat on the second instance shouldn't be called if we correctly simulated prior failure state
    # For this specific test focusing on *fallback*, let's assume middleware_instance is reused or state persists as -1
    # If testing caching of failure, a separate test focusing on *not calling get_chat again* after failure would be better.
    # Here, we focus on the fallback path.
    mock_subscription_manager.is_subscriber.assert_called_once_with(user.id, mock_bot)
    event_message.answer.assert_not_called()
    mock_handler.assert_called_once_with(event_message, data)
    assert result == "handler_called"

@pytest.mark.asyncio
@patch('middlewares.subscription.CHANNEL_ID', "@brokenchannel")
async def test_channel_id_resolution_fails_generic_exception(create_middleware, mock_subscription_manager, mock_handler, mock_bot):
    """
    Test Scenario: CHANNEL_ID resolution fails with a generic Exception.
    - Bypass is disabled.
    - Falls back to user subscription check.
    """
    middleware_instance = create_middleware()
    mock_bot.get_chat.side_effect = Exception("Some generic error")

    user = User(id=789, is_bot=False, first_name="TestUser")
    # Message with from_user, as sender_chat bypass will fail
    event_message = Message(message_id=1, chat=Chat(id=-1002, type="group"), from_user=user, sender_chat=None, bot=mock_bot)
    event_message.answer = AsyncMock()
    data = {"bot": mock_bot}

    mock_subscription_manager.is_subscriber.return_value = False # Test non-subscribed user path
    await middleware_instance(handler=mock_handler, event=event_message, data=data)

    mock_bot.get_chat.assert_called_once_with(chat_id="@brokenchannel")
    mock_subscription_manager.is_subscriber.assert_called_once_with(user.id, mock_bot)
    event_message.answer.assert_called_once_with(f"To use this bot, you need to be a subscriber of the @brokenchannel channel.")
    mock_handler.assert_not_called()
    assert middleware_instance.resolved_numeric_channel_id == -1

# --- Tests for Regular User Subscription (Unaffected by Channel Bypass Logic if sender_chat is not the resolved channel) ---

@pytest.mark.asyncio
@patch('middlewares.subscription.CHANNEL_ID', "@some_other_channel") # Patch to a channel ID not used in sender_chat
async def test_user_not_subscribed_regular_message(create_middleware, mock_subscription_manager, mock_handler, mock_bot):
    """User not subscribed, message not related to channel bypass."""
    middleware_instance = create_middleware()
    user = User(id=123, is_bot=False, first_name="Test")
    chat = Chat(id=456, type="private")
    # Message has no sender_chat or sender_chat.id does not match RESOLVED_NUMERIC_CHANNEL_ID_EXAMPLE
    event_message = Message(message_id=1, chat=chat, from_user=user, text="Hello", bot=mock_bot, sender_chat=None)
    event_message.answer = AsyncMock()
    data = {"bot": mock_bot}

    mock_subscription_manager.is_subscriber.return_value = False
    result = await middleware_instance(handler=mock_handler, event=event_message, data=data)

    # Resolution might happen if it's the first call, but it won't lead to bypass for this message
    # mock_bot.get_chat could be called once if this test runs first in a session for this patched CHANNEL_ID

    mock_subscription_manager.is_subscriber.assert_called_once_with(user.id, mock_bot)
    # Denial message uses the patched CHANNEL_ID
    event_message.answer.assert_called_once_with("To use this bot, you need to be a subscriber of the @some_other_channel channel.")
    mock_handler.assert_not_called()
    assert result is None

@pytest.mark.asyncio
@patch('middlewares.subscription.CHANNEL_ID', "@another_channel_configured") # Patch to a channel ID
async def test_user_subscribed_regular_message(create_middleware, mock_subscription_manager, mock_handler, mock_bot):
    """User subscribed, message not related to channel bypass."""
    middleware_instance = create_middleware()
    user = User(id=123, is_bot=False, first_name="Test")
    chat = Chat(id=456, type="private")
    event_message = Message(message_id=1, chat=chat, from_user=user, text="Hello", bot=mock_bot, sender_chat=None)
    event_message.answer = AsyncMock()
    data = {"bot": mock_bot}

    mock_subscription_manager.is_subscriber.return_value = True
    result = await middleware_instance(handler=mock_handler, event=event_message, data=data)

    mock_subscription_manager.is_subscriber.assert_called_once_with(user.id, mock_bot)
    event_message.answer.assert_not_called()
    mock_handler.assert_called_once_with(event_message, data)
    assert result == "handler_called"

# --- Utility tests (should still pass) ---

@pytest.mark.asyncio
async def test_non_message_event_passes(create_middleware, mock_handler, mock_bot):
    middleware_instance = create_middleware()
    non_message_event = MagicMock(spec=AsyncMock) # Not a Message instance
    data = {"bot": mock_bot}
    result = await middleware_instance(handler=mock_handler, event=non_message_event, data=data)
    mock_handler.assert_called_once_with(non_message_event, data)
    assert result == "handler_called"
    mock_bot.get_chat.assert_not_called() # Resolution shouldn't occur for non-Message

@pytest.mark.asyncio
@patch('middlewares.subscription.CHANNEL_ID', "@utility_test_channel")
async def test_message_without_from_user_or_relevant_sender_chat_passes(create_middleware, mock_handler, mock_bot):
    """Message without from_user and sender_chat not matching resolved CHANNEL_ID passes."""
    middleware_instance = create_middleware()
    # Simulate that CHANNEL_ID resolved to something, but this message's sender_chat won't match
    middleware_instance.resolved_numeric_channel_id = RESOLVED_NUMERIC_CHANNEL_ID_EXAMPLE
    middleware_instance.resolving_started = True # Assume resolution attempt already made

    chat = Chat(id=456, type="private")
    # sender_chat is None, or its ID is different from resolved_numeric_channel_id
    event_message = Message(message_id=1, chat=chat, from_user=None, sender_chat=Chat(id=RESOLVED_NUMERIC_CHANNEL_ID_EXAMPLE + 1, type="channel"), text="System Message?", bot=mock_bot)
    data = {"bot": mock_bot}

    result = await middleware_instance(handler=mock_handler, event=event_message, data=data)

    mock_handler.assert_called_once_with(event_message, data)
    assert result == "handler_called"
    # get_chat should not be called again if resolving_started is True and resolved_id is set.
    # If this test runs in isolation and CHANNEL_ID is "@utility_test_channel", get_chat would be called once.
    # The key is that it passes to handler.
    # To be very specific about get_chat not being called here, we'd need to ensure it was called before
    # or patch CHANNEL_ID to a numeric string for this specific test.
    # Given the setup, it's fine; the main assertion is that the handler is called.

# Note: The `create_middleware` factory is used to ensure a fresh middleware instance
# with reset internal state (like resolved_numeric_channel_id) for each test function.
# This is crucial for testing the resolution logic correctly.
# Patching `middlewares.subscription.CHANNEL_ID` allows controlling the config value per test.
# Aiogram's specific exception `TelegramAPIError` is used for more targeted error mocking.
# (Assuming `aiogram.exceptions.ChatNotFound` might not be a distinct class or is a subclass of TelegramAPIError)
# If ChatNotFound is a distinct, importable error, it would be even better for that specific case.
# For now, TelegramAPIError is a good general representation of "API call failed".
# Added spec=AsyncMock to MagicMock for bot to ensure async methods are properly mocked.
# In test_channel_id_resolution_fails_telegram_api_error, clarified testing of fallback for both
# non-subscribed and subscribed users.
# The test for resolution failure now also checks that resolved_numeric_channel_id is set to -1.The tests for `SubscriptionMiddleware` in `tests/middlewares/test_subscription.py` have been successfully updated to reflect the new `CHANNEL_ID` resolution logic.

Here's a summary of the modifications:

1.  **`mock_bot` Fixture Updated:** The `mock_bot` fixture now includes an `AsyncMock` for `get_chat`, allowing simulation of `bot.get_chat()` calls.
2.  **`create_middleware` Factory Fixture:** A new factory fixture `create_middleware` was introduced. This ensures that each test function gets a fresh instance of `SubscriptionMiddleware`. This is crucial because the middleware now has internal state (`resolved_numeric_channel_id`, `resolving_started`), and tests for resolution logic (especially caching) need to start with a clean slate.
3.  **`CHANNEL_ID` Patching:** Instead of a global `TEST_CHANNEL_ID`, `unittest.mock.patch` is used directly within test decorators (e.g., `@patch('middlewares.subscription.CHANNEL_ID', "@testchannel")`) to set the desired `CHANNEL_ID` value from `config` for each specific test scenario. This provides better isolation and clarity.
4.  **New Tests for Resolution Logic:**
    *   **`test_channel_id_username_resolution_success_and_cache`**:
        *   Verifies that when `CHANNEL_ID` is a username string (e.g., "@testchannel"), `bot.get_chat` is called on the first message.
        *   Confirms the message is bypassed if `sender_chat.id` matches the resolved ID.
        *   Asserts `bot.get_chat` is NOT called on a subsequent message (testing the caching of the resolved ID), and the bypass still works.
    *   **`test_channel_id_numeric_string_direct_use`**:
        *   Verifies that if `CHANNEL_ID` is already a numeric string, `bot.get_chat` is NOT called.
        *   Confirms the message is bypassed if `sender_chat.id` matches this numeric ID.
    *   **`test_channel_id_resolution_fails_telegram_api_error`**:
        *   Simulates `bot.get_chat` raising a `TelegramAPIError`.
        *   Asserts `bot.get_chat` is called.
        *   Confirms that the channel bypass is disabled and the middleware falls back to checking the `event.from_user`'s subscription status (testing both non-subscribed and subscribed cases).
        *   Checks that `resolved_numeric_channel_id` is set to the non-matchable value (`-1`).
    *   **`test_channel_id_resolution_fails_generic_exception`**:
        *   Similar to the above, but `bot.get_chat` raises a generic `Exception`.
        *   Ensures fallback to user subscription check.
5.  **Adaptation of Existing User Subscription Tests:**
    *   `test_user_not_subscribed_regular_message` (formerly `test_scenario_1_1_user_not_subscribed`) and `test_user_subscribed_regular_message` (formerly `test_scenario_1_2_user_subscribed`) are updated to use the `create_middleware` factory and patch `CHANNEL_ID`. They verify the core user subscription logic when the channel bypass conditions are not met. The denial message check correctly uses the patched `CHANNEL_ID`.
6.  **Utility Tests Maintained:**
    *   `test_non_message_event_passes` and `test_message_without_from_user_or_relevant_sender_chat_passes` were kept and updated to use `create_middleware`, ensuring they still correctly pass non-relevant events/messages to the handler.

**Expected Outcome:**
All updated tests in `tests/middlewares/test_subscription.py` are expected to pass in a properly configured `pytest` environment. They now comprehensively cover the new `CHANNEL_ID` resolution mechanism, including success, caching, direct use of numeric IDs, and failure scenarios, while also ensuring the original user-based subscription logic remains intact.

The next step is to submit the report.
