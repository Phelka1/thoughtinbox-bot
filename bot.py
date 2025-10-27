import telebot
import json
import os
from datetime import datetime
from telebot import types

# 🔑 Токен из Render (или вставь вручную при тесте в Pydroid)
TOKEN = os.getenv("TOKEN")
bot = telebot.TeleBot(TOKEN)

DATA_FILE = "thoughts.json"


# 🧠 --- Работа с файлами ---
def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def add_thought(user_id, text):
    data = load_data()
    user_id = str(user_id)
    if user_id not in data:
        data[user_id] = []

    tags = [word[1:].lower() for word in text.split() if word.startswith("#")]
    entry = {
        "text": text,
        "tags": tags,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    data[user_id].append(entry)
    save_data(data)


# 🧾 --- Инлайн-кнопки ---
def main_menu():
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton("📋 Мысли", callback_data="inbox"),
        types.InlineKeyboardButton("🌅 Сегодня", callback_data="review"),
    )
    keyboard.add(
        types.InlineKeyboardButton("🏷️ Теги", callback_data="tags"),
        types.InlineKeyboardButton("📤 Экспорт", callback_data="export"),
    )
    keyboard.add(
        types.InlineKeyboardButton("🧹 Очистить", callback_data="clear")
    )
    return keyboard


# 📋 --- Команды ---
@bot.message_handler(commands=["start"])
def start(message):
    bot.send_message(
        message.chat.id,
        "👋 Привет! Я ThoughtInbox 🤖\n"
        "Пиши свои мысли, добавляй #теги, а я всё сохраню.\n\n"
        "Выбери действие ниже ⬇️",
        reply_markup=main_menu()
    )


@bot.message_handler(commands=["help"])
def help_cmd(message):
    bot.send_message(
        message.chat.id,
        "📘 Команды:\n"
        "/start — меню и кнопки\n"
        "/help — помощь\n"
        "/inbox — последние мысли\n"
        "/review — мысли за сегодня\n"
        "/tags — твои теги\n"
        "/export — экспорт мыслей\n"
        "/clear — очистить всё\n\n"
        "💡 Просто напиши любую мысль, я сохраню её."
    )


# 📥 --- Обработка кнопок ---
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    data = load_data()
    user_id = str(call.from_user.id)

    if call.data == "inbox":
        if user_id not in data or not data[user_id]:
            bot.answer_callback_query(call.id, "Пока нет мыслей 🗒️")
            return
        thoughts = "\n\n".join(
            [f"💭 {t['text']} ({t['time']})" for t in data[user_id][-10:]]
        )
        bot.send_message(call.message.chat.id, f"🧾 Последние мысли:\n\n{thoughts}")

    elif call.data == "review":
        today = datetime.now().strftime("%Y-%m-%d")
        today_thoughts = [
            t["text"] for t in data.get(user_id, []) if today in t["time"]
        ]
        if not today_thoughts:
            bot.answer_callback_query(call.id, "Сегодня записей нет ☀️")
            return
        joined = "\n".join([f"💡 {t}" for t in today_thoughts])
        bot.send_message(call.message.chat.id, f"🌅 Мысли за сегодня:\n\n{joined}")

    elif call.data == "tags":
        tags = set()
        for t in data.get(user_id, []):
            tags.update(t["tags"])
        if not tags:
            bot.answer_callback_query(call.id, "Пока нет тегов 🏷️")
            return
        bot.send_message(call.message.chat.id, "📚 Твои теги:\n" + ", ".join(f"#{t}" for t in sorted(tags)))

    elif call.data == "export":
        if user_id not in data or not data[user_id]:
            bot.answer_callback_query(call.id, "Нет мыслей для экспорта 📂")
            return
        filename = f"thoughts_{user_id}.txt"
        with open(filename, "w", encoding="utf-8") as f:
            for t in data[user_id]:
                tags = " ".join([f"#{tag}" for tag in t["tags"]])
                f.write(f"{t['time']} — {t['text']} {tags}\n")
        with open(filename, "rb") as f:
            bot.send_document(call.message.chat.id, f)
        os.remove(filename)

    elif call.data == "clear":
        data[user_id] = []
        save_data(data)
        bot.send_message(call.message.chat.id, "🧹 Все мысли очищены!")

    bot.answer_callback_query(call.id)


# 💬 --- Сохранение мысли ---
@bot.message_handler(func=lambda message: True)
def save_thought(message):
    text = message.text.strip()
    if not text:
        return
    add_thought(message.from_user.id, text)
    bot.send_message(
        message.chat.id,
        "💡 Мысль сохранена!",
        reply_markup=main_menu()
    )


# 🚀 Запуск
bot.polling(none_stop=True)
