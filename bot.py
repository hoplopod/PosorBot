import os
import random
import asyncio
import threading
import psycopg2
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime
from zoneinfo import ZoneInfo
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, ContextTypes,
    CallbackQueryHandler, MessageHandler, filters
)

TOKEN = os.getenv("BOT_TOKEN")
DB_URL = os.getenv("DATABASE_URL")

# --- ВЕБ-СЕРВЕР ЗАГЛУШКА ДЛЯ RENDER И UPTIMEROBOT ---
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Alive")

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), DummyHandler)
    server.serve_forever()

# --- БАЗА ДАННЫХ ---
def get_db():
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = True
    return conn, conn.cursor()

def init_db():
    conn, cursor = get_db()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        chat_id BIGINT,
        user_id BIGINT,
        username TEXT,
        length INTEGER DEFAULT 0,
        last_used TEXT DEFAULT '0',
        actions_date TEXT DEFAULT '0',
        actions_count INTEGER DEFAULT 3,
        PRIMARY KEY (chat_id, user_id)
    )
    """)
    conn.close()

def get_today_str():
    return datetime.now(ZoneInfo("Europe/Moscow")).strftime("%Y-%m-%d")

def init_and_get_user(chat_id, user_id, username):
    today_str = get_today_str()
    conn, cursor = get_db()
    
    cursor.execute(
        "SELECT length, last_used, actions_date, actions_count FROM users WHERE chat_id=%s AND user_id=%s",
        (chat_id, user_id)
    )
    row = cursor.fetchone()
    
    if row is None:
        cursor.execute(
            """
            INSERT INTO users
            (chat_id, user_id, username, length, last_used, actions_date, actions_count)
            VALUES (%s, %s, %s, 0, '0', %s, 3)
            """,
            (chat_id, user_id, username, today_str)
        )
        conn.close()
        return 0, '0', today_str, 3
    
    length, last_used, actions_date, actions_count = row
    
    if actions_date != today_str:
        actions_date = today_str
        actions_count = 3
        cursor.execute(
            "UPDATE users SET actions_date=%s, actions_count=%s, username=%s WHERE chat_id=%s AND user_id=%s",
            (actions_date, actions_count, username, chat_id, user_id)
        )
        
    conn.close()
    return length, last_used, actions_date, actions_count

# --- БАЗОВЫЕ КОМАНДЫ ---
async def dick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    username = f"@{user.username}" if user.username else user.first_name

    if user.username and user.username.lower() == "hoplopod":
        await update.message.reply_text(f"{username}, у тебя и так самый большой член, пошёл нахуй от сюда")
        return

    length, last_used, _, _ = init_and_get_user(chat.id, user.id, username)
    today_str = get_today_str()

    if str(last_used) == today_str:
        await update.message.reply_text(f"{username}, ты уже использовал бонусное действие сегодня! Кулдаун сбросится в полночь. 😉")
        return

    value = random.randint(1, 10)
    sign = random.choices([1, -1], weights=[10, 1])[0]
    length += value * sign

    conn, cursor = get_db()
    cursor.execute(
        "UPDATE users SET length=%s, last_used=%s, username=%s WHERE chat_id=%s AND user_id=%s",
        (length, today_str, username, chat.id, user.id)
    )
    conn.close()

    text = f"📈 {username}, твой член увеличился на {value} см!\n\nТеперь его длина: {length} см" if sign > 0 else f"📉 {username}, твой член уменьшился на {value} см!\n\nТеперь его длина: {length} см"
    await update.message.reply_text(text)

async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    conn, cursor = get_db()
    cursor.execute("SELECT username, length FROM users WHERE chat_id=%s ORDER BY length DESC LIMIT 10", (chat.id,))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("В этом чате пока нет участников рейтинга.")
        return

    text = "🏆 Топ писюнов чата\n\n"
    for i, (username, length) in enumerate(rows, start=1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        text += f"{medal} {username} — {length} см\n"
    await update.message.reply_text(text)

async def setdicksize(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat

    if not user.username or user.username.lower() != "hoplopod":
        await update.message.reply_text("Нет доступа.")
        return

    if len(context.args) != 2:
        await update.message.reply_text("Использование: /setdicksize @username размер")
        return

    target_username = context.args[0].replace("@", "")
    try:
        new_size = int(context.args[1])
    except ValueError:
        await update.message.reply_text("Размер должен быть числом.")
        return

    conn, cursor = get_db()
    cursor.execute("SELECT user_id FROM users WHERE chat_id=%s AND username=%s", (chat.id, f"@{target_username}"))
    row = cursor.fetchone()

    if not row:
        conn.close()
        await update.message.reply_text("Пользователь не найден в базе этого чата.")
        return

    cursor.execute("UPDATE users SET length=%s WHERE chat_id=%s AND username=%s", (new_size, chat.id, f"@{target_username}"))
    conn.close()
    await update.message.reply_text(f"✅ Размер пользователя @{target_username} установлен на {new_size} см")

# --- РУЛЕТКА ---
async def roulette_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    username = f"@{user.username}" if user.username else user.first_name

    if user.username and user.username.lower() == "hoplopod":
        await update.message.reply_text("Тебе нельзя играть.")
        return

    length, _, _, actions_count = init_and_get_user(chat.id, user.id, username)

    if actions_count <= 0:
        await update.message.reply_text(f"{username}, у тебя закончились действия на сегодня!")
        return
        
    if length <= 0:
        await update.message.reply_text(f"{username}, у тебя нулевой или отрицательный размер. Подрасти сначала!")
        return

    keyboard = [
        [InlineKeyboardButton("⬛ Чёрное (x2)", callback_data="rl_black"),
         InlineKeyboardButton("🟥 Красное (x2)", callback_data="rl_red")],
        [InlineKeyboardButton("🟩 Зелёное (x8)", callback_data="rl_green")],
        [InlineKeyboardButton("❌ Выйти", callback_data="rl_cancel")]
    ]
    await update.message.reply_text("🎰 Выбери цвет для ставки:", reply_markup=InlineKeyboardMarkup(keyboard))

async def roulette_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data

    await query.answer()

    if data == "rl_cancel":
        if f"roulette_{user_id}" in context.chat_data:
            del context.chat_data[f"roulette_{user_id}"]
        await query.edit_message_text("Действие отменено.")
        return

    color_map = {"rl_black": "⬛ Чёрное", "rl_red": "🟥 Красное", "rl_green": "🟩 Зелёное"}
    color_name = color_map.get(data)
    
    context.chat_data[f"roulette_{user_id}"] = {"color": data, "msg_id": query.message.message_id}

    keyboard = [[InlineKeyboardButton("❌ Выйти", callback_data="rl_cancel")]]
    await query.edit_message_text(
        f"Ты выбрал {color_name}.\nНапиши в чат сумму ставки (не больше 10% от длины).",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# --- ДУЭЛЬ НА КУБИКАХ ---
async def duel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    username = f"@{user.username}" if user.username else user.first_name

    if user.username and user.username.lower() == "hoplopod":
        await update.message.reply_text("Тебе нельзя играть.")
        return

    if len(context.args) != 2:
        await update.message.reply_text("Использование: /duel @username ставка")
        return

    target_username = context.args[0]
    if not target_username.startswith("@"):
        target_username = f"@{target_username}"
        
    try:
        bet = int(context.args[1])
        if bet <= 0: raise ValueError
    except ValueError:
        await update.message.reply_text("Ставка должна быть положительным числом.")
        return

    if target_username == username:
        await update.message.reply_text("Нельзя вызвать самого себя!")
        return

    length_1, _, _, actions_1 = init_and_get_user(chat.id, user.id, username)
    if actions_1 <= 0:
        await update.message.reply_text("У тебя закончились действия на сегодня!")
        return
    if length_1 < bet:
        await update.message.reply_text("Твоя длина меньше ставки!")
        return

    conn, cursor = get_db()
    cursor.execute("SELECT user_id, length, actions_count FROM users WHERE chat_id=%s AND username=%s", (chat.id, target_username))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        await update.message.reply_text("Противник не найден в базе этого чата.")
        return
        
    target_id, length_2, actions_2 = row
    if actions_2 <= 0:
        await update.message.reply_text("У противника закончились действия на сегодня!")
        return
    if length_2 < bet:
        await update.message.reply_text("Длина противника меньше ставки!")
        return

    keyboard = [
        [InlineKeyboardButton("⚔️ Принять", callback_data=f"duel_acc_{user.id}_{target_id}_{bet}"),
         InlineKeyboardButton("❌ Отклонить", callback_data=f"duel_dec_{user.id}_{target_id}")]
    ]
    
    await update.message.reply_text(
        f"{target_username}, тебя вызывает на дуэль {username}!\nСтавка: {bet} см.\nУ вас обоих спишется 1 действие.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def duel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    clicker_id = query.from_user.id
    chat_id = query.message.chat_id
    data = query.data.split("_")
    
    action = data[1]
    p1_id = int(data[2])
    p2_id = int(data[3])
    
    if clicker_id not in [p1_id, p2_id]:
        await query.answer("Это не твоя дуэль!", show_alert=True)
        return

    await query.answer()

    if action == "dec":
        await query.edit_message_text("Дуэль отклонена или отменена.")
        return

    if action == "acc":
        if clicker_id != p2_id:
            await query.answer("Только вызванный игрок может принять дуэль!", show_alert=True)
            return
            
        bet = int(data[4])
        await query.edit_message_text(f"⚔️ Дуэль началась! Ставка: {bet} см.\nБросаем кубики 5 раз...")

        p1_score = 0
        p2_score = 0

        for round_num in range(1, 6):
            msg1 = await context.bot.send_dice(chat_id=chat_id, emoji="🎲")
            msg2 = await context.bot.send_dice(chat_id=chat_id, emoji="🎲")
            await asyncio.sleep(4) 
            
            v1 = msg1.dice.value
            v2 = msg2.dice.value
            if v1 > v2: p1_score += 1
            elif v2 > v1: p2_score += 1

        conn, cursor = get_db()
        cursor.execute("SELECT username FROM users WHERE user_id=%s AND chat_id=%s", (p1_id, chat_id))
        p1_name = cursor.fetchone()[0]
        cursor.execute("SELECT username FROM users WHERE user_id=%s AND chat_id=%s", (p2_id, chat_id))
        p2_name = cursor.fetchone()[0]

        if p1_score > p2_score:
            winner, loser, winner_name = p1_id, p2_id, p1_name
        elif p2_score > p1_score:
            winner, loser, winner_name = p2_id, p1_id, p2_name
        else:
            await context.bot.send_message(chat_id, f"🤝 Ничья! {p1_score}:{p2_score}. Ставки возвращаются. Действия потрачены.")
            cursor.execute("UPDATE users SET actions_count = actions_count - 1 WHERE chat_id=%s AND user_id IN (%s, %s)", (chat_id, p1_id, p2_id))
            conn.close()
            return

        cursor.execute("UPDATE users SET length = length + %s, actions_count = actions_count - 1 WHERE chat_id=%s AND user_id=%s", (bet, chat_id, winner))
        cursor.execute("UPDATE users SET length = length - %s, actions_count = actions_count - 1 WHERE chat_id=%s AND user_id=%s", (bet, chat_id, loser))
        conn.close()

        await context.bot.send_message(
            chat_id, 
            f"🏆 Победил {winner_name} со счетом {max(p1_score, p2_score)}:{min(p1_score, p2_score)}!\n"
            f"Он забирает ставку {bet} см."
        )

# --- ОБРАБОТЧИК ТЕКСТА (СТАВКИ В РУЛЕТКЕ) ---
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    
    if not update.message or not update.message.text:
        return
        
    state = context.chat_data.get(f"roulette_{user.id}")
    if not state:
        return

    text = update.message.text
    if not text.isdigit():
        return

    bet = int(text)
    length, _, _, _ = init_and_get_user(chat.id, user.id, "")
    
    max_bet = max(1, int(length * 0.10))
    if bet > max_bet or bet <= 0:
        await update.message.reply_text(f"Ставка должна быть от 1 до {max_bet} см (10% от длины).")
        return

    chosen_color = state["color"]
    del context.chat_data[f"roulette_{user.id}"] 

    msg = await update.message.reply_text("🎡 Шарик запущен, рулетка крутится... 🎱")
    await asyncio.sleep(2) 

    number = random.randint(0, 36)
    red_numbers = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
    
    if number == 0:
        result_color = "rl_green"
        color_text = "🟩 Зелёное (0)"
    elif number in red_numbers:
        result_color = "rl_red"
        color_text = f"🟥 Красное ({number})"
    else:
        result_color = "rl_black"
        color_text = f"⬛ Чёрное ({number})"

    conn, cursor = get_db()
    if chosen_color == result_color:
        multiplier = 8 if result_color == "rl_green" else 2
        win_amount = bet * multiplier
        cursor.execute(
            "UPDATE users SET length = length + %s, actions_count = actions_count - 1 WHERE chat_id=%s AND user_id=%s", 
            (win_amount, chat.id, user.id)
        )
        await msg.edit_text(f"Выпало {color_text}!\n🎉 Победа! Твой член увеличился на {win_amount} см.\nДействие потрачено.")
    else:
        cursor.execute(
            "UPDATE users SET length = length - %s, actions_count = actions_count - 1 WHERE chat_id=%s AND user_id=%s", 
            (bet, chat.id, user.id)
        )
        await msg.edit_text(f"Выпало {color_text}!\n😢 Проигрыш... Твой член уменьшился на {bet} см.\nДействие потрачено.")
    conn.close()

def main():
    threading.Thread(target=run_dummy_server, daemon=True).start()
    init_db()

    app = Application.builder().token(TOKEN).connect_timeout(30.0).read_timeout(30.0).build()

    app.add_handler(CommandHandler("dick", dick))
    app.add_handler(CommandHandler("top", top))
    app.add_handler(CommandHandler("setdicksize", setdicksize))
    app.add_handler(CommandHandler("roulette", roulette_cmd))
    app.add_handler(CommandHandler("duel", duel_cmd))
    
    app.add_handler(CallbackQueryHandler(roulette_callback, pattern="^rl_"))
    app.add_handler(CallbackQueryHandler(duel_callback, pattern="^duel_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    print("Bot started")
    app.run_polling()

if __name__ == "__main__":
    main()