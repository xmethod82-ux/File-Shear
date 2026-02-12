import telebot
import sqlite3
import datetime
import string
import random
import time
from telebot import types

# --- CONFIGURATION ---
BOT_TOKEN = "BOT_TOKEN"
ADMIN_ID = ADMIN_ID
BOT_USERNAME = "BOT_USERNAME" 

bot = telebot.TeleBot(BOT_TOKEN)

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS files (
            id TEXT PRIMARY KEY,
            file_id TEXT NOT NULL,
            file_type TEXT NOT NULL,
            file_name TEXT,
            user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def generate_id():
    chars = string.ascii_lowercase + string.digits
    return ''.join(random.choice(chars) for _ in range(8))

# --- HELPERS ---
def get_file_list_markup(user_id):
    conn = sqlite3.connect('bot_database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM files WHERE user_id=? ORDER BY created_at DESC LIMIT 10", (user_id,))
    rows = cursor.fetchall()
    conn.close()

    markup = types.InlineKeyboardMarkup()
    if rows:
        for f in rows:
            markup.add(types.InlineKeyboardButton(text=f"📄 {f['file_name']}", callback_data=f"manage_{f['id']}"))
        return markup, "📁 Click on a file name to manage it:"
    return None, "📭 You haven't uploaded any files yet."

# --- HANDLERS ---

@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    text_args = message.text.split()

    if len(text_args) > 1:
        file_id_param = text_args[1]
        conn = sqlite3.connect('bot_database.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM files WHERE id=?", (file_id_param,))
        file = cursor.fetchone()
        conn.close()

        if file:
            caption = f"📄 {file['file_name']}"
            if file['file_type'] == 'photo':
                bot.send_photo(chat_id, file['file_id'], caption=caption)
            elif file['file_type'] == 'video':
                bot.send_video(chat_id, file['file_id'], caption=caption)
            else:
                bot.send_document(chat_id, file['file_id'], caption=caption)
            return
        else:
            bot.send_message(chat_id, "❌ File not found or expired.")
            return

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('📤 Upload File', '📂 My Files')
    welcome_text = f"Hello {message.from_user.first_name}! 👋\nWelcome to File Share Bot."
    bot.send_message(chat_id, welcome_text, reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == '📤 Upload File')
def upload_instruction(message):
    bot.reply_to(message, "Please send the file (Photo, Video, or Document) you want to upload.")

@bot.message_handler(func=lambda message: message.text == '📂 My Files')
def my_files(message):
    markup, text = get_file_list_markup(message.from_user.id)
    bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    data = call.data
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    
    if data.startswith("manage_"):
        file_db_id = data.split("_")[1]
        conn = sqlite3.connect('bot_database.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM files WHERE id=?", (file_db_id,))
        file = cursor.fetchone()
        conn.close()

        if file:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔗 File Link", callback_data=f"getlink_{file_db_id}"))
            markup.add(types.InlineKeyboardButton("🗑️ Delete File", callback_data=f"delete_{file_db_id}"))
            markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="back_to_list"))
            
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"📄 **File:** {file['file_name']}\n\nWhat would you like to do?",
                reply_markup=markup,
                parse_mode='Markdown'
            )

    elif data.startswith("getlink_"):
        file_db_id = data.split("_")[1]
        link = f"https://t.me/{BOT_USERNAME}?start={file_db_id}"
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data=f"manage_{file_db_id}"))
        
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=f"🔗 **Your Shareable Link:**\n\n`{link}`\n\n_Click to copy the link above._",
            reply_markup=markup,
            parse_mode='Markdown'
        )

    elif data.startswith("delete_"):
        file_db_id = data.split("_")[1]
        conn = sqlite3.connect('bot_database.db')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM files WHERE id=?", (file_db_id,))
        conn.commit()
        conn.close()
        
        bot.answer_callback_query(call.id, "✅ File Deleted!")
        # Refresh the list after deletion by editing the same message
        markup, text = get_file_list_markup(call.from_user.id)
        bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=markup)

    elif data == "back_to_list":
        markup, text = get_file_list_markup(call.from_user.id)
        bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=markup)

@bot.message_handler(content_types=['document', 'photo', 'video'])
def handle_incoming_files(message):
    file_type, file_id, file_name = "", "", "file"
    if message.document:
        file_type, file_id, file_name = "document", message.document.file_id, message.document.file_name
    elif message.photo:
        file_type, file_id, file_name = "photo", message.photo[-1].file_id, "photo.jpg"
    elif message.video:
        file_type, file_id, file_name = "video", message.video.file_id, message.video.file_name or "video.mp4"

    unique_id = generate_id()
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO files (id, file_id, file_type, file_name, user_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (unique_id, file_id, file_type, file_name, message.from_user.id, datetime.datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

    share_link = f"https://t.me/{BOT_USERNAME}?start={unique_id}"
    bot.reply_to(message, f"✅ Upload Complete!\n\n📄 {file_name}\n🔗 {share_link}")

@bot.message_handler(commands=['broadcast'])
def broadcast(message):
    if message.from_user.id != ADMIN_ID: return
    command_text = message.text.replace('/broadcast', '').strip()
    if not command_text:
        bot.reply_to(message, "❌ Usage: /broadcast [your message]")
        return

    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT user_id FROM files")
    users = cursor.fetchall()
    conn.close()

    success = 0
    for user in users:
        try:
            bot.send_message(user[0], f"\n\n{command_text}", parse_mode='Markdown')
            success += 1
        except: continue
    bot.send_message(message.chat.id, f"✅ Broadcast sent to {success} users.")

if __name__ == '__main__':
    init_db()
    print("Bot is running...")
    while True:
        try:
            bot.infinity_polling(timeout=20, long_polling_timeout=10)
        except Exception as e:
            print(f"Reconnect error: {e}")
            time.sleep(5)


