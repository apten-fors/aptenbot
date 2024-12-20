# AptenBot: AI-Powered Chatbot for Telegram

AptenBot is an intelligent, AI-powered chatbot designed for Telegram users. It leverages OpenAI's ChatGPT model to provide conversational AI capabilities. AptenBot allows users to interact with it and engage in conversations. Additionally, the bot checks if users are subscribed to a specified Telegram channel before allowing them to interact with the bot.

AptenBot uses Python's `python-telegram-bot` library and integrates with OpenAI's API for natural language understanding. The bot operates in private chats and supports commands like starting, asking questions, and resetting conversations.

## Key Features

- **AI-Powered Conversations**: Powered by OpenAI's GPT models, AptenBot provides intelligent and helpful responses to user queries.
- **Telegram Group and Private Chat Support**: While AptenBot can operate in group chats, it encourages the use of private chats for direct interactions.
- **Subscription Validation**: AptenBot ensures users are subscribed to a specified Telegram channel before they can access its features.
- **Session Management**: User sessions are tracked, allowing AptenBot to maintain context and conversation continuity. Sessions can be reset as needed.
- **Retry Logic**: The bot includes built-in retry logic to handle Telegram API errors, ensuring robust communication.

## Prerequisites

Before you can use AptenBot, ensure you have the following:

- A valid OpenAI API key
- A valid Telegram bot token
- The required Python libraries installed (`openai`, `python-telegram-bot`, `python-json-logger`, etc.)

## Environment Variables

The bot uses environment variables for configuration:

- `OPENAI_API_KEY`: Your OpenAI API key for GPT model access.
- `TG_BOT_TOKEN`: Your Telegram bot token.
- `CHANNEL_ID`: The Telegram channel ID where users need to be subscribed.
- `OPENAI_MODEL`: (Optional) The OpenAI model to use (default: `gpt-4o-mini`).

## How to Use

### 1. Setup Environment

Make sure the necessary environment variables are set up:

```bash
export OPENAI_API_KEY='your_openai_api_key'
export TG_BOT_TOKEN='your_telegram_bot_token'
export CHANNEL_ID='@your_channel_id'
```

### 2. Install Dependencies

Install the required Python libraries:

```bash
pip install -r requirements.txt
```

### 3. Run the Bot

Run the bot:

```bash
python main.py
```

The bot will begin polling for messages on Telegram. Using specific commands, you can interact with the bot via private messages or group chats.

### 4. Bot Commands

- `/start or /help`: Initiates a conversation with the bot. Informs the user how to interact with the bot.
- `/ask [question]`: The user can ask questions in groups or private chats.
- `/reset`: Resets the current conversation session for the user, allowing a fresh start.
- `/insta [Reels url]`: Download reels from Instagram by link
- `/img [text prompt]`: Generate image from text via black forest API. (Not available in public)

### 5. Private Chat Interaction

For private conversations, send a message directly to AptenBot. The bot will respond based on your message if you’re subscribed to the required channel. If you're not subscribed, the bot will prompt you to join the channel.

### 6. Group Chat Interaction

Use the `/ask` command in group chats followed by your question. The bot does not process free-text messages in groups to reduce noise.

## Future Features

AptenBot is set to evolve with more functionalities like advanced conversation handling, integration with external APIs, and user-specific customization options.
