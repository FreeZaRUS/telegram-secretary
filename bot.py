import os
from openai import OpenAI
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

SYSTEM_PROMPT = "Ты — вежливый и организованный личный секретарь пользователя.\nОтвечай кратко, по делу, дружелюбным тоном."

user_histories = {}


def is_allowed(update: Update) -> bool:
    if "*" in ALLOWED_USERNAMES:
        return True
    user = update.effective_user
    username = (user.username or "").lower()
    return username in ALLOWED_USERNAMES or user.id in ALLOWED_USER_IDS


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я секретарь.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return

    user_id = update.effective_user.id
    user_text = update.message.text

    if user_id not in user_histories:
        user_histories[user_id] = []

    user_histories[user_id].append({"role": "user", "content": user_text})

    response = client_ai.chat.completions.create(
        model="google/gemma-2-9b-it:free",
        max_tokens=1000,
        messages=[{"role": "system", "content": SYSTEM_PROMPT}] + user_histories[user_id],
    )

    reply_text = response.choices[0].message.content
    user_histories[user_id].append({"role": "assistant", "content": reply_text})

    if len(user_histories[user_id]) > 20:
        user_histories[user_id] = user_histories[user_id][-20:]

    await update.message.reply_text(reply_text)


def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()


if __name__ == "__main__":
    main()
