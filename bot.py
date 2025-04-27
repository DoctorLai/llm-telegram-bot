import time
import os
import openai
import yaml
import logging
import time
import requests
from dotenv import load_dotenv
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, MessageHandler, filters, CallbackQueryHandler, Application

# Configure logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("Starting the bot...")

# Load environment variables
load_dotenv()

logger.info("Loaded environment variables...")

# Load the config.yaml file
with open("config.yaml", "r") as config_file:
    config = yaml.safe_load(config_file)

# Function to expand environment variables in the configuration
def expand_env_vars(config):
    if isinstance(config, dict):
        return {key: expand_env_vars(value) for key, value in config.items()}
    elif isinstance(config, list):
        return [expand_env_vars(item) for item in config]
    elif isinstance(config, str):
        return os.path.expandvars(config)
    return config

# Expand the environment variables in the loaded config
config = expand_env_vars(config)

logger.info("Expanded environment variables in config...")

# Access LLM API URLs
providers = config["llms"]["providers"]
default_model = config["llms"]["default_model"]

# Set OpenAI API key
openai.api_key = providers["openai"]["api_key"]

# Set Grok API key
grok_api_key = providers["grok"]["api_key"]

# Create the Telegram bot
telegram_token = config["telegram"]["token"]
if not telegram_token:
    raise ValueError("Telegram bot token is missing!")

app = Application.builder().token(telegram_token).build()

# Memory cache to store user conversations
user_memory = {}
# Rate-limiting dictionary (to track user query times)
last_query_time = {}

# Use the new API format for chat completions
def get_openai_response(prompt):
    try:
        response = openai.Completion.create(
            model=providers["openai"]["model"],
            messages=[
                {"role": "system", "content": providers["openai"]["role"]},
                {"role": "user", "content": prompt}  # User's input message
            ],
            max_tokens=providers["openai"]["max_tokens"],
            temperature=providers["openai"]["temperature"],
            api_base=providers["openai"]["api_url"],
        )
        return response['choices'][0]['message']['content']
    except Exception as e:
        return f"Error: {str(e)}"

def get_response(model_name, prompt):
    try:
        if model_name == "openai":
            response = get_openai_response(prompt)
            return response

        elif model_name == "grok":
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {grok_api_key}"
            }
            payload = {
                "messages": [
                    {"role": "system", "content": providers["grok"]["role"]},
                    {"role": "user", "content": prompt}
                ],
                "model": providers["grok"]["model"],
                "stream": False,
                "temperature": providers["grok"]["temperature"],
                "max_tokens": providers["grok"]["max_tokens"],
            }
            response = requests.post(providers["grok"]["api_url"], headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

        else:
            return f"Unknown model: {model_name}"

    except Exception as e:
        return f"Error: {str(e)}"

async def start(update: Update, context):
    welcome_message = (
        "Hello! I'm your AI assistant.\n\n"
        "You can use the following commands:\n"
        "/start - Welcome message\n"
        "/help - Bot instructions\n"
        "/ping - Check if the bot is online\n"
        "/ask [model] [prompt] - Ask me something (e.g., /ask openai What is AI?)\n"
        "I support inline buttons for retry, new ask, and clear memory.\n\n"
        "To get started, just type /ask followed by your question.\n"
        "You can also use /help to see the available commands.\n\n"
        "Please note that I have a rate limit of " + str(config["rate_limit"]) + " seconds between queries.\n"
        "If you have any questions, feel free to ask!\n\n"
        "This telegram bot is open source and available on GitHub: https://github.com/DoctorLai/llm-telegram-bot\n"
        "Considering buying me a coffee? You can do so here: https://buymeacoffee.com/y0BtG5R\n"
    )
    await update.message.reply_text(welcome_message, reply_to_message_id=update.message.message_id)

async def help(update: Update, context):
    help_message = (
        "Here are some commands you can use:\n"
        "/start - Welcome message and bot instructions\n"
        "/help - This help message\n"
        "/ping - Check if the bot is online\n"
        "/ask [model] [prompt] - Ask a question to the bot\n"
        #"Inline Buttons for retry, new ask, and clear memory supported."
    )
    await update.message.reply_text(help_message, reply_to_message_id=update.message.message_id)

async def ping(update: Update, context):
    # Record the current time before sending the message
    start_time = time.time()

    # Send the "Pong!" response
    await update.message.reply_text("Pong!")

    # Calculate latency after sending the "Pong!" response
    latency_ms = (time.time() - start_time) * 1000  # Convert to milliseconds

    logger.info(f"Latency: {latency_ms:.2f} ms")

    # Reply with "Pong!" and the latency
    await update.message.reply_text(f"Pong! This message had a latency of {latency_ms:.2f} ms.", reply_to_message_id=update.message.message_id)

async def ask(update: Update, context):
    user_id = update.message.from_user.id
    args = context.args

    logger.info(f"User {user_id} asked: {' '.join(args)}")

    if args:
        # Rate limiting
        current_time = time.time()
        if user_id in last_query_time and current_time - last_query_time[user_id] < config["rate_limit"]:
            logger.info(f"User {user_id} is rate-limited. Last query time: {last_query_time[user_id]}")
            await update.message.reply_text("You must wait " + str(config["rate_limit"]) + " seconds before asking again.", reply_to_message_id=update.message.message_id)
            return
        last_query_time[user_id] = current_time

        # Check if first arg is a model
        model = args[0].lower()
        prompt = " ".join(args[1:]) if model in providers else " ".join(args)
        if model not in providers:
            model = default_model

        await update.message.reply_text("...typing")

        # Save prompt to user memory
        if user_id not in user_memory:
            user_memory[user_id] = []

        user_memory[user_id].append({"role": "user", "content": prompt, "model": model})

        # Get model response
        response = get_response(model, prompt)

        user_memory[user_id].append({"role": "assistant", "content": response, "model": model})

        logger.info(f"User {user_id} received response: {response}")
        await update.message.reply_text(response, reply_to_message_id=update.message.message_id)

    else:
        logger.info(f"User {user_id} did not provide a prompt.")
        await update.message.reply_text("Please provide a prompt after /ask.", reply_to_message_id=update.message.message_id)

# async def retry(update: Update, context):
#     query = update.callback_query
#     await query.answer()
#     user_id = query.from_user.id
#     if user_id in user_memory and len(user_memory[user_id]) > 1:
#         last_user_input = user_memory[user_id][-2]
#         model = last_user_input.get("model", default_model)
#         prompt = last_user_input.get("content", "")
#         response = get_response(model, prompt)
#         await query.message.reply_text(response)
#     else:
#         await query.message.reply_text("No previous question to retry.", reply_to_message_id=update.message.message_id)

# async def new_ask(update: Update, context):
#     await update.callback_query.message.reply_text("Please ask a new question with /ask [model] [prompt].")

# async def clear_memory(update: Update, context):
#     user_id = update.callback_query.from_user.id
#     if user_id in user_memory:
#         del user_memory[user_id]
#         await update.callback_query.message.reply_text("Your memory has been cleared.", reply_to_message_id=update.message.message_id)
#     else:
#         await update.callback_query.message.reply_text("No memory to clear.", reply_to_message_id=update.message.message_id)

# async def inline_buttons(update: Update, context):
#     keyboard = [
#         [InlineKeyboardButton("Retry", callback_data="retry"),
#          InlineKeyboardButton("New Ask", callback_data="new_ask"),
#          InlineKeyboardButton("Clear Memory", callback_data="clear_memory")]
#     ]
#     reply_markup = InlineKeyboardMarkup(keyboard)
#     await update.message.reply_text("What would you like to do?", reply_markup=reply_markup)

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", help))
app.add_handler(CommandHandler("ping", ping))
app.add_handler(CommandHandler("ask", ask))
#app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, inline_buttons))
#app.add_handler(CallbackQueryHandler(retry, pattern="retry"))
#app.add_handler(CallbackQueryHandler(new_ask, pattern="new_ask"))
#app.add_handler(CallbackQueryHandler(clear_memory, pattern="clear_memory"))

if __name__ == "__main__":
    app.run_polling()
