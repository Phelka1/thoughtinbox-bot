import os, json, random
from datetime import datetime
from telebot import TeleBot, types
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

TOKEN = os.getenv("TOKEN")
bot = TeleBot(TOKEN, parse_mode="HTML")

DATA_FILE = "thoughts.json"
REMIND_FILE = "reminders.json"
scheduler = BackgroundScheduler(timezone="UTC")
scheduler.start()


# ==== Вспомогательные функции ====
def read_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_data():
    return read_json(DATA_FILE, {})

def save_data(data):
    write_json(DATA_FILE, data)


# ==== Работа с мыслями ====
def add_thought(uid, text):
    data = load_data()
    u = str(uid)
    if u not in data:
        data[u] = []
    tags = [w[1:].lower() for w in text.split() if w.startswith("#")]
    data[u].append({
        "id": len(data[u]) + 1,
        "text": text,
        "tags": tags,
        "time": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    })
    save_data(data)


# ==== Главное меню ====
def main_menu():
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("📋 Мысли", callback_data="inbox"),
        types.InlineKeyboardButton("🌅 Сегодня", callback_data="today")
    )
    kb.add(
        types.InlineKeyboardButton("🏷️ Теги", callback_data="tags"),
        types.InlineKeyboardButton("📤 Экспорт", callback_data="export")
    )
    kb.add(
        types.InlineKeyboardButton("🎲 Случайная", callback_data="random"),
        types.InlineKeyboardButton("📈 Статистика", callback_data="stats")
    )
    kb.add(types.InlineKeyboardButton("🧹 Очистить", callback_data="clear"))
    return kb


# ==== Команды ====
@bot.message_handler(commands=["start"])
def start(message):
    bot.send_message(
        message.chat.id,
        "🐝 Привет! Я ThoughtInbox — пчела, собирающая твои мысли в улей.\n"
        "Пиши идею, добавляй #теги — и я всё сохраню.\n\nВыбирай действие:",
        reply_markup=main_menu()
    )

@bot.message_handler(commands=["help"])
def help_cmd(message):
    bot.send_message(
        message.chat.id,
        "📘 Команды:\n"
        "/inbox — последние мысли\n"
        "/review — мысли за сегодня\n"
        "/tags — все теги\n"
        "/export — скачать мысли\n"
        "/clear — очистить\n"
        "/stats — статистика\n"
        "/remind HH:MM — напоминание раз в день\n"
        "/remind off — отключить напоминания\n"
        "/find текст — поиск по мыслям\n"
        "/random — случайная мысль\n\n"
        "💡 Просто напиши текст — я сохраню его."
    )


@bot.message_handler(commands=["find"])
def find_cmd(message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        bot.send_message(message.chat.id, "Используй: /find слово")
        return
    query = args[1].lower()
    data = load_data()
    uid = str(message.from_user.id)
    results = [t for t in data.get(uid, []) if query in t["text"].lower()]
    if not results:
        bot.send_message(message.chat.id, "Ничего не найдено 🔍")
        return
    msg = "\n".join([f"• {t['text']} ({t['time']})" for t in results[-10:]])
    bot.send_message(message.chat.id, f"🔎 Найдено:\n{msg}")


@bot.message_handler(commands=["review"])
def review_cmd(message):
    data = load_data()
    uid = str(message.from_user.id)
    today = datetime.utcnow().strftime("%Y-%m-%d")
    today_items = [t for t in data.get(uid, []) if today in t["time"]]
    if not today_items:
        bot.send_message(message.chat.id, "Сегодня мыслей нет ☀️")
        return
    msg = "\n".join([f"• {t['text']}" for t in today_items])
    bot.send_message(message.chat.id, f"🌅 Мысли за сегодня:\n{msg}")


@bot.message_handler(commands=["export"])
def export_cmd(message):
    data = load_data()
    uid = str(message.from_user.id)
    items = data.get(uid, [])
    if not items:
        bot.send_message(message.chat.id, "Нет мыслей для экспорта 📂")
        return

    fname = f"thoughts_{uid}.txt"
    with open(fname, "w", encoding="utf-8") as f:
        for t in items:
            tags = " ".join(f"#{tg}" for tg in t["tags"])
            f.write(f"{t['time']} — {t['text']} {tags}\n")
    with open(fname, "rb") as f:
        bot.send_document(message.chat.id, f)
    os.remove(fname)


@bot.message_handler(commands=["stats"])
def stats_cmd(message):
    data = load_data()
    uid = str(message.from_user.id)
    items = data.get(uid, [])
    if not items:
        bot.send_message(message.chat.id, "Пока пусто 📉")
        return
    total = len(items)
    tags = {}
    for t in items:
        for tg in t["tags"]:
            tags[tg] = tags.get(tg, 0) + 1
    top = ", ".join([f"#{k}({v})" for k, v in sorted(tags.items(), key=lambda x: -x[1])])
    bot.send_message(message.chat.id, f"📈 Всего мыслей: {total}\nПопулярные теги: {top if top else '—'}")


# ==== Напоминания ====
def reminders_db():
    return read_json(REMIND_FILE, {})

def save_reminders(data):
    write_json(REMIND_FILE, data)

def schedule(uid, h, m):
    job_id = f"rem_{uid}"
    try: scheduler.remove_job(job_id)
    except: pass
    trig = CronTrigger(hour=h, minute=m)
    scheduler.add_job(lambda: send_rem(uid), trig, id=job_id)

def send_rem(uid):
    bot.send_message(int(uid), "🐝 Напоминание! Есть новая мысль для улея? 💭", reply_markup=main_menu())

@bot.message_handler(commands=["remind"])
def remind_cmd(message):
    args = message.text.split(maxsplit=1)
    rem = reminders_db()
    uid = str(message.from_user.id)

    if len(args) == 1:
        val = rem.get(uid, "off")
        bot.send_message(message.chat.id, f"🔔 Напоминание сейчас: {val}")
        return

    arg = args[1].strip().lower()
    if arg == "off":
        try: scheduler.remove_job(f"rem_{uid}")
        except: pass
        rem[uid] = "off"
        save_reminders(rem)
        bot.send_message(message.chat.id, "🔕 Напоминания отключены.")
        return

    try:
        h, m = map(int, arg.split(":"))
        schedule(uid, h, m)
        rem[uid] = arg
        save_reminders(rem)
        bot.send_message(message.chat.id, f"🔔 Напоминание установлено на {arg}")
    except:
        bot.send_message(message.chat.id, "Формат: /remind HH:MM")


# ==== Inline кнопки ====
@bot.callback_query_handler(func=lambda c: True)
def callback(c):
    data = load_data()
    uid = str(c.from_user.id)

    if c.data == "inbox":
        items = data.get(uid, [])
        if not items:
            bot.answer_callback_query(c.id, "Нет мыслей 🗒️")
            return
        msg = "\n".join([f"• {t['text']} ({t['time']})" for t in items[-10:]])
        bot.send_message(c.message.chat.id, f"🧾 Последние:\n{msg}")

    elif c.data == "today":
        cmd = types.SimpleNamespace(message=c.message, from_user=c.from_user)
        review_cmd(cmd)

    elif c.data == "tags":
        tags = set()
        for t in data.get(uid, []):
            for tg in t["tags"]:
                tags.add(tg)
        if not tags:
            bot.send_message(c.message.chat.id, "🏷️ Тегов пока нет.")
            return
        kb = types.InlineKeyboardMarkup()
        for tg in sorted(tags):
            kb.add(types.InlineKeyboardButton(f"#{tg}", callback_data=f"tag_{tg}"))
        bot.send_message(c.message.chat.id, "🏷️ Выбери тег:", reply_markup=kb)

    elif c.data.startswith("tag_"):
        tag = c.data[4:]
        items = [t for t in data.get(uid, []) if tag in t["tags"]]
        msg = "\n".join([f"• {t['text']}" for t in items]) or "Нет мыслей с этим тегом."
        bot.send_message(c.message.chat.id, f"#{tag}:\n{msg}")

    elif c.data == "export":
        cmd = types.SimpleNamespace(message=c.message, from_user=c.from_user)
        export_cmd(cmd)

    elif c.data == "random":
        items = data.get(uid, [])
        if not items:
            bot.answer_callback_query(c.id, "Пока пусто 🐝")
            return
        t = random.choice(items)
        bot.send_message(c.message.chat.id, f"🎲 {t['text']}")

    elif c.data == "stats":
        cmd = types.SimpleNamespace(message=c.message, from_user=c.from_user)
        stats_cmd(cmd)

    elif c.data == "clear":
        data[uid] = []
        save_data(data)
        bot.send_message(c.message.chat.id, "🧹 Всё очищено.")

    bot.answer_callback_query(c.id)


# ==== Любой текст ====
@bot.message_handler(func=lambda m: True)
def save_msg(m):
    if not m.text.startswith("/"):
        add_thought(m.from_user.id, m.text)
        bot.send_message(m.chat.id, "💡 Сохранил!", reply_markup=main_menu())


# ==== Запуск ====
if __name__ == "__main__":
    for uid, val in reminders_db().items():
        if val != "off":
            try:
                h, m = map(int, val.split(":"))
                schedule(uid, h, m)
            except: pass
    bot.polling(none_stop=True)
    
    
