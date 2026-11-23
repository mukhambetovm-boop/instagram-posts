"""Telegram-бот: раз в 15 минут читает сообщения владельца и выполняет команды.

Команды (можно писать по-русски, со слэшем или без):
  очередь            — показать запланированные посты
  опубликуй          — опубликовать ближайший пост прямо сейчас
  опубликуй ГГГГ-ММ-ДД — опубликовать пост за указанную дату
  помощь             — список команд

Отвечает только в чат владельца (ID из секрета TG_CHAT_ID или файла tg_chat_id.txt).
"""
import os, re, sys
import publish as p

API = f"https://api.telegram.org/bot{p.TG_TOKEN}"
HELP = ("Команды:\n"
        "• очередь — что запланировано\n"
        "• опубликуй — выпустить ближайший пост сейчас\n"
        "• опубликуй 2026-11-30 — выпустить пост за эту дату\n"
        "• помощь — этот список\n\n"
        "Я проверяю сообщения раз в ~15 минут, так что ответ придёт с задержкой.")


def queue():
    days = sorted(d for d in os.listdir("posts")
                  if os.path.isdir(os.path.join("posts", d))
                  and not os.path.exists(os.path.join("posts", d, "published.txt")))
    out = []
    for d in days:
        try:
            first = open(os.path.join("posts", d, "caption.txt"), encoding="utf-8").readline().strip()
        except OSError:
            first = "(нет подписи)"
        out.append((d, first[:70]))
    return out


def handle(text):
    t = text.strip().lower().lstrip("/")
    if t.startswith(("start", "help", "помощь", "команды")):
        p.tg(HELP)
    elif t.startswith(("queue", "очередь", "план")):
        q = queue()
        if not q:
            p.tg("📭 Очередь пуста — пора согласовать новые посты.")
        else:
            p.tg("📅 В очереди:\n" + "\n".join(f"• {d} — {f}" for d, f in q))
    elif t.startswith(("publish", "опубликуй", "публикуй", "опубликовать")):
        m = re.search(r"\d{4}-\d{2}-\d{2}", t)
        q = queue()
        if m:
            day = m.group(0)
            if day not in [d for d, _ in q]:
                p.tg(f"⚠️ Поста {day} нет в очереди (или он уже вышел).")
                return
        elif q:
            day = q[0][0]
        else:
            p.tg("📭 Публиковать нечего — очередь пуста.")
            return
        p.tg(f"⏳ Публикую пост {day}…")
        try:
            p.publish(day)
        except Exception as e:
            p.tg(f"❌ Не удалось опубликовать {day}:\n{e}")
    else:
        p.tg("Не понял команду 🙂\n\n" + HELP)


def main():
    if not p.TG_TOKEN:
        print("Нет TG_TOKEN")
        return
    owner = p.tg_chat_id()
    upd = p.http("GET", f"{API}/getUpdates", {"timeout": "0"}).get("result", [])
    if not upd:
        print("Новых сообщений нет.")
        return
    last = upd[-1]["update_id"]
    # Сразу подтверждаем получение, чтобы при сбое команда не выполнилась дважды
    p.http("GET", f"{API}/getUpdates", {"offset": str(last + 1), "timeout": "0"})
    for u in upd:
        msg = u.get("message") or {}
        chat = str(msg.get("chat", {}).get("id", ""))
        text = msg.get("text") or ""
        if not text or (owner and chat != owner):
            continue
        print("Команда:", text)
        handle(text)


if __name__ == "__main__":
    main()
