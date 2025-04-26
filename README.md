![image](https://github.com/user-attachments/assets/957d966b-df81-4589-b12a-7c894277e05d)


# Telegram AI Bot

This is a Telegram bot that uses OpenAI (and other LLM providers) to answer questions, with support for rate limiting, retry functionality, inline buttons, chat continuity, and configurable API URLs. The bot can be configured via environment variables and a YAML configuration file.

You can add telegram bot here: https://t.me/justyy_llm_bot

Please consider buying me a coffee to support the development and running cost of the telegram bot:

<a rel="nofollow" href="http://steemyy.com/out/buymecoffee" target="_blank"><img src="https://user-images.githubusercontent.com/1764434/161362754-c45a85d3-5c80-4e10-b05c-62af49291d0b.png" alt="Buy me a Coffee"/></a>

---

## Features

- **Rate Limiting**: Users are limited to one query every 30 seconds.
- **Chat Continuity**: Memory cache stores user conversations for context.
- **Inline Buttons**: Allows retrying a query, asking a new question, or clearing memory.
- **Configurable OpenAI API URL**: Easily switch between different compatible LLM providers.
- **Typing Indicator**: Simulates a "typing..." message while processing the query.

---

## Commands

- `/start` - Sends a welcome message and bot instructions.
- `/help` - Displays the list of available commands.
- `!ping` - Checks if the bot is online.
- `!ask [model] [prompt]` - Ask a question to the bot (e.g., `!ask openai What is AI?`).
- Inline buttons:
  - **Retry**: Retry the previous query.
  - **New Ask**: Ask a new question.
  - **Clear Memory**: Clears the stored chat memory.

---

## Requirements

- **Python**: Version 3.8 or higher.
- **Telegram Bot API Token**: You can get it by creating a bot via [BotFather](https://core.telegram.org/bots#botfather).
- **OpenAI API Key**: You'll need a valid OpenAI API key.
- **Grok API Key (Optional)**: For using the Grok model.
- **Docker**: For running the bot in a containerized environment.

---

## Setup

### 1. Clone the repository

Clone this repository to your local machine:

```bash
git clone https://github.com/your-repo/telegram-ai-bot.git  
cd telegram-ai-bot
```

### 2. Configure Environment Variables

Create a `.env` file in the root of the project with the following variables:

```bash
YOUR_TELEGRAM_BOT_API_TOKEN=your_telegram_bot_token  
YOUR_OPENAI_API_KEY=your_openai_api_key  
YOUR_GROK_API_KEY=your_grok_api_key  
OPENAI_API_URL=https://api.gptapi.us/v1/chat/completions  # Example custom URL
```

### 3. Configure the `config.yaml`

In the [config.yaml](./config.yaml) file, specify your bot's settings and which LLM providers you wish to use (OpenAI by default):

```yaml
rate_limit: 10
telegram:
  token: ${YOUR_TELEGRAM_BOT_API_TOKEN}

llms:
  default_model: grok # can be 'openai' or 'grok'

  providers:
    openai:
      api_url:  https://api.openai.com/v1/chat/completions
      api_key: ${YOUR_OPENAI_API_KEY}
      model: gpt-3.5-turbo
      temperature: 0.7
      max_tokens: 1500
      role: "You are a helpful assistant (open ai). Answer the user's questions as accurately as possible. You are a large language model trained by OpenAI. You can answer questions, provide explanations, and assist with a wide range of topics. Your goal is to be helpful and informative. You are created by @justyy who is a steem witness."

    grok:
      api_url: https://api.x.ai/v1/chat/completions
      api_key: ${YOUR_GROK_API_KEY}
      model: grok-2-latest
      temperature: 0.7
      max_tokens: 1500
      role: "You are a helpful assistant (grok). Answer the user's questions as accurately as possible. You are a large language model trained by Grok. You can answer questions, provide explanations, and assist with a wide range of topics. Your goal is to be helpful and informative. You are created by @justyy who is a steem witness."    
```
---

## Running the Bot

### 1. Install Dependencies

Create a virtual environment (optional but recommended) and install the dependencies:

```bash
python -m venv venv  
source venv/bin/activate  # For Linux/macOS  
venv\Scripts\activate  # For Windows
pip install -r requirements.txt
```

### 2. Run the Bot

You can run the bot directly with the following command:

```bash
python bot.py
```

### 3. Run the Bot Using Docker

You can also run the bot in a Docker container. Follow these steps:

1. **Build the Docker Image:**

```bash
docker build -t telegram-bot .
```

2. **Run the Docker Container:**

```bash
docker run -d \
 --name telegram-bot \
 --env-file .env \
 -v `pwd`/config.yaml:/app/config.yaml \
telegram-bot
```

Specify `-d` to detach the container.

---

## Docker Setup (Optional)

### Dockerfile

The bot is containerized using Docker. The `Dockerfile` provided ensures that all dependencies are installed and the bot runs seamlessly.

```Dockerfile
FROM python:3.9-slim

# Set the working directory  
WORKDIR /app

# Copy the requirements file  
COPY requirements.txt .

# Install dependencies  
RUN pip install --no-cache-dir -r requirements.txt

# Copy the bot's source code  
COPY . .

# Set environment variables  
ENV TELEGRAM_API_TOKEN=${YOUR_TELEGRAM_BOT_API_TOKEN}  
ENV OPENAI_API_KEY=${YOUR_OPENAI_API_KEY}  
ENV GROK_API_KEY=${YOUR_GROK_API_KEY}  
ENV OPENAI_API_URL=${OPENAI_API_URL}

# Run the bot  
CMD ["python", "bot.py"]
```

---

## Troubleshooting

### 1. **Bot Not Responding**

- Double-check your `.env` file to ensure the correct values are set for your API tokens and URLs.
- Ensure that you have installed all required dependencies with `pip install -r requirements.txt`.

### 2. **Rate Limiting Issue**

If you're hitting rate limits for OpenAI or another API, make sure you’re not making too many requests in a short period of time (you’re limited to one request every 30 seconds per user).

### 3. **Memory Cache Clearing**

If you encounter issues with stored memory, use the **Clear Memory** inline button to reset the memory cache for a user.

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support me
If you like this and want to support me in continuous development, you can do the following:
- [Buy me a coffee](https://justyy.com/out/bmc)
- [Sponsor me](https://github.com/sponsors/DoctorLai)
- [Vote me as a witness](https://steemyy.com/witness-voting/?witness=justyy&action=approve)
- [Set me a Witness Proxy if you are too lazy to vote](https://steemyy.com/witness-voting/?witness=justyy&action=proxy)

<a rel="nofollow" href="http://steemyy.com/out/buymecoffee" target="_blank"><img src="https://user-images.githubusercontent.com/1764434/161362754-c45a85d3-5c80-4e10-b05c-62af49291d0b.png" alt="Buy me a Coffee"/></a>

---
