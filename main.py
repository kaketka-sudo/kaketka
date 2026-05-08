import os
import sqlite3
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from datetime import datetime

# ===== НАСТРОЙКИ ДЛЯ RAILWAY =====
BOT_TOKEN = "8401686455:AAFFJkuATAayrDocPsM1aJXGq8PULMKZ_qI"
ADMIN_IDS = [7296255452, 6515134253, 1638720657]
FOLDER_PATH = "/app/AlexG_Songs"
DB_NAME = "alexg_music.db"
# =================================

bot = telebot.TeleBot(BOT_TOKEN)
temp_song_data = {}

def is_admin(user_id):
    return user_id in ADMIN_IDS

def create_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS songs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT UNIQUE,
            title TEXT,
            lyrics TEXT
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            first_seen TIMESTAMP,
            last_seen TIMESTAMP,
            messages_count INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

def update_user(message):
    user = message.from_user
    now = datetime.now().isoformat()
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO users (user_id, username, first_name, last_name, first_seen, last_seen, messages_count)
        VALUES (?, ?, ?, ?, ?, ?, 1)
        ON CONFLICT(user_id) DO UPDATE SET
            username = COALESCE(?, username),
            first_name = COALESCE(?, first_name),
            last_name = COALESCE(?, last_name),
            last_seen = ?,
            messages_count = messages_count + 1
    ''', (user.id, user.username, user.first_name, user.last_name, now, now,
          user.username, user.first_name, user.last_name, now))
    conn.commit()
    conn.close()

def get_all_users():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('SELECT user_id, username, first_name, last_name, first_seen, last_seen, messages_count FROM users ORDER BY last_seen DESC')
    results = cur.fetchall()
    conn.close()
    return results

def get_users_count():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM users')
    count = cur.fetchone()[0]
    conn.close()
    return count

def broadcast_message(user_ids, text):
    success = 0
    fail = 0
    for uid in user_ids:
        try:
            bot.send_message(uid, text, parse_mode="Markdown")
            success += 1
        except:
            fail += 1
    return success, fail

def add_or_update_song(filename, title, lyrics=""):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO songs (filename, title, lyrics)
        VALUES (?, ?, ?)
        ON CONFLICT(filename) DO UPDATE SET
            title = excluded.title,
            lyrics = excluded.lyrics
    ''', (filename, title, lyrics))
    conn.commit()
    conn.close()

def remove_song(filename):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("DELETE FROM songs WHERE filename = ?", (filename,))
    conn.commit()
    conn.close()

def get_all_songs():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT id, filename, title FROM songs ORDER BY title")
    results = cur.fetchall()
    conn.close()
    return results

def search_songs_by_title(query):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT id, filename, title FROM songs WHERE title LIKE ? ORDER BY title", (f'%{query}%',))
    results = cur.fetchall()
    conn.close()
    return results

def get_lyrics(song_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT lyrics FROM songs WHERE id = ?", (song_id,))
    result = cur.fetchone()
    conn.close()
    return result[0] if result else "Текст не найден"

def scan_folder():
    if not os.path.exists(FOLDER_PATH):
        os.makedirs(FOLDER_PATH)
        print(f"Создана папка: {FOLDER_PATH}")
        return
    audio_extensions = ('.mp3', '.ogg', '.m4a', '.wav')
    existing_files = set()
    for file in os.listdir(FOLDER_PATH):
        if file.lower().endswith(audio_extensions):
            existing_files.add(file)
            conn = sqlite3.connect(DB_NAME)
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM songs WHERE filename = ?", (file,))
            if not cur.fetchone():
                title = os.path.splitext(file)[0].replace("_", " ").replace("-", " ")
                add_or_update_song(file, title)
            conn.close()
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT filename FROM songs")
    db_files = [row[0] for row in cur.fetchall()]
    conn.close()
    for db_file in db_files:
        if db_file not in existing_files:
            remove_song(db_file)

def get_main_menu(user_id):
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = KeyboardButton("🎵 Все песни")
    btn2 = KeyboardButton("🔍 Поиск по названию")
    keyboard.add(btn1, btn2)
    if is_admin(user_id):
        btn3 = KeyboardButton("👑 Админ-панель")
        keyboard.add(btn3)
    return keyboard

@bot.message_handler(commands=['start'])
def start(message):
    update_user(message)
    scan_folder()
    bot.send_message(
        message.chat.id,
        "🎸 *Alex G Bot*\n\nВыбери действие на кнопках ниже:",
        parse_mode="Markdown",
        reply_markup=get_main_menu(message.from_user.id)
    )

@bot.message_handler(func=lambda message: message.text == "🎵 Все песни")
def list_all_songs(message):
    update_user(message)
    songs = get_all_songs()
    if not songs:
        bot.send_message(message.chat.id, "📭 В базе нет песен")
        return
    total = len(songs)
    bot.send_message(message.chat.id, f"🎵 *Все песни Alex G* — всего {total}\n", parse_mode="Markdown")
    page_size = 7
    pages = (total + page_size - 1) // page_size
    start_idx = 0
    end_idx = min(page_size, total)
    page_songs = songs[start_idx:end_idx]
    keyboard = InlineKeyboardMarkup(row_width=1)
    for song_id, filename, title in page_songs:
        keyboard.add(InlineKeyboardButton(f"🎵 {title}", callback_data=f"play_{song_id}"))
    if pages > 1:
        keyboard.add(InlineKeyboardButton("▶️ Вперёд", callback_data="page_1"))
    bot.send_message(
        message.chat.id,
        f"📄 *Страница 1 из {pages}*",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

@bot.message_handler(func=lambda message: message.text == "🔍 Поиск по названию")
def search_song_prompt(message):
    update_user(message)
    msg = bot.send_message(
        message.chat.id,
        "🔎 *Введи название песни:*",
        parse_mode="Markdown"
    )
    bot.register_next_step_handler(msg, perform_search)

def perform_search(message):
    update_user(message)
    query = message.text.strip()
    if not query:
        bot.send_message(message.chat.id, "❌ Введи название")
        return
    results = search_songs_by_title(query)
    if not results:
        bot.send_message(message.chat.id, f"❌ Ничего не найдено: *{query}*", parse_mode="Markdown")
        return
    total = len(results)
    bot.send_message(message.chat.id, f"🔍 *Результаты:* «{query}» — {total}\n", parse_mode="Markdown")
    page_size = 7
    pages = (total + page_size - 1) // page_size
    start_idx = 0
    end_idx = min(page_size, total)
    page_results = results[start_idx:end_idx]
    keyboard = InlineKeyboardMarkup(row_width=1)
    for song_id, filename, title in page_results:
        keyboard.add(InlineKeyboardButton(f"🎵 {title}", callback_data=f"play_{song_id}"))
    if pages > 1:
        keyboard.add(InlineKeyboardButton("▶️ Вперёд", callback_data=f"searchpage_1_{query}"))
    bot.send_message(
        message.chat.id,
        f"📄 *Страница 1 из {pages}*",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

@bot.message_handler(func=lambda message: message.text == "👑 Админ-панель")
def admin_panel_button(message):
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "⛔ Доступ запрещён.")
        return
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(InlineKeyboardButton("➕ Добавить песню", callback_data="admin_add_song"))
    keyboard.add(InlineKeyboardButton("📋 Список песен", callback_data="admin_list_songs"))
    keyboard.add(InlineKeyboardButton("🔄 Обновить базу", callback_data="admin_update"))
    keyboard.add(InlineKeyboardButton("🗑 Удалить песню", callback_data="admin_delete_song"))
    keyboard.add(InlineKeyboardButton("👥 Пользователи", callback_data="admin_users"))
    keyboard.add(InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast"))
    bot.send_message(
        message.chat.id,
        "👑 *Админ-панель*",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

@bot.callback_query_handler(func=lambda call: call.data == "admin_users")
def admin_users(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Не для тебя")
        return
    users = get_all_users()
    count = get_users_count()
    if not users:
        bot.edit_message_text("📭 Нет пользователей", call.message.chat.id, call.message.message_id)
        return
    text = f"👥 *Пользователи бота* — всего {count}\n\n"
    for user_id, username, first_name, last_name, first_seen, last_seen, msg_count in users:
        name = first_name or "Без имени"
        if username:
            name += f" (@{username})"
        text += f"• `{user_id}` | {name} | Сообщений: {msg_count}\n"
        if len(text) > 3500:
            bot.send_message(call.message.chat.id, text, parse_mode="Markdown")
            text = ""
    if text:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode=None)
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("◀️ Назад", callback_data="admin_back"))
    bot.send_message(call.message.chat.id, "🔙", reply_markup=keyboard)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "admin_broadcast")
def admin_broadcast_prompt(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Не для тебя")
        return
    bot.edit_message_text(
        "📢 *Рассылка*\n\nВведи сообщение, которое будет отправлено ВСЕМ пользователям бота:\n(Можно использовать Markdown)",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown"
    )
    bot.register_next_step_handler(call.message, process_broadcast)
    bot.answer_callback_query(call.id)

def process_broadcast(message):
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "⛔ Доступ запрещён.")
        return
    text = message.text
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users")
    users = [row[0] for row in cur.fetchall()]
    conn.close()
    if not users:
        bot.send_message(message.chat.id, "📭 Нет пользователей для рассылки")
        return
    bot.send_message(message.chat.id, f"📢 Начинаю рассылку для {len(users)} пользователей...")
    success, fail = broadcast_message(users, text)
    bot.send_message(
        message.chat.id,
        f"✅ Рассылка завершена!\n\n✅ Успешно: {success}\n❌ Ошибок: {fail}"
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_"))
def admin_buttons(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Не для тебя")
        return
    if call.data == "admin_add_song":
        bot.edit_message_text(
            "📤 *Отправь аудиофайл* (MP3, OGG, M4A, WAV)",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown"
        )
        bot.register_next_step_handler(call.message, process_audio_file)
    elif call.data == "admin_list_songs":
        songs = get_all_songs()
        if not songs:
            bot.edit_message_text("📭 Нет песен", call.message.chat.id, call.message.message_id)
            return
        text = "🎵 *Список песен:*\n\n"
        for song_id, filename, title in songs:
            text += f"• {title}\n"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown")
    elif call.data == "admin_update":
        scan_folder()
        bot.edit_message_text("✅ Обновлено", call.message.chat.id, call.message.message_id)
    elif call.data == "admin_delete_song":
        songs = get_all_songs()
        if not songs:
            bot.edit_message_text("📭 Нет песен", call.message.chat.id, call.message.message_id)
            return
        keyboard = InlineKeyboardMarkup(row_width=1)
        for song_id, _, title in songs:
            keyboard.add(InlineKeyboardButton(f"❌ {title}", callback_data=f"del_{song_id}"))
        keyboard.add(InlineKeyboardButton("◀️ Назад", callback_data="admin_back"))
        bot.edit_message_text("🗑 *Выбери песню:*", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=keyboard)
    elif call.data == "admin_back":
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(InlineKeyboardButton("➕ Добавить песню", callback_data="admin_add_song"))
        keyboard.add(InlineKeyboardButton("📋 Список песен", callback_data="admin_list_songs"))
        keyboard.add(InlineKeyboardButton("🔄 Обновить базу", callback_data="admin_update"))
        keyboard.add(InlineKeyboardButton("🗑 Удалить песню", callback_data="admin_delete_song"))
        keyboard.add(InlineKeyboardButton("👥 Пользователи", callback_data="admin_users"))
        keyboard.add(InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast"))
        bot.edit_message_text("👑 *Админ-панель*", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data.startswith("del_"))
def delete_song_handler(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Не для тебя")
        return
    song_id = int(call.data.split("_")[1])
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT filename, title FROM songs WHERE id = ?", (song_id,))
    song = cur.fetchone()
    if song:
        filename, title = song
        file_path = os.path.join(FOLDER_PATH, filename)
        if os.path.exists(file_path):
            os.remove(file_path)
        cur.execute("DELETE FROM songs WHERE id = ?", (song_id,))
        conn.commit()
        bot.answer_callback_query(call.id, f"✅ {title} удалена")
        bot.edit_message_text(f"🗑 *{title}* удалена", call.message.chat.id, call.message.message_id, parse_mode="Markdown")
    else:
        bot.answer_callback_query(call.id, "❌ Не найдено")
    conn.close()

def process_audio_file(message):
    if not message.audio and not message.document:
        bot.send_message(message.chat.id, "❌ Отправь аудиофайл")
        bot.register_next_step_handler(message, process_audio_file)
        return
    if message.audio:
        file_id = message.audio.file_id
        file_name = message.audio.file_name or f"audio_{file_id}.mp3"
    else:
        file_id = message.document.file_id
        file_name = message.document.file_name
    temp_song_data[message.chat.id] = {'file_id': file_id, 'file_name': file_name}
    bot.send_message(message.chat.id, f"📁 Файл: `{file_name}`\n\n✏️ *Введи название:*", parse_mode="Markdown")
    bot.register_next_step_handler(message, get_song_title)

def get_song_title(message):
    title = message.text.strip()
    if not title:
        bot.send_message(message.chat.id, "❌ Введи название")
        bot.register_next_step_handler(message, get_song_title)
        return
    temp_song_data[message.chat.id]['title'] = title
    bot.send_message(message.chat.id, f"🎵 *{title}*\n\n✏️ *Введи текст песни:*", parse_mode="Markdown")
    bot.register_next_step_handler(message, get_song_lyrics)

def get_song_lyrics(message):
    lyrics = message.text.strip()
    user_data = temp_song_data.get(message.chat.id)
    if not user_data:
        bot.send_message(message.chat.id, "❌ Ошибка. Начни заново с /start")
        return
    file_id = user_data['file_id']
    file_name = user_data['file_name']
    title = user_data['title']
    try:
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        if not os.path.exists(FOLDER_PATH):
            os.makedirs(FOLDER_PATH)
        file_path = os.path.join(FOLDER_PATH, file_name)
        with open(file_path, 'wb') as f:
            f.write(downloaded_file)
        add_or_update_song(file_name, title, lyrics)
        del temp_song_data[message.chat.id]
        bot.send_message(message.chat.id, f"✅ *{title}* добавлена!", parse_mode="Markdown")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {str(e)}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("page_") and not call.data.startswith("searchpage_"))
def navigate_pages(call):
    page = int(call.data.split("_")[1])
    songs = get_all_songs()
    total = len(songs)
    page_size = 7
    pages = (total + page_size - 1) // page_size
    start_idx = page * page_size
    end_idx = min(start_idx + page_size, total)
    page_songs = songs[start_idx:end_idx]
    keyboard = InlineKeyboardMarkup(row_width=1)
    for song_id, filename, title in page_songs:
        keyboard.add(InlineKeyboardButton(f"🎵 {title}", callback_data=f"play_{song_id}"))
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("◀️ Назад", callback_data=f"page_{page-1}"))
    if page < pages - 1:
        nav_buttons.append(InlineKeyboardButton("▶️ Вперёд", callback_data=f"page_{page+1}"))
    if nav_buttons:
        keyboard.row(*nav_buttons)
    bot.edit_message_text(
        f"📄 *Страница {page+1} из {pages}*",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown",
        reply_markup=keyboard
    )
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("searchpage_"))
def navigate_search_pages(call):
    parts = call.data.split("_")
    page = int(parts[1])
    query = "_".join(parts[2:])
    results = search_songs_by_title(query)
    total = len(results)
    page_size = 7
    pages = (total + page_size - 1) // page_size
    start_idx = page * page_size
    end_idx = min(start_idx + page_size, total)
    page_results = results[start_idx:end_idx]
    keyboard = InlineKeyboardMarkup(row_width=1)
    for song_id, filename, title in page_results:
        keyboard.add(InlineKeyboardButton(f"🎵 {title}", callback_data=f"play_{song_id}"))
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("◀️ Назад", callback_data=f"searchpage_{page-1}_{query}"))
    if page < pages - 1:
        nav_buttons.append(InlineKeyboardButton("▶️ Вперёд", callback_data=f"searchpage_{page+1}_{query}"))
    if nav_buttons:
        keyboard.row(*nav_buttons)
    bot.edit_message_text(
        f"🔍 *{query}* • страница {page+1} из {pages}",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown",
        reply_markup=keyboard
    )
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("play_"))
def play_song(call):
    song_id = int(call.data.split("_")[1])
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT filename, title FROM songs WHERE id = ?", (song_id,))
    song = cur.fetchone()
    conn.close()
    if song:
        filename, title = song
        file_path = os.path.join(FOLDER_PATH, filename)
        if os.path.exists(file_path):
            with open(file_path, 'rb') as audio:
                bot.send_audio(call.message.chat.id, audio, title=title, performer="Alex G")
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("📝 Текст песни", callback_data=f"lyrics_{song_id}"))
            bot.send_message(call.message.chat.id, f"🎶 *{title}*", parse_mode="Markdown", reply_markup=keyboard)
        else:
            bot.answer_callback_query(call.id, "❌ Файл не найден")
    else:
        bot.answer_callback_query(call.id, "❌ Песня не найдена")
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("lyrics_"))
def show_lyrics(call):
    song_id = int(call.data.split("_")[1])
    lyrics = get_lyrics(song_id)
    if lyrics and lyrics.strip():
        if len(lyrics) > 4000:
            for i in range(0, len(lyrics), 4000):
                bot.send_message(call.message.chat.id, lyrics[i:i+4000])
        else:
            bot.send_message(call.message.chat.id, f"📝 *Текст:*\n\n{lyrics}", parse_mode="Markdown")
    else:
        bot.answer_callback_query(call.id, "❌ Текст не добавлен", show_alert=True)
    bot.answer_callback_query(call.id)

if __name__ == "__main__":
    print("🎸 Alex G Bot запущен!")
    create_db()
    scan_folder()
    bot.infinity_polling()
