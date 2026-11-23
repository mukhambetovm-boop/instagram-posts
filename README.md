# Автопостинг @mukhambetov.yurist

- `posts/ГГГГ-ММ-ДД/` — пост на эту дату: слайды `1.png`, `2.png`, … и подпись `caption.txt`.
- Публикация — автоматически в Пн, Ср, Пт в 10:00 по Астане (GitHub Actions).
- После публикации в папке появляется `published.txt`, а в Telegram приходит сообщение.

Секреты (Settings → Secrets and variables → Actions): `IG_TOKEN`, `TG_TOKEN`, при необходимости `TG_CHAT_ID`.

Проверка подключения: Actions → «Публикация в Instagram» → Run workflow → `check`.
