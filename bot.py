import asyncio
import json
import os
import random
import tomllib
from openai import OpenAI, RateLimitError, NotFoundError
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes
from upstash_redis.asyncio import Redis

with open("config.toml", "rb") as _f:
    _config = tomllib.load(_f)

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]

ALLOWED_USERNAMES = set(
    u.strip().lower()
    for u in os.environ.get("ALLOWED_USERNAMES", "").split(",")
    if u.strip()
)
ALLOWED_USER_IDS = set(
    int(i.strip())
    for i in os.environ.get("ALLOWED_USER_IDS", "").split(",")
    if i.strip()
)

client_ai = OpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
)

redis = Redis(
    url=os.environ["UPSTASH_REDIS_REST_URL"],
    token=os.environ["UPSTASH_REDIS_REST_TOKEN"],
)

SYSTEM_PROMPT = _config["prompt"]["system"].strip()
MODELS = _config["models"]["fallback"]
CHARS_PER_SECOND = _config["bot"]["chars_per_second"]
MAX_HISTORY = _config["bot"]["max_history"]


async def get_history(user_id: int) -> list:
    data = await redis.get(f"tg-secretary:history:{user_id}")
    return json.loads(data) if data else []


async def save_history(user_id: int, history: list) -> None:
    await redis.set(f"tg-secretary:history:{user_id}", json.dumps(history))


def is_allowed(update: Update) -> bool:
    if "*" in ALLOWED_USERNAMES:
        return True
    user = update.effective_user
    username = (user.username or "").lower()
    return username in ALLOWED_USERNAMES or user.id in ALLOWED_USER_IDS


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я секретарь.")


async def call_ai(messages: list) -> str:
    for model in MODELS:
        for attempt in range(2):
            try:
                response = client_ai.chat.completions.create(
                    model=model,
                    max_tokens=1000,
                    messages=messages,
                )
                if response.choices and response.choices[0].message.content:
                    return response.choices[0].message.content
                continue
            except RateLimitError:
                if attempt == 0:
                    await asyncio.sleep(15)
                continue
            except NotFoundError:
                break  # try next model
    return "Сервис временно недоступен, попробуйте через минуту."


async def simulate_typing(context, chat_id: int, total_seconds: float, business_connection_id: str | None = None) -> None:
    elapsed = 0.0
    while elapsed < total_seconds:
        await context.bot.send_chat_action(
            chat_id=chat_id,
            action="typing",
            business_connection_id=business_connection_id,
        )
        step = min(4.0, total_seconds - elapsed)
        await asyncio.sleep(step)
        elapsed += step


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return

    message = update.effective_message
    if not message or not message.text:
        return

    user_id = update.effective_user.id
    user_text = message.text
    business_connection_id = getattr(message, "business_connection_id", None)

    history = await get_history(user_id)
    history.append({"role": "user", "content": user_text})

    await context.bot.send_chat_action(
        chat_id=message.chat_id,
        action="typing",
        business_connection_id=business_connection_id,
    )

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history
    reply_text = await call_ai(messages)

    speed = CHARS_PER_SECOND * random.uniform(0.8, 1.2)
    typing_seconds = len(reply_text) / speed
    await simulate_typing(context, message.chat_id, typing_seconds, business_connection_id)

    history.append({"role": "assistant", "content": reply_text})
    if len(history) > MAX_HISTORY:
        history = history[-MAX_HISTORY:]
    await save_history(user_id, history)

    await message.reply_text(reply_text)


def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.UpdateType.BUSINESS_MESSAGE, handle_message))
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
