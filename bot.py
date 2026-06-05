import sqlite3
import random
import time
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import os

TOKEN = os.getenv("BOT_TOKEN")

COOLDOWN = 24 * 60 * 60  # 24 часа

db = sqlite3.connect("dickbot.db", check_same_thread=False)
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    chat_id INTEGER,
    user_id INTEGER,
    username TEXT,
    length INTEGER DEFAULT 0,
    last_used INTEGER DEFAULT 0,
    PRIMARY KEY (chat_id, user_id)
)
""")
db.commit()


async def dick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat

    username_raw = user.username.lower() if user.username else ""

    if username_raw == "hoplopod":
        await update.message.reply_text(
            "У тебя и так самый большой член, пошёл нахуй от сюда"
        )
        return

    username = (
        f"@{user.username}"
        if user.username
        else user.first_name
    )

    cursor.execute(
        "SELECT length, last_used FROM users WHERE chat_id=? AND user_id=?",
        (chat.id, user.id)
    )
    row = cursor.fetchone()

    now = int(time.time())

    if row is None:
        cursor.execute(
            """
            INSERT INTO users
            (chat_id, user_id, username, length, last_used)
            VALUES (?, ?, ?, 0, 0)
            """,
            (chat.id, user.id, username)
        )
        db.commit()
        length = 0
        last_used = 0
    else:
        length, last_used = row

    if now - last_used < COOLDOWN:
        remaining = COOLDOWN - (now - last_used)
        hours = remaining // 3600

        await update.message.reply_text(
            f"{username}, команду можно использовать через {hours} ч."
        )
        return

    value = random.randint(1, 10)
    sign = random.choice([-1, 1])

    length += value * sign

    cursor.execute(
        """
        UPDATE users
        SET length=?, last_used=?, username=?
        WHERE chat_id=? AND user_id=?
        """,
        (length, now, username, chat.id, user.id)
    )
    db.commit()

    if sign > 0:
        text = (
            f"📈 {username}, твой член увеличился на {value} см!\n\n"
            f"Теперь его длина: {length} см"
        )
    else:
        text = (
            f"📉 {username}, твой член уменьшился на {value} см!\n\n"
            f"Теперь его длина: {length} см"
        )

    await update.message.reply_text(text)


async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat

    cursor.execute(
        """
        SELECT username, length
        FROM users
        WHERE chat_id=?
        ORDER BY length DESC
        LIMIT 10
        """,
        (chat.id,)
    )

    rows = cursor.fetchall()

    if not rows:
        await update.message.reply_text("В этом чате пока нет участников рейтинга.")
        return

    text = "🏆 Топ писюнов чата\n\n"

    for i, (username, length) in enumerate(rows, start=1):
        text += f"{i}. {username} — {length} см\n"

    await update.message.reply_text(text)


def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("dick", dick))
    app.add_handler(CommandHandler("top", top))

    print("Bot started")

    app.run_polling()


if __name__ == "__main__":
    main()