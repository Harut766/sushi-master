"""Адаптация истории через Gemini (запрос идёт в ваш n8n, см. n8n/adapt-story.json).

Сюжет и смысл сохраняются, а подача, структура и слова каждый раз новые:
цепляющее начало, живой язык, вопрос зрителю в конце.

Отдельный запуск (удобно сначала прочитать и поправить текст):
    python rewrite.py --story story.txt --out adapted.txt
"""

import argparse
import json
import os
import random
import re
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_URL = os.environ.get("N8N_WEBHOOK_URL", "http://localhost:5678/webhook/adapt-story")
WORDS_PER_SECOND = 2.5  # примерный темп озвучки

STYLES = {
    "drama": "драматично, с напряжением и паузами, как будто рассказываешь другу шёпотом",
    "irony": "с иронией и лёгким юмором, но без клоунады",
    "calm": "спокойно и искренне, как исповедь",
    "suspense": "как триллер: держи интригу до самого конца, раскрывай детали постепенно",
}

PROMPT = """Ты автор коротких историй для YouTube Shorts и TikTok.
Перескажи историю ниже заново.

Правила:
- Язык: {language}. Живой разговорный стиль, от первого лица.
- Сохрани сюжет, факты и смысл, но полностью поменяй структуру и формулировки:
  другой порядок подачи, другие фразы, не копируй предложения оригинала.
- Первое предложение — сильный крючок, чтобы зритель не пролистал.
- Тон: {style}.
- В конце — короткий вопрос к зрителю (например, «А вы бы простили?»).
- Длина истории: около {words} слов.
- Замени имена людей на другие, не упоминай реальных людей и компании.
- Без эмодзи, хэштегов, markdown и ремарок в скобках — текст будет читать голос.
- Придумай новый короткий заголовок в стиле поста Reddit.

Ответь строго JSON без пояснений: {{"title": "...", "story": "..."}}

Заголовок оригинала: {title}

История:
{story}
"""


def _parse(text):
    """Достаёт JSON из ответа модели (она иногда оборачивает его в ```json)."""
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise RuntimeError(f"Модель ответила не JSON:\n{text[:500]}")
    data = json.loads(match.group(0))
    title, story = data.get("title", "").strip(), data.get("story", "").strip()
    if not title or not story:
        raise RuntimeError(f"В ответе нет title или story:\n{text[:500]}")
    return title, story


def adapt(title, story, url=DEFAULT_URL, style=None, seconds=60, language="русский"):
    style = style or random.choice(list(STYLES))
    prompt = PROMPT.format(language=language, style=STYLES.get(style, style),
                           words=int(seconds * WORDS_PER_SECOND), title=title, story=story)
    request = urllib.request.Request(
        url, data=json.dumps({"prompt": prompt}).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    last_error = None
    for _ in range(3):
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                body = json.loads(response.read().decode("utf-8"))
            if isinstance(body, list):  # n8n иногда отвечает массивом
                body = body[0]
            return _parse(body.get("text", "") if isinstance(body, dict) else str(body))
        except urllib.error.URLError as exc:
            raise SystemExit(f"Не удалось достучаться до n8n ({url}): {exc}\n"
                             "Проверьте, что n8n запущен и workflow активирован.") from exc
        except (RuntimeError, json.JSONDecodeError) as exc:
            last_error = exc  # модель ответила криво — просим ещё раз
    raise RuntimeError(f"Gemini трижды вернул некорректный ответ: {last_error}")


def main():
    p = argparse.ArgumentParser(description="Адаптация истории через Gemini в n8n")
    p.add_argument("--story", required=True, type=Path, help="первая строка — заголовок")
    p.add_argument("--out", type=Path, default=Path("adapted.txt"))
    p.add_argument("--variants", type=int, default=1, help="сколько разных версий сделать")
    p.add_argument("--style", help=f"{', '.join(STYLES)} или свой текст; по умолчанию случайный")
    p.add_argument("--seconds", type=float, default=60, help="желаемая длина озвучки")
    p.add_argument("--language", default="русский")
    p.add_argument("--n8n-url", default=DEFAULT_URL)
    args = p.parse_args()

    lines = args.story.read_text(encoding="utf-8").strip().splitlines()
    title, story = lines[0].strip(), "\n".join(lines[1:])
    for n in range(1, args.variants + 1):
        out = args.out if args.variants == 1 else \
            args.out.with_name(f"{args.out.stem}_{n}{args.out.suffix}")
        new_title, new_story = adapt(title, story, args.n8n_url, args.style,
                                     args.seconds, args.language)
        out.write_text(f"{new_title}\n{new_story}\n", encoding="utf-8")
        print(f"Сохранено: {out} — {new_title}")


if __name__ == "__main__":
    main()
