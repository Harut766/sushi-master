"""Reddit-история: голос читает пост поверх геймплея (Minecraft-паркур,
Subway Surfers и т. п.), крупные субтитры по центру, в начале — карточка поста.

Формат файла истории: первая строка — заголовок, дальше — текст.

Пример:
    python reddit_story.py --story story.txt --background gameplay.mp4 --out story.mp4
"""

import argparse
import random
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import card  # noqa: E402
import subtitles  # noqa: E402
import tts  # noqa: E402
from utils import has_audio, media_duration, require_ffmpeg, run  # noqa: E402

VIDEO_EXT = {".mp4", ".mkv", ".mov", ".webm", ".avi"}


def parse_args():
    p = argparse.ArgumentParser(description="Reddit-история поверх геймплея")
    p.add_argument("--story", required=True, type=Path,
                   help="текст: первая строка — заголовок, дальше — история")
    p.add_argument("--background", required=True, type=Path,
                   help="видео с геймплеем или папка с видео (возьмётся случайное)")
    p.add_argument("--out", type=Path, default=Path("story.mp4"))

    g = p.add_argument_group("озвучка")
    g.add_argument("--engine", choices=tts.ENGINES, default="edge")
    g.add_argument("--voice", default=None, help="например ru-RU-DmitryNeural, en-US-GuyNeural")
    g.add_argument("--rate", default="+10%", help="скорость речи")

    g = p.add_argument_group("карточка поста")
    g.add_argument("--subreddit", default="r/AskReddit")
    g.add_argument("--username", default="u/throwaway")
    g.add_argument("--upvotes", default="24.1k")
    g.add_argument("--comments", default="1.3k")
    g.add_argument("--font", help="путь к .ttf-шрифту для карточки")

    g = p.add_argument_group("ролик")
    g.add_argument("--part-length", type=float, default=150,
                   help="длинные истории делятся на части примерно такой длины, с (0 — не делить)")
    g.add_argument("--part-label", default="Часть {n}.",
                   help="что говорить в начале каждой части после заголовка")
    g.add_argument("--music", type=Path, help="фоновая музыка")
    g.add_argument("--music-volume", type=float, default=0.08)
    g.add_argument("--background-volume", type=float, default=0.0,
                   help="громкость звука геймплея (по умолчанию выключен)")
    g.add_argument("--words", type=int, default=2, help="слов в одном субтитре")
    g.add_argument("--upper", action="store_true", help="субтитры капсом")
    g.add_argument("--seed", type=int, help="зафиксировать случайный выбор фрагмента фона")
    p.add_argument("--keep-temp", action="store_true")
    return p.parse_args()


def read_story(path):
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    if len(lines) < 2:
        raise SystemExit("В файле истории нужна первая строка-заголовок и сам текст ниже.")
    title = lines[0].strip()
    # Точка в конце нужна, чтобы заголовок озвучивался отдельной фразой.
    spoken = title if title[-1] in ".!?…" else title + "."
    return title, spoken, "\n".join(lines[1:])


def split_parts(body, part_length):
    """Делит озвученные предложения на части, не разрывая предложения."""
    if part_length <= 0:
        return [body]
    parts, current, total = [], [], 0.0
    for item in body:
        if current and total + item.duration > part_length:
            parts.append(current)
            current, total = [], 0.0
        current.append(item)
        total += item.duration + tts.PAUSE
    if current:
        # Слишком короткий хвост приклеиваем к предыдущей части.
        if parts and total < 20:
            parts[-1].extend(current)
        else:
            parts.append(current)
    return parts


def pick_background(path):
    if path.is_dir():
        videos = [p for p in path.iterdir() if p.suffix.lower() in VIDEO_EXT]
        if not videos:
            raise SystemExit(f"В папке {path} нет видео.")
        return random.choice(videos)
    if not path.exists():
        raise SystemExit(f"Нет файла {path}")
    return path


def render_part(background, narration, card_png, subs, card_until, length, out, workdir,
                music=None, music_volume=0.08, background_volume=0.0):
    bg_duration = media_duration(background)
    start = random.uniform(0, bg_duration - length) if bg_duration > length + 1 else 0.0

    cmd = ["ffmpeg", "-y", "-v", "error",
           "-stream_loop", "-1", "-ss", f"{start:.2f}", "-i", background,
           "-i", narration.name, "-loop", "1", "-i", card_png.name]
    audio = ["[1:a]volume=1.0[n]"]
    labels = ["[n]"]
    idx = 3
    if background_volume > 0 and has_audio(background):
        audio.append(f"[0:a]volume={background_volume}[b]")
        labels.append("[b]")
    if music:
        cmd += ["-stream_loop", "-1", "-i", music]
        audio.append(f"[{idx}:a]volume={music_volume}[m]")
        labels.append("[m]")
    audio.append(f"{''.join(labels)}amix=inputs={len(labels)}:duration=first:normalize=0,"
                 "alimiter=limit=0.95[aout]")
    video = [
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
        "fps=30,setsar=1[bg]",
        f"[bg][2:v]overlay=(W-w)/2:(H-h)/2:enable='lte(t,{card_until:.2f})'[ov]",
        f"[ov]subtitles={subs.name},format=yuv420p[vout]",
    ]
    cmd += [
        "-filter_complex", ";".join(video + audio),
        "-map", "[vout]", "-map", "[aout]", "-t", f"{length:.2f}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out.resolve(),
    ]
    run(cmd, cwd=workdir)


def main():
    args = parse_args()
    require_ffmpeg()
    if args.seed is not None:
        random.seed(args.seed)
    if args.voice is None:
        args.voice = "ru" if args.engine == "espeak" else "ru-RU-DmitryNeural"

    title, spoken_title, text = read_story(args.story)
    background = pick_background(args.background).resolve()
    workdir = Path(tempfile.mkdtemp(prefix="reddit_"))
    try:
        print("1/3 Озвучиваю историю…")
        speak = dict(engine=args.engine, voice=args.voice, rate=args.rate)
        title_spoken = tts.synthesize(tts.split_sentences(spoken_title), workdir, prefix="title", **speak)
        body = tts.synthesize(tts.split_sentences(text), workdir, prefix="body", **speak)
        parts = split_parts(body, args.part_length)

        print("2/3 Рисую карточку поста…")
        card_png = card.make_card(title, workdir / "card.png", args.subreddit, args.username,
                                  args.upvotes, args.comments, font_path=args.font)

        print(f"3/3 Собираю видео ({len(parts)} шт.)…")
        args.out.parent.mkdir(parents=True, exist_ok=True)
        outputs = []
        for n, part in enumerate(parts, 1):
            intro = list(title_spoken)
            if len(parts) > 1:
                intro += tts.synthesize([args.part_label.format(n=n)], workdir,
                                        prefix=f"label{n}", **speak)
            narration, lines = tts.assemble(intro + part, workdir, name=f"narration{n}")
            card_until = lines[len(intro) - 1].end
            subs = workdir / f"subs{n}.ass"
            # Пока видна карточка, субтитры не нужны — заголовок и так на экране.
            subtitles.build_ass(lines[len(intro):], subs, "vertical", args.words,
                                args.upper, center=True)
            out = args.out if len(parts) == 1 else \
                args.out.with_name(f"{args.out.stem}_part{n}{args.out.suffix}")
            render_part(background, narration, card_png, subs, card_until,
                        lines[-1].end + 0.6, out, workdir,
                        args.music.resolve() if args.music else None,
                        args.music_volume, args.background_volume)
            outputs.append(out)

        print("\nГотово:")
        for out in outputs:
            print(f"  {out} ({media_duration(out):.1f} с)")
    finally:
        if args.keep_temp:
            print(f"Временные файлы: {workdir}")
        else:
            shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    main()
