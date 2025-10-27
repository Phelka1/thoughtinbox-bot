import telebot
import json, os

# 🔑 вставь сюда свой токен от BotFather
TOKEN = '8218144711:AAHs-bakVn1DmfAHL4inU2OoRosXALX893Q'

bot = telebot.TeleBot(TOKEN)
DATA_FILE = "thoughts.json"

def save_thought(user_id, text):
    data = {}
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    if str(user_id) not in data:
        data[str(user_id)] = []
    data[str(user_id)].append({"text": text})
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "Привет! Я ThoughtInbox 🤖 Просто напиши мне мысль, и я её сохраню!")

@bot.message_handler(commands=['inbox'])
def inbox(message):
    if not os.path.exists(DATA_FILE):
        bot.reply_to(message, "Пока нет записей 🗒️")
        return
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    thoughts = data.get(str(message.from_user.id), [])
    if not thoughts:
        bot.reply_to(message, "Пока нет записей 🗒️")
    else:
        text = "\n".join([f"{i+1}. {t['text']}" for i, t in enumerate(thoughts[-10:])])
        bot.reply_to(message, f"Твои последние мысли:\n\n{text}")

@bot.message_handler(func=lambda m: True)
def add(message):
    save_thought(message.from_user.id, message.text)
    bot.reply_to(message, "💡 Мысль сохранена!")

print("🤖 Бот запущен. Нажми Ctrl+C для остановки.")
bot.polling(none_stop=True)
