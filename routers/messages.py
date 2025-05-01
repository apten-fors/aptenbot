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

    # Add logging for debugging
    logger.info(f"Using model provider: {model_provider}")

    if model_provider == "anthropic":
        logger.info("Using Anthropic (Claude) client for processing")
        reply = await claude_client.process_message(session, user_message)
    else:
        logger.info("Using OpenAI client for processing")
        reply = await openai_client.process_message(session, user_message)

    await message.answer(reply)

@router.message((F.chat.type == "group") | (F.chat.type == "supergroup"), F.text)
async def handle_group_message(message: Message, session_manager, openai_client, claude_client):
    bot_username = (await message.bot.me()).username
    bot_id = (await message.bot.me()).id
    message_text = message.text or "" # Ensure message_text is not None

    # Check if the message is a direct command /ask (processed separately)
    if message_text.startswith("/ask"):
        logger.debug("Ignoring message starting with /ask in group message handler.")
        return

    # --- Check if the bot should process this message ---
    bot_mentioned = False
    is_reply_to_bot = False

    # Check for @username mention
    if f"@{bot_username}" in message_text:
        bot_mentioned = True
        logger.debug("Bot mentioned by username.")

    # Check for entity mention
    if not bot_mentioned and message.entities:
        for entity in message.entities:
            if entity.type == "mention" and message_text[entity.offset:entity.offset+entity.length] == f"@{bot_username}":
                bot_mentioned = True
                logger.debug("Bot mentioned by entity.")
                break
            elif entity.type == "text_mention" and entity.user and entity.user.id == bot_id:
                bot_mentioned = True
                logger.debug("Bot mentioned by text_mention entity.")
                break

    # Check if this is a reply to a bot message
    if message.reply_to_message and message.reply_to_message.from_user and (
        message.reply_to_message.from_user.id == bot_id or
        message.reply_to_message.from_user.username == bot_username
    ):
        is_reply_to_bot = True
        logger.debug("Message is a reply to the bot.")

    # If the bot is neither mentioned nor replied to, ignore the message
    if not bot_mentioned and not is_reply_to_bot:
        logger.debug("Ignoring group message: No mention and not a reply to the bot.")
        return
    # --- End Check ---

    user_id = message.from_user.id
    user_message = message_text # Start with the full text

    # If the bot was mentioned, remove the mention for processing
    if bot_mentioned:
        user_message = user_message.replace(f"@{bot_username}", "").strip()
        logger.debug(f"Removed mention, message to process: '{user_message}'")

    # If this is a reply to the bot, add context from the replied message
    # Prepend context only if it's a reply and the message text isn't empty
    if is_reply_to_bot and message.reply_to_message.text and user_message:
        replied_text = message.reply_to_message.text
        user_message = f"Context: {replied_text}\n\nQuestion: {user_message}"
        logger.debug(f"Added context from reply. Message to process: '{user_message}'")
    elif is_reply_to_bot and not user_message:
        # If it's a reply but the reply text itself is empty (e.g., just a sticker reply)
        # We might still want to process it if the original message had text
        if message.reply_to_message.text:
             user_message = f"Context: {message.reply_to_message.text}\n\nQuestion: [User replied without text] What do you think about this?"
             logger.debug("Reply had no text, created default question with context.")
        else: # Reply to a message without text (e.g. photo) - might need specific handling?
             logger.debug("Reply to a non-text message without text in reply - ignoring for now.")
             return # Or maybe process based on original message type?

    if not user_message:
        logger.debug("After processing mentions/replies, message is empty. Ignoring.")
        return

    logger.info(f"Processing group message/reply: '{user_message}'")

    session = session_manager.get_or_create_session(user_id)
    model_provider = session_manager.get_model_provider(user_id)

    try:
        if model_provider == "anthropic":
            reply = await claude_client.process_message(session, user_message)
        else:
            reply = await openai_client.process_message(session, user_message)

        await message.reply(reply) # Use reply to keep context in group chat
        logger.info("Successfully processed and replied in group.")
    except Exception as e:
        logger.error(f"Error processing group message via AI client: {e}", exc_info=True)
        await message.reply("Sorry, I encountered an error trying to process that.")
