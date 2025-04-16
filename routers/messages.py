from aiogram import Router, F
from aiogram.types import Message
from utils.logging_config import logger

router = Router()

@router.message(F.chat.type == "private", F.text)
async def handle_private_message(message: Message, session_manager, openai_client, claude_client):
    user_id = message.from_user.id

    user_message = message.text
    logger.info(f"Received message from user: {user_message}")

    session = session_manager.get_or_create_session(user_id)
    model_provider = session_manager.get_model_provider(user_id)

    if model_provider == "claude":
        reply = await claude_client.process_message(session, user_message)
    else:
        reply = await openai_client.process_message(session, user_message)

    await message.answer(reply)

@router.message((F.chat.type == "group") | (F.chat.type == "supergroup"), F.text)
async def handle_group_message(message: Message, session_manager, openai_client, claude_client):
    bot_username = (await message.bot.me()).username
    if f"@{bot_username}" not in message.text:
        return

    user_id = message.from_user.id

    message_text = message.text
    logger.debug(f"Received group message: '{message_text}', checking for mention of @{bot_username}")

    # Remove the bot mention from the message
    user_message = message_text.replace(f"@{bot_username}", "").strip()

    # If this is a reply to another message, include that message's text as context
    if message.reply_to_message and message.reply_to_message.text:
        replied_text = message.reply_to_message.text
        user_message = f"Context: {replied_text}\n\nQuestion: {user_message}"

    logger.info(f"Processing mention with message: {user_message}")

    session = session_manager.get_or_create_session(user_id)
    model_provider = session_manager.get_model_provider(user_id)

    if model_provider == "claude":
        reply = await claude_client.process_message(session, user_message)
    else:
        reply = await openai_client.process_message(session, user_message)

    await message.reply(reply)

@router.message(F.reply_to_message)
async def handle_reply(message: Message, session_manager, openai_client, claude_client):
    user_id = message.from_user.id
    bot_username = (await message.bot.me()).username
    message_text = message.text

    # Check if the bot is mentioned in the reply
    bot_mentioned = f"@{bot_username}" in message_text

    # If this is a group chat and the bot is not mentioned, ignore the message
    if message.chat.type in ['group', 'supergroup'] and not bot_mentioned:
        return

    # If it's a reply to the bot's message, process it
    if message.reply_to_message and message.reply_to_message.from_user.username == bot_username:
        # If the bot is mentioned, remove the mention from the message text
        if bot_mentioned:
            message_text = message_text.replace(f"@{bot_username}", "").strip()

        logger.info(f"Processing reply to bot: {message_text}")

        # Get or create a session for this user
        session = session_manager.get_or_create_session(user_id)
        model_provider = session_manager.get_model_provider(user_id)

        # Process the message with the appropriate AI model
        if model_provider == "claude":
            reply = await claude_client.process_message(session, message_text)
        else:
            reply = await openai_client.process_message(session, message_text)

        await message.answer(reply)