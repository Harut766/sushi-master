# video-recap — нарезка фильмов и аниме с озвучкой

Скрипт делает короткий ролик для YouTube Shorts / TikTok / Reels:

1. **озвучивает ваш текст** бесплатным нейроголосом (edge-tts);
2. **находит интересные моменты** в фильме или серии — по громкости звука и темпу монтажа;
3. **режет и склеивает** их в хронологическом порядке ровно под длину озвучки;
4. переводит в **вертикальный формат 9:16** (кадр на размытом фоне или с обрезкой);
5. **вжигает субтитры** крупными словами, как в Shorts, и подмешивает фоновую музыку.

## Установка

1. Python 3.9+ — https://www.python.org/downloads/
2. ffmpeg:
   - Windows: `winget install ffmpeg` (потом перезапустить терминал)
   - macOS: `brew install ffmpeg`
   - Linux: `sudo apt install ffmpeg`
3. Библиотеки:
   ```bash
   cd video-recap
   pip install -r requirements.txt
   ```

## Использование

Напишите текст пересказа в файл `text.txt` (UTF-8), затем:

```bash
python recap.py --video film.mp4 --script text.txt --out short.mp4
```

Аниме (пропускает опенинг и эндинг по ~90 секунд):

```bash
python recap.py --video episode.mkv --script text.txt --preset anime --out anime.mp4
```

С фоновой музыкой, женским голосом и субтитрами капсом:

```bash
python recap.py --video film.mp4 --script text.txt --voice ru-RU-SvetlanaNeural \
    --music music.mp3 --upper --out short.mp4
```

Без озвучки — просто нарезка лучших моментов на 60 секунд с оригинальным звуком:

```bash
python recap.py --video film.mp4 --duration 60 --out highlights.mp4
```

### Основные параметры

| Параметр | Что делает |
|---|---|
| `--script` | текст озвучки; длина ролика = длина озвучки |
| `--voice` | голос. Список всех голосов: `edge-tts --list-voices` |
| `--rate` | скорость речи, например `+15%` |
| `--preset` | `film` (пропуск титров), `anime` (пропуск опенинга/эндинга), `none` |
| `--format` | `vertical` (9:16) или `horizontal` (16:9) |
| `--fit` | `blur` — кадр целиком на размытом фоне, `crop` — обрезать по бокам |
| `--music`, `--music-volume` | фоновая музыка и её громкость (0.12 по умолчанию) |
| `--original-volume` | громкость звука фильма под озвучкой (0.15 по умолчанию) |
| `--threshold` | чувствительность поиска сцен; если сцен мало — поставьте 20 |
| `--min-clip`, `--max-clip` | длина одного клипа в секундах (1.2–3.5) |
| `--skip-start`, `--skip-end` | вручную пропустить N секунд с начала/конца |
| `--no-subs`, `--upper`, `--words` | субтитры: выключить, капсом, слов на экране |
| `--engine espeak` | офлайн-озвучка без интернета (звучит роботизированно) |

Все параметры: `python recap.py --help`.

## Reddit-истории (`reddit_story.py`)

Голос читает историю поверх геймплея, в начале показывается карточка поста,
дальше крупные субтитры по центру экрана.

Файл истории: **первая строка — заголовок**, дальше текст.

```
Моя соседка три года воровала мой Wi-Fi, и я наконец отомстил
Всё началось, когда интернет стал подозрительно медленным...
```

```bash
python reddit_story.py --story story.txt --background gameplay.mp4 --out story.mp4
```

- `--background` — видео с геймплеем или **папка** с несколькими видео (каждый раз
  берётся случайное видео и случайный фрагмент).
- Длинные истории автоматически делятся на части (`story_part1.mp4`, `story_part2.mp4`…)
  примерно по `--part-length 150` секунд; в каждой части сначала звучит заголовок и «Часть N».
- `--subreddit`, `--username`, `--upvotes`, `--comments` — надписи на карточке.
- `--voice en-US-GuyNeural` — для англоязычных историй (там выше оплата за просмотры).
- `--music`, `--words 1` (по одному слову), `--upper`, `--background-volume 0.1`.

### Адаптация текста через Gemini (n8n)

Скрипт может пересказать историю заново: сюжет и смысл те же, а структура, слова,
крючок в начале и вопрос зрителю в конце каждый раз новые. Запрос идёт в ваш n8n,
а n8n вызывает Gemini с вашими ключами.

Настройка n8n (один раз):
1. В n8n: **Workflows → Import from File** → `n8n/adapt-story.json`.
2. Откройте узел **Google Gemini Chat Model** и выберите свои креды Gemini.
   Модель можно поменять там же (по умолчанию `gemini-2.5-flash`).
3. Нажмите **Active** (включить workflow). Адрес вебхука:
   `http://localhost:5678/webhook/adapt-story`. Если адрес другой — передайте
   `--n8n-url` или задайте переменную окружения `N8N_WEBHOOK_URL`.

Сначала посмотреть и поправить текст (рекомендую — ваши правки = больше оригинальности):

```bash
python rewrite.py --story story.txt --out adapted.txt --variants 3 --seconds 60
python reddit_story.py --story adapted_1.txt --background backgrounds/ --out story.mp4
```

Или сразу в видео:

```bash
python reddit_story.py --story story.txt --background backgrounds/ --rewrite --style irony
```

Стили: `drama`, `irony`, `calm`, `suspense` или свой текст (`--style "как стендап-комик"`).
`--language english` — написать историю на английском (не забудьте английский `--voice`).

### Сгенерированные фоны (`satisfying.py`)

Вместо геймплея — анимации, которые рисует код. Они полностью ваши: без чужих прав
и страйков, и каждая новая.

```bash
python satisfying.py --count 6 --duration 180 --out backgrounds/bg.mp4
python reddit_story.py --story story.txt --background backgrounds/ --out story.mp4
```

Режимы (`--mode`): `bounce` — растущий шарик прыгает в круге, `orbits` — точки на
кольцах выстраиваются в линию, `spiro` — спирограф; `random` — случайный.

Геймплей лучше записывать самому (например, свой паркур в Minecraft — Mojang разрешает
монетизировать видео с игрой). Чужие нарезки Subway Surfers и т. п. могут получить заявки.

## Советы для монетизации

- Платформы платят за **ваш вклад**: пишите свой пересказ, мнение, разбор, а не копируйте описание фильма.
- Меняйте подачу между роликами: однотипные ролики на поток YouTube отключает от монетизации.
- Фильмы в общественном достоянии (Internet Archive → Feature Films) — без риска страйков.
- Новые фильмы и аниме защищены авторским правом: часть роликов может получить заявки Content ID.
- Для TikTok Creator Rewards ролик должен быть длиннее 1 минуты.
