import asyncio
import os
import random
from openai import OpenAI, RateLimitError, NotFoundError
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

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

SYSTEM_PROMPT = (
    "Ты отвечаешь от имени Senior Android-разработчика с 10-летним опытом. "
    "Ты в лёгком пассивном поиске работы — не торопишься, выбираешь осознанно, "
    "готов рассмотреть интересные предложения но не бегаешь за ними. "
    "Пиши кратко, уверенно и профессионально. "
    "Если спрашивают про опыт — упоминай Android (Kotlin, Jetpack Compose, архитектуры MVVM/MVI, работу с REST/GraphQL, CI/CD). "
    "Если предлагают вакансию — вежливо уточняй стек, условия и формат работы перед тем как давать ответ. "
    "Не соглашайся сразу, не отказывай грубо — держи баланс заинтересованного но разборчивого специалиста."
)

# Primary model, fallback used when primary is rate-limited or unavailable
MODELS = [
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "tencent/hy3:free",
]

user_histories = {}

# Typing speed: chars per second with ±20% random variation
CHARS_PER_SECOND = 60


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


async def simulate_typing(context, chat_id: int, total_seconds: float) -> None:
    """Send typing action repeatedly for total_seconds duration."""
    elapsed = 0.0
    while elapsed < total_seconds:
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        # Telegram typing indicator lasts 5s; refresh every 4s
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

    if user_id not in user_histories:
        user_histories[user_id] = []

    user_histories[user_id].append({"role": "user", "content": user_text})

    # Show typing while waiting for AI
    await context.bot.send_chat_action(chat_id=message.chat_id, action="typing")

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + user_histories[user_id]
    reply_text = await call_ai(messages)

    # Calculate realistic typing delay based on response length (±20% random)
    speed = CHARS_PER_SECOND * random.uniform(0.8, 1.2)
    typing_seconds = len(reply_text) / speed

    # Keep showing typing indicator until delay is done
    await simulate_typing(context, message.chat_id, typing_seconds)

    user_histories[user_id].append({"role": "assistant", "content": reply_text})

    if len(user_histories[user_id]) > 20:
        user_histories[user_id] = user_histories[user_id][-20:]

    await message.reply_text(reply_text)


def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.UpdateType.BUSINESS_MESSAGE, handle_message))
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
