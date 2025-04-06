# AptenBot: Multi-AI Telegram Bot

AptenBot is an intelligent, AI-powered chatbot designed for Telegram users. It leverages OpenAI's GPT models and Anthropic's Claude models to provide advanced conversational AI capabilities. AptenBot allows users to interact with it in private chats and groups, and also offers features like Instagram video downloading and image generation. The bot verifies that users are subscribed to a specified Telegram channel before allowing them to interact with it.

## Key Features

- **Multi-AI Support**: Choose between OpenAI (GPT-4o, etc.) and Anthropic (Claude) models for conversations
- **Model Selection**: Switch between different AI models with the `/set provider` command
- **Image Understanding**: Send images with questions for AI analysis in both private and group chats
- **Instagram Video Download**: Download Instagram videos with the `/insta` command
- **Image Generation**: Create images from text descriptions with the `/img` command
- **Conversation Context**: Maintain conversation history with reply functionality
- **Telegram Group and Private Chat Support**: Works in both group chats and private conversations
- **Subscription Validation**: Ensures users are subscribed to a specified Telegram channel before accessing features
- **Session Management**: Maintains context and conversation continuity with automatic expiry after 1 hour

## Prerequisites

Before you can use AptenBot, ensure you have the following:

- A valid OpenAI API key
- A valid Anthropic API key (for Claude features)
- A valid Telegram bot token
- An optional Black Forest Labs API key (for image generation)
- The required Python libraries installed

## Environment Variables

The bot uses the following environment variables for configuration:

- `OPENAI_API_KEY`: Your OpenAI API key
- `ANTHROPIC_API_KEY`: Your Anthropic API key
- `TG_BOT_TOKEN`: Your Telegram bot token
- `CHANNEL_ID`: The Telegram channel ID where users need to be subscribed (default: `@korobo4ka_xoroni`)
- `OPENAI_MODEL`: The default OpenAI model to use (default: `gpt-4o-mini`)
- `ANTHROPIC_MODEL`: The default Anthropic model to use (default: `claude-3-5-haiku-20241022`)
- `DEFAULT_MODEL_PROVIDER`: The default AI provider to use (default: `openai`)
- `BFL_API_KEY`: Black Forest Labs API key (for image generation)
- `LOG_LEVEL`: Logging level (default: `INFO`)
- `SYSTEM_PROMPT`: Custom system prompt for AI models (default: `You are a helpful assistant.`)

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/aptenbot.git
cd aptenbot
```

### 2. Install Dependencies

Install the required Python libraries:

```bash
pip install -r requirements.txt
```

### 3. Set Environment Variables

Set up the necessary environment variables:

```bash
export OPENAI_API_KEY='your_openai_api_key'
export ANTHROPIC_API_KEY='your_anthropic_api_key'
export TG_BOT_TOKEN='your_telegram_bot_token'
export CHANNEL_ID='@your_channel_id'
# Optional environment variables
export BFL_API_KEY='your_black_forest_labs_api_key'
export OPENAI_MODEL='gpt-4o-mini'
export ANTHROPIC_MODEL='claude-3-5-haiku-20241022'
export DEFAULT_MODEL_PROVIDER='openai'
```

### 4. Run the Bot

Run the bot:

```bash
python main.py
```

The bot will begin polling for messages on Telegram.

## Bot Commands

- `/start` or `/help`: Initiates a conversation with the bot and displays usage instructions
- `/ask [question]`: Ask questions in groups or private chats
- `/reset`: Resets the current conversation session to start fresh
- `/insta [Reels url]`: Downloads Instagram videos from the provided link
- `/img [text prompt]`: Generates an image based on the text prompt (requires BFL_API_KEY)
- `/set provider [openai/claude]`: Changes the AI model provider between OpenAI and Claude

## Usage

### Private Chat Interaction

For private conversations, send a message directly to AptenBot. The bot will respond based on your message if you're subscribed to the required channel. You can:

1. Send text messages to get AI responses
2. Send images with captions to get image analysis
3. Reply to the bot's messages to maintain context in the conversation

### Group Chat Interaction

In group chats, you need to use specific commands:

1. Use `/ask [question]` to ask the bot a question
2. Send photos with `/ask [question]` in the caption for image analysis
3. Reply to the bot's messages to continue the conversation

### Changing AI Models

You can switch between OpenAI and Claude models:

```
/set provider openai   # Switch to OpenAI (default: gpt-4o-mini)
/set provider claude   # Switch to Claude (default: claude-3-5-haiku-20241022)
```

## Deployment

The repository includes Docker support for easy deployment:

```bash
docker build -t aptenbot .
docker run -d --name aptenbot \
  -e OPENAI_API_KEY='your_openai_api_key' \
  -e ANTHROPIC_API_KEY='your_anthropic_api_key' \
  -e TG_BOT_TOKEN='your_telegram_bot_token' \
  -e CHANNEL_ID='@your_channel_id' \
  aptenbot
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
