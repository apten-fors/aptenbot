from aiogram import Router, F
from aiogram.types import Message, FSInputFile
from aiogram.filters import Command
from config import OPENAI_MODEL, ANTHROPIC_MODEL, OPENAI_MODELS, ANTHROPIC_MODELS
import re
from models.models_list import MODELS, DEFAULT_MODEL

router = Router()

@router.message(Command("start"))
async def handle_start(message: Message, session_manager):
    user_id = message.from_user.id
    session_manager.get_or_create_session(user_id)

    welcome_message = (
        "👋 Hello! I'm a helpful bot with AI capabilities.\n\n"
        "In private chat, you can:\n"
        "• Just send me a message to chat\n"
        "• Send an image for analysis\n"
        "• Use /model to switch between AI models\n"
        "• Use /new to start a new conversation\n\n"
        "In group chats, you can:\n"
        "• Tag me in a message to get my attention\n"
        "• Start your message with /ask to ask me a question\n"
        "• Send images with the /ask command in the caption\n\n"
        "Currently supported models: GPT-4o, Claude 3 Opus, Claude 3 Sonnet, Claude 3 Haiku"
    )

    await message.answer(welcome_message)

@router.message(Command("help"))
async def handle_help(message: Message):
    help_message = (
        "📚 <b>Available Commands</b>\n\n"
        "/start - Introduction to the bot\n"
        "/new - Start a new conversation\n"
        "/model - Select an AI model\n"
        "/help - Show this help message\n\n"
        "<b>Using the bot:</b>\n"
        "• In <b>private chat</b>, just send messages directly\n"
        "• In <b>groups</b>, tag me or use /ask to get my attention\n"
        "• <b>Image analysis</b> works in both private and group chats\n"
        "• <b>Group chats</b>: Add /ask when posting images for analysis\n\n"
        "Each user has their own conversation history that persists until you start a new conversation with /new"
    )

    await message.answer(help_message, parse_mode="HTML")

@router.message(Command("new"))
async def handle_new(message: Message, session_manager):
    user_id = message.from_user.id
    session_manager.create_new_session(user_id)
    await message.answer("🔄 Starting a new conversation. Previous messages have been cleared.")

@router.message(Command("model"))
async def handle_model_command(message: Message, session_manager):
    user_id = message.from_user.id

    # Create provider options
    model_options = ""
    current_provider = session_manager.get_model_provider(user_id)

    for i, model in enumerate(MODELS, start=1):
        current = "✓ " if model['provider'] == current_provider else ""
        model_options += f"{i}. {current}{model['name']}\n"

    response = (
        "🤖 <b>Select an AI provider:</b>\n\n"
        f"{model_options}\n"
        "To select a provider, reply with its number (e.g., '1')"
    )

    # Create or update model selection state
    session = session_manager.get_or_create_session(user_id)
    session.update_state("selecting_model")

    await message.answer(response, parse_mode="HTML")

@router.message(F.text.regexp(r"^[1-9]\d*$") & F.chat.type == "private")
async def handle_model_selection(message: Message, session_manager):
    user_id = message.from_user.id

    # Check if user is in model selection state
    session = session_manager.get_or_create_session(user_id)
    if session.get_state() != "selecting_model":
        return

    try:
        selected_idx = int(message.text) - 1
        if 0 <= selected_idx < len(MODELS):
            selected_model = MODELS[selected_idx]
            # Устанавливаем только провайдер, а не конкретную модель
            session.update_model(selected_model['provider'])
            await message.answer(
                f"✅ Provider switched to <b>{selected_model['name']}</b>.",
                parse_mode="HTML"
            )
        else:
            await message.answer("❌ Invalid selection. Please choose a valid number from the list.")
    except ValueError:
        await message.answer("❌ Please enter a valid number.")
    finally:
        # Clear selection state
        session.clear_state()

@router.message(Command("img"))
async def handle_img_command(message: Message, openai_client):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Please provide a prompt for image generation.")
        return

    prompt = args[1]
    await message.answer("Generating image...")

    try:
        async with openai_client.get_client() as client:
            response = await client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size="1024x1024",
                quality="standard",
                n=1,
            )
        image_url = response.data[0].url
        await message.answer_photo(image_url)
    except Exception as e:
        await message.answer(f"Error generating image: {str(e)}")

@router.message(Command("insta"))
async def cmd_insta(message: Message, instaloader_client):
    user_id = message.from_user.id
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Usage: /insta <link to instagram video>")
        return
    user_message = args[1]
    url_pattern = r'https?://(?:www\.)?instagram\.com/[^\s]+'
    match = re.search(url_pattern, user_message)
    if not match:
        await message.answer("Please provide a valid Instagram URL")
        return
    instagram_url = match.group(0)
    ok, path = instaloader_client.download_video(instagram_url)
    if not ok:
        await message.answer(f"Something went wrong: {path}")
        return

    # Используем FSInputFile вместо открытия файла напрямую
    video_file = FSInputFile(path)
    await message.answer_video(video_file)

@router.message(Command("ask"))
async def handle_ask_command(message: Message, session_manager, openai_client, claude_client):
    user_id = message.from_user.id

    # Extract the actual question (remove the /ask part)
    question = message.text.replace("/ask", "", 1).strip()
    if not question:
        await message.answer("Please provide a question after /ask")
        return

    session = session_manager.get_or_create_session(user_id)
    provider = session.get_provider()

    # Process the question using the appropriate provider
    if provider == "anthropic":
        response = await session.process_claude_message(question, claude_client)
    else:
        response = await session.process_openai_message(question, openai_client)

    await message.answer(response)