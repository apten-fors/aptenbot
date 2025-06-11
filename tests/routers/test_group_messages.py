import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.types import Message, User, Chat, ChatMemberOwner, ChatMemberMember, MessageEntity

# Assuming routers are in 'project_root/routers/'
# Adjust import paths if your project structure is different
from routers.messages import handle_group_message
from routers.commands import handle_ask_command # For Scenario 2.3
from config import CHANNEL_ID # For any CHANNEL_ID related logic if needed, though not directly here

TEST_BOT_USERNAME = "TestBot"
TEST_BOT_ID = 987654321
MOCKED_AI_RESPONSE = "Mocked AI response"

@pytest.fixture
def mock_bot_instance():
    """Mocks the bot instance (message.bot.me())"""
    bot_user = User(id=TEST_BOT_ID, is_bot=True, first_name=TEST_BOT_USERNAME, username=TEST_BOT_USERNAME)
    bot_instance = AsyncMock()
    bot_instance.me = AsyncMock(return_value=bot_user)
    # Mock get_chat_member here as it's used by handle_ask_command
    bot_instance.get_chat_member = AsyncMock(return_value=ChatMemberMember(user=User(id=12345, is_bot=False, first_name="Regular User"), status="member"))
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
    client.process_message = AsyncMock(return_value=MOCKED_AI_RESPONSE)
    return client

@pytest.fixture
def mock_claude_client():
    client = AsyncMock()
    client.process_message = AsyncMock(return_value="Mocked Claude response")
    return client

@pytest.fixture
def group_chat():
    return Chat(id=-100123456789, type="group", title="Test Group")

@pytest.fixture
def regular_user():
    return User(id=12345, is_bot=False, first_name="Test User")

@pytest.fixture
def another_user():
    return User(id=54321, is_bot=False, first_name="Another User")

# --- Tests for routers.messages.handle_group_message ---

@pytest.mark.asyncio
async def test_direct_mention_in_group_processed(
    mock_bot_instance, mock_session_manager, mock_openai_client, mock_claude_client, group_chat, regular_user
):
    """Test: Direct @bot_username mention in a group message IS processed."""
    message_text = f"@{TEST_BOT_USERNAME} hello there!"
    # Simulate entity for mention
    entities = [MessageEntity(type="mention", offset=0, length=len(f"@{TEST_BOT_USERNAME}"))]
    message = Message(
        message_id=100,
        chat=group_chat,
        from_user=regular_user,
        text=message_text,
        entities=entities,
        bot=mock_bot_instance
    )
    message.reply = AsyncMock()

    await handle_group_message(
        message,
        session_manager=mock_session_manager,
        openai_client=mock_openai_client,
        claude_client=mock_claude_client
    )

    message.reply.assert_called_once_with(MOCKED_AI_RESPONSE)
    mock_openai_client.process_message.assert_called_once()
    # Check that the actual message passed to AI is "hello there!"
    args, _ = mock_openai_client.process_message.call_args
    assert args[1] == "hello there!"
    mock_claude_client.process_message.assert_not_called()

@pytest.mark.asyncio
async def test_reply_to_bot_in_group_processed(
    mock_bot_instance, mock_session_manager, mock_openai_client, mock_claude_client, group_chat, regular_user
):
    """Test: Replying to the bot's own message IS processed."""
    bot_user_for_reply = User(id=TEST_BOT_ID, is_bot=True, first_name=TEST_BOT_USERNAME, username=TEST_BOT_USERNAME)
    bot_previous_message_text = "I am a bot."
    bot_previous_message = Message(
        message_id=100, chat=group_chat, from_user=bot_user_for_reply, text=bot_previous_message_text
    )

    user_reply_text = "Oh really?"
    message = Message(
        message_id=101,
        chat=group_chat,
        from_user=regular_user,
        text=user_reply_text,
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

    message.reply.assert_called_once_with(MOCKED_AI_RESPONSE)
    mock_openai_client.process_message.assert_called_once()
    # Check context formatting
    args, _ = mock_openai_client.process_message.call_args
    expected_processed_message = f"Context from my previous message: \"{bot_previous_message_text}\"\n\nUser's question/reply: \"{user_reply_text}\""
    assert args[1] == expected_processed_message
    mock_claude_client.process_message.assert_not_called()

@pytest.mark.asyncio
async def test_mention_in_reply_to_another_user_processed(
    mock_bot_instance, mock_session_manager, mock_openai_client, mock_claude_client, group_chat, regular_user, another_user
):
    """Test: Bot mention in a reply to another user's message IS processed."""
    original_poster_message_text = "This is User A's original message."
    original_poster_message = Message(
        message_id=200, chat=group_chat, from_user=another_user, text=original_poster_message_text
    )

    reply_text_with_mention = f"@{TEST_BOT_USERNAME} what do you think about this?"
    # Simulate entity for mention
    entities = [MessageEntity(type="mention", offset=0, length=len(f"@{TEST_BOT_USERNAME}"))]
    message = Message(
        message_id=201,
        chat=group_chat,
        from_user=regular_user, # User B is replying
        text=reply_text_with_mention,
        reply_to_message=original_poster_message, # Replying to User A's message
        entities=entities,
        bot=mock_bot_instance
    )
    message.reply = AsyncMock()

    await handle_group_message(
        message,
        session_manager=mock_session_manager,
        openai_client=mock_openai_client,
        claude_client=mock_claude_client
    )

    message.reply.assert_called_once_with(MOCKED_AI_RESPONSE)
    mock_openai_client.process_message.assert_called_once()
    # The context from another user's message is NOT added in the current implementation,
    # only the mention is stripped. If context from the replied-to message (from another user)
    # was desired, the handle_group_message logic would need to change.
    # Current logic: bot_mentioned=True, is_reply_to_bot=False.
    # So, it strips the mention and processes: "what do you think about this?"
    args, _ = mock_openai_client.process_message.call_args
    assert args[1] == "what do you think about this?"
    mock_claude_client.process_message.assert_not_called()

@pytest.mark.asyncio
async def test_general_group_message_ignored(
    mock_bot_instance, mock_session_manager, mock_openai_client, mock_claude_client, group_chat, regular_user
):
    """Test: A general group message (no mention, no reply, not /ask) is IGNORED."""
    message = Message(
        message_id=300,
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

@pytest.mark.asyncio
async def test_ask_command_in_group_ignored_by_message_handler(
    mock_bot_instance, mock_session_manager, mock_openai_client, mock_claude_client, group_chat, regular_user
):
    """Test: /ask command in Group is IGNORED by handle_group_message."""
    ask_message_text_group = "/ask How are you in a group?"
    group_ask_message = Message(
        message_id=400,
        chat=group_chat,
        from_user=regular_user,
        text=ask_message_text_group,
        bot=mock_bot_instance,
        entities=[MessageEntity(type='bot_command', offset=0, length=4)]
    )
    group_ask_message.reply = AsyncMock()

    await handle_group_message(
        group_ask_message,
        session_manager=mock_session_manager,
        openai_client=mock_openai_client,
        claude_client=mock_claude_client
    )
    group_ask_message.reply.assert_not_called()
    mock_openai_client.process_message.assert_not_called()
    mock_claude_client.process_message.assert_not_called()

@pytest.mark.asyncio
async def test_ask_command_in_group_processed_by_command_handler(
    mock_bot_instance, mock_session_manager, mock_openai_client, mock_claude_client, group_chat, regular_user
):
    """Test: /ask command in Group IS processed by handle_ask_command."""
    ask_message_text_group = "/ask How are you in a group?"
    group_ask_message = Message(
        message_id=401, # Different ID from previous test
        chat=group_chat,
        from_user=regular_user,
        text=ask_message_text_group,
        bot=mock_bot_instance,
        entities=[MessageEntity(type='bot_command', offset=0, length=4)]
    )
    group_ask_message.reply = AsyncMock()

    # Reset relevant mocks that might have been called if this message object was reused by mistake
    mock_openai_client.process_message.reset_mock()
    mock_claude_client.process_message.reset_mock()
    mock_openai_client.process_message.return_value = "AI reply to /ask in group" # Specific return for this test

    mock_state = AsyncMock()
    mock_state.get_state = AsyncMock(return_value=None)
    mock_state.set_state = AsyncMock()
    mock_state.update_data = AsyncMock()
    mock_state.clear = AsyncMock()

    await handle_ask_command(
        group_ask_message,
        session_manager=mock_session_manager,
        openai_client=mock_openai_client,
        claude_client=mock_claude_client,
        state=mock_state,
        bot=mock_bot_instance
    )

    mock_openai_client.process_message.assert_called_once()
    args, _ = mock_openai_client.process_message.call_args
    # handle_ask_command strips the "/ask " part
    assert args[1] == "How are you in a group?"
    group_ask_message.reply.assert_called_once_with("AI reply to /ask in group")

# Note: The `mock_bot_instance` fixture now includes a default mock for `get_chat_member`
# as it's used by `handle_ask_command`. This simplifies individual tests.
# MessageEntity objects are now used for simulating entities like mentions and commands.
# Assertions for what exactly is passed to `process_message` are added for clarity.
# Renamed tests from "*_ignored" to "*_processed" where behavior changed.
# Test for `/ask` command now split into two:
#   - `test_ask_command_in_group_ignored_by_message_handler`
#   - `test_ask_command_in_group_processed_by_command_handler`
# to clearly distinguish the responsibilities.
