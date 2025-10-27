import os, json, random
from datetime import datetime
from telebot import TeleBot, types
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

# === Настройки ===
TOKEN = os.getenv("TOKEN")  # на Render хранится в Environment
bot = TeleBot(TOKEN, parse_mode="HTML")

DATA_FILE = "thoughts.json"
REMIND_FILE = "reminders.json"

scheduler = BackgroundScheduler(timezone="UTC")
scheduler.start()


# === Утилиты работы с файлами ===
def _read_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_data():
    return _read_json(DATA_FILE, {})

def save_data(data):
    _write_json(DATA_FILE, data)


# === Логика мыслей ===
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


# === Главное меню ===
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
    return _read_json(REMIND_FILE, {})

def save_reminders(data):
    _write_json(REMIND_FILE, data)

def schedule(uid, mode, value):
    job_id = f"rem_{uid}"
    try:
        scheduler.remove_job(job_id)
    except Exception:
        pass

    if mode == "daily":
        h, m = map(int, value.split(":"))
        trigger = CronTrigger(hour=h, minute=m)
    elif mode == "weekday":
        h, m = map(int, value.split(":"))
        trigger = CronTrigger(hour=h, minute=m, day_of_week="mon-fri")
    elif mode == "interval":
        trigger = IntervalTrigger(hours=int(value))
    else:
        return

    scheduler.add_job(lambda: send_rem(uid), trigger, id=job_id)

def send_rem(uid):
    bot.send_message(int(uid), "🐝 Напоминание! Есть новая мысль для улея? 💭", reply_markup=main_menu())

@bot.message_handler(commands=["remind"])
def remind_cmd(message):
    args = message.text.split(maxsplit=1)
    rem = reminders_db()
    uid = str(message.from_user.id)

    # показать текущее
    if len(args) == 1:
        bot.send_message(message.chat.id, f"🔔 Текущее: {rem.get(uid, {'mode':'off'})}")
        return

    arg = args[1].strip().lower()
    if arg == "off":
        try:
            scheduler.remove_job(f"rem_{uid}")
        except Exception:
            pass
        rem[uid] = {"mode": "off"}
        save_reminders(rem)
        bot.send_message(message.chat.id, "🔕 Напоминания отключены.")
        return

    # варианты: daily 10:00 | weekday 9:30 | interval 3
    try:
        mode, value = arg.split()
        schedule(uid, mode, value)
        rem[uid] = {"mode": mode, "value": value}
        save_reminders(rem)
        bot.send_message(message.chat.id, f"🔔 Установлено: {mode} {value}")
    except Exception:
        bot.send_message(message.chat.id, "❌ Формат: /remind daily 10:00 | weekday 9:30 | interval 3 | off")


# === Команды ===
@bot.message_handler(commands=["start"])
def start_cmd(message):
    bot.send_message(
        message.chat.id,
        "🐝 Привет! Я ThoughtInbox. Пиши мысль (можно с #тегами) — я сохраню.\n\nВыбирай действие:",
        reply_markup=main_menu()
    )

@bot.message_handler(commands=["help"])
def help_cmd(message):
    bot.send_message(
        message.chat.id,
        "📘 Команды:\n"
        "/inbox — последние мысли\n"
        "/review — мысли за сегодня\n"
        "/tags — список тегов\n"
        "/export — экспорт заметок\n"
        "/stats — статистика\n"
        "/find текст — поиск\n"
        "/random — случайная мысль\n"
        "/remind — показать статус\n"
        "/remind daily 10:00 — каждый день\n"
        "/remind weekday 9:30 — по будням\n"
        "/remind interval 3 — каждые 3 часа\n"
        "/remind off — выключить"
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
    res = [t for t in data.get(uid, []) if query in t["text"].lower()]
    if not res:
        bot.send_message(message.chat.id, "Ничего не найдено 🔍")
        return
    msg = "\n".join(f"• {t['text']} ({t['time']})" for t in res[-10:])
    bot.send_message(message.chat.id, f"🔎 Найдено:\n{msg}")

@bot.message_handler(commands=["review"])
def review_cmd(message):
    data = load_data()
    uid = str(message.from_user.id)
    today = datetime.utcnow().strftime("%Y-%m-%d")
    items = [t for t in data.get(uid, []) if today in t["time"]]
    if not items:
        bot.send_message(message.chat.id, "Сегодня мыслей нет ☀️")
        return
    msg = "\n".join(f"• {t['text']}" for t in items)
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
    tag_count = {}
    for t in items:
        for tg in t["tags"]:
            tag_count[tg] = tag_count.get(tg, 0) + 1
    top = ", ".join(f"#{k}({v})" for k, v in sorted(tag_count.items(), key=lambda x: -x[1]))
    bot.send_message(message.chat.id, f"📈 Всего мыслей: {total}\nПопулярные теги: {top or '—'}")


# === Callback-инлайн (фиксированная версия) ===
@bot.callback_query_handler(func=lambda c: True)
def callbacks(c):
    uid = str(c.from_user.id)
    chat_id = c.message.chat.id
    data_all = load_data()

    try:
        if c.data == "inbox":
            items = data_all.get(uid, [])
            if not items:
                bot.send_message(chat_id, "Нет мыслей 🗒️")
                return
            msg = "\n".join(f"• {t['text']} ({t['time']})" for t in items[-10:])
            bot.send_message(chat_id, f"🧾 Последние:\n{msg}")

        elif c.data == "today":
            today = datetime.utcnow().strftime("%Y-%m-%d")
            items = [t for t in data_all.get(uid, []) if today in t["time"]]
            if not items:
                bot.send_message(chat_id, "Сегодня мыслей нет ☀️")
                return
            msg = "\n".join(f"• {t['text']}" for t in items)
            bot.send_message(chat_id, f"🌅 Мысли за сегодня:\n{msg}")

        elif c.data == "tags":
            tags = sorted({tg for t in data_all.get(uid, []) for tg in t["tags"]})
            if not tags:
                bot.send_message(chat_id, "🏷️ Тегов пока нет.")
                return
            kb = types.InlineKeyboardMarkup()
            for tg in tags:
                kb.add(types.InlineKeyboardButton(f"#{tg}", callback_data=f"tag_{tg}"))
            bot.send_message(chat_id, "🏷️ Выбери тег:", reply_markup=kb)

        elif c.data.startswith("tag_"):
            tag = c.data[4:]
            items = [t for t in data_all.get(uid, []) if tag in t["tags"]]
            msg = "\n".join(f"• {t['text']}" for t in items) or "Нет мыслей с этим тегом."
            bot.send_message(chat_id, f"#{tag}:\n{msg}")

        elif c.data == "export":
            items = data_all.get(uid, [])
            if not items:
                bot.send_message(chat_id, "Нет мыслей для экспорта 📂")
                return
            fname = f"thoughts_{uid}.txt"
            with open(fname, "w", encoding="utf-8") as f:
                for t in items:
                    tags = " ".join(f"#{tg}" for tg in t["tags"])
                    f.write(f"{t['time']} — {t['text']} {tags}\n")
            with open(fname, "rb") as f:
                bot.send_document(chat_id, f)
            os.remove(fname)

        elif c.data == "random":
            items = data_all.get(uid, [])
            if not items:
                bot.send_message(chat_id, "Пока пусто 🐝")
                return
            t = random.choice(items)
            bot.send_message(chat_id, f"🎲 {t['text']}")

        elif c.data == "stats":
            items = data_all.get(uid, [])
            if not items:
                bot.send_message(chat_id, "Пока пусто 📉")
                return
            total = len(items)
            tag_count = {}
            for t in items:
                for tg in t["tags"]:
                    tag_count[tg] = tag_count.get(tg, 0) + 1
            top = ", ".join(f"#{k}({v})" for k, v in sorted(tag_count.items(), key=lambda x: -x[1]))
            bot.send_message(chat_id, f"📈 Всего мыслей: {total}\nПопулярные теги: {top or '—'}")

        elif c.data == "clear":
            data_all[uid] = []
            save_data(data_all)
            bot.send_message(chat_id, "🧹 Всё очищено.")

        elif c.data == "remind_menu":
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("🕐 Ежедневно 10:00", callback_data="rem_d_10"))
            kb.add(types.InlineKeyboardButton("📅 Будни 09:00", callback_data="rem_w_09"))
            kb.add(types.InlineKeyboardButton("⏱️ Каждые 3 часа", callback_data="rem_i_3"))
            kb.add(types.InlineKeyboardButton("❌ Выключить", callback_data="rem_off"))
            bot.send_message(chat_id, "Выбери режим напоминаний:", reply_markup=kb)

        elif c.data in ("rem_d_10", "rem_w_09", "rem_i_3", "rem_off"):
            rem = reminders_db()
            if c.data == "rem_off":
                try:
                    scheduler.remove_job(f"rem_{uid}")
                except Exception:
                    pass
                rem[uid] = {"mode": "off"}
                bot.send_message(chat_id, "🔕 Напоминания отключены.")
            elif c.data == "rem_d_10":
                schedule(uid, "daily", "10:00")
                rem[uid] = {"mode": "daily", "value": "10:00"}
                bot.send_message(chat_id, "🔔 Ежедневно в 10:00 (UTC).")
            elif c.data == "rem_w_09":
                schedule(uid, "weekday", "09:00")
                rem[uid] = {"mode": "weekday", "value": "09:00"}
                bot.send_message(chat_id, "📅 По будням в 09:00 (UTC).")
            elif c.data == "rem_i_3":
                schedule(uid, "interval", "3")
                rem[uid] = {"mode": "interval", "value": "3"}
                bot.send_message(chat_id, "⏱️ Каждые 3 часа.")
            save_reminders(rem)

    except Exception as e:
        try:
            bot.send_message(chat_id, f"⚠️ Ошибка: {e}")
        except:
            pass
        print("Callback error:", e)
    finally:
        try:
            bot.answer_callback_query(c.id)
        except:
            pass


# === Сохранение любого текста ===
@bot.message_handler(func=lambda m: True)
def save_msg(m):
    if not m.text.startswith("/"):
        add_thought(m.from_user.id, m.text)
        bot.send_message(m.chat.id, "💡 Сохранил!", reply_markup=main_menu())


# === Запуск ===
if __name__ == "__main__":
    # восстановить активные напоминания
    for uid, val in reminders_db().items():
        if val.get("mode") != "off":
            try:
                schedule(uid, val["mode"], val["value"])
            except Exception:
                pass

    # сбросить возможный вебхук и «хвосты» апдейтов
    try:
        bot.delete_webhook(drop_pending_updates=True)
    except Exception:
        pass

    bot.polling(none_stop=True)
                            
