import os, json, random
from datetime import datetime, timedelta
from telebot import TeleBot, types
from types import SimpleNamespace
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

TOKEN = os.getenv("TOKEN")
bot = TeleBot(TOKEN, parse_mode="HTML")

DATA_FILE = "thoughts.json"
REMIND_FILE = "reminders.json"
scheduler = BackgroundScheduler(timezone="UTC")
scheduler.start()


# === Вспомогательные функции ===
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


# === Работа с мыслями ===
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


# === Меню ===
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
    kb.add(
        types.InlineKeyboardButton("🔔 Напоминания", callback_data="remind_menu"),
        types.InlineKeyboardButton("🧹 Очистить", callback_data="clear")
    )
    return kb


# === Напоминания ===
def reminders_db():
    return read_json(REMIND_FILE, {})

def save_reminders(data):
    write_json(REMIND_FILE, data)


def schedule(uid, mode, value):
    job_id = f"rem_{uid}"
    try:
        scheduler.remove_job(job_id)
    except:
        pass

    if mode == "daily":
        h, m = map(int, value.split(":"))
        trig = CronTrigger(hour=h, minute=m)
    elif mode == "weekday":
        h, m = map(int, value.split(":"))
        trig = CronTrigger(hour=h, minute=m, day_of_week="mon-fri")
    elif mode == "interval":
        trig = IntervalTrigger(hours=int(value))
    else:
        return

    scheduler.add_job(lambda: send_rem(uid), trig, id=job_id)


def send_rem(uid):
    bot.send_message(int(uid), "🐝 Напоминание! Есть новая мысль для улея? 💭", reply_markup=main_menu())


@bot.message_handler(commands=["remind"])
def remind_cmd(message):
    args = message.text.split(maxsplit=1)
    rem = reminders_db()
    uid = str(message.from_user.id)

    if len(args) == 1:
        val = rem.get(uid, {"mode": "off"})
        bot.send_message(message.chat.id, f"🔔 Текущее напоминание: {val}")
        return

    arg = args[1].strip().lower()
    if arg == "off":
        try:
            scheduler.remove_job(f"rem_{uid}")
        except:
            pass
        rem[uid] = {"mode": "off"}
        save_reminders(rem)
        bot.send_message(message.chat.id, "🔕 Напоминания отключены.")
        return

    # Форматы: daily 10:00, weekday 9:00, interval 3
    try:
        parts = arg.split()
        mode = parts[0]
        value = parts[1]
        schedule(uid, mode, value)
        rem[uid] = {"mode": mode, "value": value}
        save_reminders(rem)
        bot.send_message(message.chat.id, f"🔔 Напоминание установлено: {mode} {value}")
    except Exception as e:
        bot.send_message(message.chat.id, "❌ Формат: /remind daily 10:00 | weekday 9:30 | interval 3 | off")


# === Callback ===
@bot.callback_query_handler(func=lambda c: True)
def callback(c):
    data = load_data()
    uid = str(c.from_user.id)

    if c.data == "remind_menu":
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("🕐 Ежедневно", callback_data="rem_daily"))
        kb.add(types.InlineKeyboardButton("📅 По будням", callback_data="rem_weekday"))
        kb.add(types.InlineKeyboardButton("⏱️ Каждые 3 часа", callback_data="rem_interval"))
        kb.add(types.InlineKeyboardButton("❌ Выключить", callback_data="rem_off"))
        bot.send_message(c.message.chat.id, "Выбери тип напоминания:", reply_markup=kb)

    elif c.data.startswith("rem_"):
        rem = reminders_db()
        if c.data == "rem_off":
            try:
                scheduler.remove_job(f"rem_{uid}")
            except:
                pass
            rem[uid] = {"mode": "off"}
            bot.send_message(c.message.chat.id, "🔕 Напоминания отключены.")
        elif c.data == "rem_daily":
            schedule(uid, "daily", "10:00")
            rem[uid] = {"mode": "daily", "value": "10:00"}
            bot.send_message(c.message.chat.id, "🔔 Ежедневное напоминание установлено (10:00 UTC).")
        elif c.data == "rem_weekday":
            schedule(uid, "weekday", "09:00")
            rem[uid] = {"mode": "weekday", "value": "09:00"}
            bot.send_message(c.message.chat.id, "📅 Напоминание по будням (09:00 UTC).")
        elif c.data == "rem_interval":
            schedule(uid, "interval", "3")
            rem[uid] = {"mode": "interval", "value": "3"}
            bot.send_message(c.message.chat.id, "⏱️ Напоминание каждые 3 часа.")
        save_reminders(rem)
    bot.answer_callback_query(c.id)


# === Сохранение мыслей ===
@bot.message_handler(func=lambda m: True)
def save_msg(m):
    if not m.text.startswith("/"):
        add_thought(m.from_user.id, m.text)
        bot.send_message(m.chat.id, "💡 Сохранил!", reply_markup=main_menu())


# === Запуск ===
if __name__ == "__main__":
    for uid, val in reminders_db().items():
        if val.get("mode") != "off":
            try:
                schedule(uid, val["mode"], val["value"])
            except:
                pass
    bot.polling(none_stop=True)
    if __name__ == "__main__":
    # восстановить расписания напоминаний (оставляем как было)
    for uid, val in reminders_db().items():
        if val.get("mode") != "off":
            try:
                schedule(uid, val["mode"], val["value"])
            except:
                pass

    # ВАЖНО: перед запуском опроса — попросить Телеграм "забыть" старые подключения
    try:
        bot.delete_webhook(drop_pending_updates=True)
    except:
        pass

    bot.polling(none_stop=True)
    
    
