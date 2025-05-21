import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.types import Message, User, Chat, ChatMemberOwner, ChatMemberMember

# Assuming routers are in 'project_root/routers/'
# Adjust import paths if your project structure is different
from routers.messages import handle_group_message
from routers.commands import handle_ask_command # For Scenario 2.3
from config import CHANNEL_ID # For any CHANNEL_ID related logic if needed, though not directly here

TEST_BOT_USERNAME = "TestBot"
TEST_BOT_ID = 987654321

@pytest.fixture
def mock_bot_instance():
    """Mocks the bot instance (message.bot.me())"""
    bot_user = User(id=TEST_BOT_ID, is_bot=True, first_name=TEST_BOT_USERNAME, username=TEST_BOT_USERNAME)
    bot_instance = AsyncMock()
    bot_instance.me = AsyncMock(return_value=bot_user)
    return bot_instance

@pytest.fixture
def mock_session_manager():
    manager = MagicMock()
    manager.get_or_create_session = MagicMock(return_value="session_obj")
    manager.get_model_provider = MagicMock(return_value="openai") # Default mock provider
    return manager

@pytest.fixture
def mock_openai_client():
    client = AsyncMock()
    client.process_message = AsyncMock(return_value="Mocked AI response")
    return client

@pytest.fixture
def mock_claude_client(): # Though not used in /ask by default, good to have
    client = AsyncMock()
    client.process_message = AsyncMock(return_value="Mocked Claude response")
    return client

@pytest.fixture
def group_chat():
    return Chat(id=-100123456789, type="group", title="Test Group")

@pytest.fixture
def regular_user():
    return User(id=12345, is_bot=False, first_name="Test User")

# --- Tests for routers.messages.handle_group_message ---

@pytest.mark.asyncio
async def test_scenario_2_1_bot_mention_in_group_ignored(
    mock_bot_instance, mock_session_manager, mock_openai_client, mock_claude_client, group_chat, regular_user
):
    """Scenario 2.1: Bot Mention in Group - No Response from handle_group_message"""
    message_text = f"@{TEST_BOT_USERNAME} hello there!"
    message = Message(
        message_id=100,
        chat=group_chat,
        from_user=regular_user,
        text=message_text,
        bot=mock_bot_instance
    )
    message.reply = AsyncMock()

    # Directly call handle_group_message
    await handle_group_message(
        message, 
        session_manager=mock_session_manager, 
        openai_client=mock_openai_client, 
        claude_client=mock_claude_client
    )

    # Assert that reply was NOT called because handle_group_message should ignore non-/ask
    message.reply.assert_not_called()
    # Assert AI client was NOT called by this handler
    mock_openai_client.process_message.assert_not_called()
    mock_claude_client.process_message.assert_not_called()

@pytest.mark.asyncio
async def test_scenario_2_2_bot_reply_in_group_ignored(
    mock_bot_instance, mock_session_manager, mock_openai_client, mock_claude_client, group_chat, regular_user
):
    """Scenario 2.2: Bot Reply in Group - No Response from handle_group_message"""
    bot_previous_message = Message(
        message_id=100, chat=group_chat, from_user=User(id=TEST_BOT_ID, is_bot=True, first_name=TEST_BOT_USERNAME, username=TEST_BOT_USERNAME), text="I am a bot."
    )
    message = Message(
        message_id=101,
        chat=group_chat,
        from_user=regular_user,
        text="Oh really?",
        reply_to_message=bot_previous_message,
        bot=mock_bot_instance
    )
    message.reply = AsyncMock()

    await handle_group_message(
        message, 
        session_manager=mock_session_manager, 
        openai_client=mock_openai_client, 
        claude_client=mock_claude_client
    )

    message.reply.assert_not_called()
    mock_openai_client.process_message.assert_not_called()
    mock_claude_client.process_message.assert_not_called()

@pytest.mark.asyncio
async def test_general_group_message_ignored(
    mock_bot_instance, mock_session_manager, mock_openai_client, mock_claude_client, group_chat, regular_user
):
    """Test that a general group message (no mention, no reply, not /ask) is ignored."""
    message = Message(
        message_id=102,
        chat=group_chat,
        from_user=regular_user,
        text="Just a random message.",
        bot=mock_bot_instance
    )
    message.reply = AsyncMock()

    await handle_group_message(
        message, 
        session_manager=mock_session_manager, 
        openai_client=mock_openai_client, 
        claude_client=mock_claude_client
    )

    message.reply.assert_not_called()
    mock_openai_client.process_message.assert_not_called()
    mock_claude_client.process_message.assert_not_called()

# --- Test for routers.commands.handle_ask_command in group context ---
# This implicitly tests that handle_group_message ignores /ask,
# and handle_ask_command processes it.

@pytest.mark.asyncio
async def test_scenario_2_3_ask_command_in_group_processed_by_command_handler(
    mock_bot_instance, mock_session_manager, mock_openai_client, mock_claude_client, group_chat, regular_user
):
    """Scenario 2.3: /ask command in Group - Response Expected from handle_ask_command"""
    
    # Part 1: Verify handle_group_message ignores /ask
    ask_message_text_group = "/ask How are you in a group?"
    group_ask_message = Message(
        message_id=200,
        chat=group_chat, # Group context
        from_user=regular_user,
        text=ask_message_text_group,
        bot=mock_bot_instance,
        entities=[{'type': 'bot_command', 'offset': 0, 'length': 4}] # Simulate command entity
    )
    group_ask_message.reply = AsyncMock()
    group_ask_message.answer = AsyncMock() # For commands, .answer might also be used by some frameworks/handlers

    # Call handle_group_message and ensure it does nothing with /ask
    await handle_group_message(
        group_ask_message, 
        session_manager=mock_session_manager, 
        openai_client=mock_openai_client, 
        claude_client=mock_claude_client
    )
    group_ask_message.reply.assert_not_called() # handle_group_message should not reply
    mock_openai_client.process_message.assert_not_called() # handle_group_message should not call AI
    mock_claude_client.process_message.assert_not_called()

    # Reset mocks for AI clients before calling the command handler
    mock_openai_client.process_message.reset_mock()
    mock_claude_client.process_message.reset_mock()
    mock_openai_client.process_message.return_value = "AI reply to /ask in group"


    # Part 2: Verify handle_ask_command processes /ask in a group
    # We need to mock get_chat_member for admin check in handle_ask_command
    # For this test, assume user is NOT an admin to simplify, or mock admin status if needed for full coverage
    mock_bot_instance.get_chat_member = AsyncMock(return_value=ChatMemberMember(user=regular_user, status="member"))

    # Create a new state mock for the command handler
    mock_state = AsyncMock()
    mock_state.get_state = AsyncMock(return_value=None) # Default to no state
    mock_state.set_state = AsyncMock()
    mock_state.update_data = AsyncMock()
    mock_state.clear = AsyncMock()

    await handle_ask_command(
        group_ask_message, # Use the same message object
        session_manager=mock_session_manager,
        openai_client=mock_openai_client,
        claude_client=mock_claude_client, # Pass claude_client as well
        state=mock_state, # Pass the mock_state
        bot=mock_bot_instance # Pass the bot instance
    )

    # Assert AI client (OpenAI by default in session_manager mock) was called by handle_ask_command
    mock_openai_client.process_message.assert_called_once()
    # Assert a reply was sent by handle_ask_command
    group_ask_message.reply.assert_called_once_with("AI reply to /ask in group")


# To run these tests:
# pytest tests/routers/test_group_messages.py
# Ensure that the routers and config are importable (PYTHONPATH setup).
# The structure of these tests assumes that handle_group_message is registered for general text
# and handle_ask_command is registered for /ask commands, and the dispatcher routes correctly.
# These tests directly call the handlers to verify their internal logic given specific inputs.
# Testing the dispatcher itself would require more complex Aiogram-specific testing utilities.
#
# Note on CHANNEL_ID: The original task description for handle_group_message mentioned CHANNEL_ID,
# but the implementation change for handle_group_message was to ignore all non-/ask messages.
# So CHANNEL_ID logic is primarily in SubscriptionMiddleware, not directly in handle_group_message's new logic.
# The handle_ask_command might have its own considerations for CHANNEL_ID if it needs to behave
# differently when the bot is used in its own channel's linked group, but that's outside current scope.
# For now, CHANNEL_ID is imported but not actively used in these specific router tests.
#
# For `handle_ask_command`, it includes admin checks using `message.bot.get_chat_member`.
# This is mocked in `test_scenario_2_3_ask_command_in_group_processed_by_command_handler`.
# If `handle_ask_command` had more complex logic based on admin status, further test cases would be needed.
# The provided test assumes a non-admin user for simplicity of the AI call path.
#
# Also, `handle_ask_command` uses `FSMContext` (state). A mock for this is added.
# The `bot` argument has been added to `handle_ask_command` call as it's used internally.
#
# The `claude_client` is passed to `handle_ask_command` for completeness, matching its signature.
#
# Added `entities` to the mock message for `/ask` command as Aiogram relies on this for command detection.
# `message.bot` is now properly `mock_bot_instance` in `handle_ask_command` call.
# `message.answer` is also mocked for `group_ask_message` as command handlers might use it.
# `mock_bot_instance.get_chat_member` is added to simulate the admin check.
# `claude_client` argument added to `handle_ask_command` call.
# `state` argument added to `handle_ask_command` call.
# `bot` argument added to `handle_ask_command` call.
