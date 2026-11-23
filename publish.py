"""Публикует пост дня в Instagram и сообщает в Telegram.

Пост дня — папка posts/ГГГГ-ММ-ДД/ (дата по Астане) со слайдами 1.png, 2.png, ...
и файлом caption.txt. Если в папке уже есть published.txt, пост пропускается.

Режимы:
  python publish.py            — опубликовать пост на сегодня (если есть)
  python publish.py check      — проверить токены, ничего не публикуя
  python publish.py 2026-11-25 — опубликовать пост за указанную дату
"""
import json, os, sys, time, datetime, urllib.parse, urllib.request, urllib.error
from zoneinfo import ZoneInfo

IG_TOKEN = os.environ.get("IG_TOKEN", "").strip()
TG_TOKEN = os.environ.get("TG_TOKEN", "").strip()
TG_CHAT_ID = os.environ.get("TG_CHAT_ID", "").strip()
REPO = os.environ.get("GITHUB_REPOSITORY", "")
BRANCH = os.environ.get("GITHUB_REF_NAME", "main")
# ID профессионального аккаунта @mukhambetov.yurist (из панели Meta)
IG_USER_ID = os.environ.get("IG_USER_ID", "").strip() or "17841410486663764"
# Токен Instagram Login начинается с "IG", токен Facebook/системного пользователя — с "EA"
FB_TOKEN = IG_TOKEN.startswith("EA")
IG = "https://graph.facebook.com/v23.0" if FB_TOKEN else "https://graph.instagram.com"


def http(method, url, params=None):
    data = None
    if params and method == "GET":
        url += "?" + urllib.parse.urlencode(params)
    elif params:
        data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        raise RuntimeError(f"{e.code} {url.split('?')[0]}: {body}") from None


def tg_chat_id():
    global TG_CHAT_ID
    if TG_CHAT_ID or not TG_TOKEN:
        return TG_CHAT_ID
    upd = http("GET", f"https://api.telegram.org/bot{TG_TOKEN}/getUpdates").get("result", [])
    for u in reversed(upd):
        msg = u.get("message") or u.get("my_chat_member") or {}
        if msg.get("chat", {}).get("id"):
            TG_CHAT_ID = str(msg["chat"]["id"])
            break
    return TG_CHAT_ID


def tg(text):
    print(text)
    if not TG_TOKEN:
        return
    chat = tg_chat_id()
    if not chat:
        print("Telegram: не найден чат. Нажмите Start у бота и запустите проверку ещё раз.")
        return
    try:
        http("POST", f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
             {"chat_id": chat, "text": text, "disable_web_page_preview": "true"})
    except Exception as e:
        print("Telegram error:", e)


def me():
    if FB_TOKEN:
        r = http("GET", f"{IG}/{IG_USER_ID}", {"fields": "id,username", "access_token": IG_TOKEN})
        return {"user_id": r["id"], "username": r.get("username")}
    return http("GET", f"{IG}/me", {"fields": "user_id,username", "access_token": IG_TOKEN})


def refresh_token():
    """Продлевает долгосрочный токен Instagram ещё на 60 дней."""
    if FB_TOKEN:
        return "∞"  # токен системного пользователя бессрочный
    try:
        r = http("GET", f"{IG}/refresh_access_token",
                 {"grant_type": "ig_refresh_token", "access_token": IG_TOKEN})
        days = int(r.get("expires_in", 0)) // 86400
        if r.get("access_token") and r["access_token"] != IG_TOKEN:
            tg("⚠️ Instagram выдал новый токен. Обновите секрет IG_TOKEN на GitHub "
               "(новый токен — в логе запуска, раздел Actions).")
            print("NEW IG_TOKEN:", r["access_token"])
        return days
    except Exception as e:
        print("Не удалось продлить токен:", e)
        return None


def wait_ready(container_id):
    for _ in range(30):
        st = http("GET", f"{IG}/{container_id}",
                  {"fields": "status_code", "access_token": IG_TOKEN}).get("status_code")
        if st == "FINISHED":
            return
        if st in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"контейнер {container_id}: статус {st}")
        time.sleep(5)
    raise RuntimeError(f"контейнер {container_id} не обработался за 2.5 минуты")


def publish(day):
    folder = os.path.join("posts", day)
    if not os.path.isdir(folder):
        print(f"На {day} поста нет — ничего не делаю.")
        return
    if os.path.exists(os.path.join(folder, "published.txt")):
        print(f"Пост {day} уже опубликован.")
        return
    slides = sorted((f for f in os.listdir(folder) if f.lower().endswith((".png", ".jpg", ".jpeg"))),
                    key=lambda f: int(os.path.splitext(f)[0]) if os.path.splitext(f)[0].isdigit() else 999)
    caption = open(os.path.join(folder, "caption.txt"), encoding="utf-8").read().strip()
    urls = [f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/posts/{day}/{urllib.parse.quote(s)}"
            for s in slides]
    uid = me()["user_id"]

    if len(urls) == 1:
        c = http("POST", f"{IG}/{uid}/media",
                 {"image_url": urls[0], "caption": caption, "access_token": IG_TOKEN})["id"]
    else:
        children = []
        for u in urls[:10]:
            cid = http("POST", f"{IG}/{uid}/media",
                       {"image_url": u, "is_carousel_item": "true", "access_token": IG_TOKEN})["id"]
            children.append(cid)
        for cid in children:
            wait_ready(cid)
        c = http("POST", f"{IG}/{uid}/media",
                 {"media_type": "CAROUSEL", "children": ",".join(children),
                  "caption": caption, "access_token": IG_TOKEN})["id"]
    wait_ready(c)
    media_id = http("POST", f"{IG}/{uid}/media_publish",
                    {"creation_id": c, "access_token": IG_TOKEN})["id"]
    link = http("GET", f"{IG}/{media_id}",
                {"fields": "permalink", "access_token": IG_TOKEN}).get("permalink", "")
    with open(os.path.join(folder, "published.txt"), "w") as fh:
        fh.write(f"{datetime.datetime.now().isoformat()} {media_id} {link}\n")
    first_line = caption.splitlines()[0][:80]
    tg(f"✅ Пост вышел в Instagram\n«{first_line}»\n{link}")


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if not IG_TOKEN:
        tg("❌ Не задан секрет IG_TOKEN на GitHub.")
        sys.exit(1)
    if arg == "check":
        info = me()
        days = refresh_token()
        upcoming = sorted(d for d in os.listdir("posts")
                          if not os.path.exists(os.path.join("posts", d, "published.txt")))
        token_line = ("Токен бессрочный." if days == "∞" else
                      f"Токен действует ещё ~{days} дн." if days else "Срок токена узнать не удалось.")
        tg(f"🔧 Проверка пройдена.\nInstagram: @{info.get('username')}\n{token_line}")
        tg("📅 В очереди: " + (", ".join(upcoming) if upcoming else "пусто — пора согласовать посты"))
        return
    day = arg or datetime.datetime.now(ZoneInfo("Asia/Almaty")).strftime("%Y-%m-%d")
    try:
        refresh_token()
        publish(day)
    except Exception as e:
        tg(f"❌ Не удалось опубликовать пост {day}:\n{e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
