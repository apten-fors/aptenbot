from aiogram import Router, F
from aiogram.types import Message
import asyncio
from utils.logging_config import logger

router = Router()
media_groups = {}
media_group_locks = {}

@router.message(F.chat.type == "private", F.photo)
async def handle_private_photo(message: Message, session_manager, openai_client, claude_client):
    user_id = message.from_user.id

    # Check if message is part of a media group
    if message.media_group_id:
        media_group_id = message.media_group_id
        logger.debug(f"Media group ID: {media_group_id}")

        # Create lock for this media group if it doesn't exist
        if media_group_id not in media_group_locks:
            media_group_locks[media_group_id] = asyncio.Lock()

        async with media_group_locks[media_group_id]:
            if media_group_id not in media_groups:
                media_groups[media_group_id] = {
                    'messages': [message],
                    'processed': False
                }

                # Schedule processing of the media group
                async def process_media_group():
                    await asyncio.sleep(2)  # Give time for all images to be received
                    async with media_group_locks[media_group_id]:
                        if not media_groups[media_group_id]['processed']:
                            messages = media_groups[media_group_id]['messages']
                            caption = None

                            # Use the caption from the first message or any message with a caption
                            for msg in messages:
                                if msg.caption:
                                    caption = msg.caption
                                    break

                            if caption and caption.startswith("/ask"):
                                caption = caption.replace("/ask", "", 1).strip()

                            if not caption:
                                caption = "What is in this image?"

                            file_urls = []
                            for message in messages:
                                if message.photo:
                                    file = await message.bot.get_file(message.photo[-1].file_id)
                                    file_urls.append(file.file_path)

                            session = session_manager.get_or_create_session(user_id)
                            model_provider = session_manager.get_model_provider(user_id)

                            if model_provider == "anthropic":
                                reply = await claude_client.process_message_with_image(session, caption, file_urls)
                            else:
                                reply = await openai_client.process_message_with_image(session, caption, file_urls)

                            await messages[0].answer(reply)
                            media_groups[media_group_id]['processed'] = True

                asyncio.create_task(process_media_group())
            else:
                media_groups[media_group_id]['messages'].append(message)
    else:
        # Single image handling
        caption = message.caption or "What is in this image?"
        if caption.startswith("/ask"):
            caption = caption.replace("/ask", "", 1).strip()
        file = await message.bot.get_file(message.photo[-1].file_id)
        file_url = file.file_path

        session = session_manager.get_or_create_session(user_id)
        model_provider = session_manager.get_model_provider(user_id)

        if model_provider == "anthropic":
            reply = await claude_client.process_message_with_image(session, caption, [file_url])
        else:
            reply = await openai_client.process_message_with_image(session, caption, [file_url])

        await message.answer(reply)

@router.message((F.chat.type == "group") | (F.chat.type == "supergroup"), F.photo & F.caption.startswith("/ask"))
async def handle_group_photo_ask(message: Message, session_manager, openai_client, claude_client):
    user_id = message.from_user.id

    # If it's a single photo with /ask command
    if not message.media_group_id:
        caption = message.caption.replace('/ask', '').strip()
        file = await message.bot.get_file(message.photo[-1].file_id)
        file_url = file.file_path

        session = session_manager.get_or_create_session(user_id)
        model_provider = session_manager.get_model_provider(user_id)

        if model_provider == "anthropic":
            reply = await claude_client.process_message_with_image(session, caption, [file_url])
        else:
            reply = await openai_client.process_message_with_image(session, caption, [file_url])

        await message.reply(reply)
        return

    # If part of a media group, process with group handler
    media_group_id = message.media_group_id

    # Create lock for this media group if it doesn't exist
    if media_group_id not in media_group_locks:
        media_group_locks[media_group_id] = asyncio.Lock()

    async with media_group_locks[media_group_id]:
        if media_group_id not in media_groups:
            media_groups[media_group_id] = {
                'messages': [message],
                'processed': False
            }

            # Schedule processing after a delay
            async def process_media_group():
                await asyncio.sleep(2)  # Wait for 2 seconds
                async with media_group_locks[media_group_id]:
                    if media_group_id in media_groups and not media_groups[media_group_id]['processed']:
                        group_data = media_groups[media_group_id]
                        messages = group_data['messages']

                        # Find message with /ask command
                        caption = None
                        for msg in messages:
                            if msg.caption and msg.caption.startswith('/ask'):
                                caption = msg.caption.replace('/ask', '').strip()
                                break

                        logger.debug(f"Processing media group {media_group_id}. Messages count: {len(messages)}")
                        logger.debug(f"Final caption: {caption}")

                        if not caption:
                            await messages[0].reply("Please add /ask command with your question")
                            return

                        # Process all photos
                        file_urls = []
                        for message in messages:
                            if message.photo:
                                file = await message.bot.get_file(message.photo[-1].file_id)
                                file_urls.append(file.file_path)

                        session = session_manager.get_or_create_session(user_id)
                        model_provider = session_manager.get_model_provider(user_id)

                        if model_provider == "anthropic":
                            reply = await claude_client.process_message_with_image(session, caption, file_urls)
                        else:
                            reply = await openai_client.process_message_with_image(session, caption, file_urls)

                        await messages[0].reply(reply)

                        # Mark as processed
                        media_groups[media_group_id]['processed'] = True

            # Start the delayed processing
            asyncio.create_task(process_media_group())
        else:
            # Just add this message to the group for processing later
            media_groups[media_group_id]['messages'].append(message)
            # Update caption if this message has the /ask command
            if message.caption and message.caption.startswith('/ask'):
                caption = message.caption.replace('/ask', '').strip()
                media_groups[media_group_id]['caption'] = caption
