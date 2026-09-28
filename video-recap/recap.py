"""Делает короткий ролик из фильма или аниме: находит интересные моменты,
режет, склеивает, озвучивает ваш текст и добавляет субтитры.

Пример:
    python recap.py --video film.mp4 --script text.txt --out short.mp4
"""

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import render  # noqa: E402
import scenes  # noqa: E402
import subtitles  # noqa: E402
import tts  # noqa: E402
from utils import has_audio, media_duration, require_ffmpeg  # noqa: E402

# Сколько отрезать с начала и конца, чтобы не брать заставки и титры.
PRESETS = {
    "film": lambda d: (0.02 * d, 0.07 * d),
    "anime": lambda d: (min(90.0, 0.1 * d), min(90.0, 0.1 * d)),  # опенинг и эндинг
    "none": lambda d: (0.0, 0.0),
}


def parse_args():
    p = argparse.ArgumentParser(description="Нарезка интересных моментов с озвучкой")
    p.add_argument("--video", required=True, type=Path, help="исходный фильм / серия")
    p.add_argument("--script", type=Path, help="текст озвучки (.txt). Без него — просто нарезка")
    p.add_argument("--out", type=Path, default=Path("short.mp4"), help="куда сохранить ролик")

    g = p.add_argument_group("озвучка")
    g.add_argument("--engine", choices=tts.ENGINES, default="edge")
    g.add_argument("--voice", default=None,
                   help="голос (edge: ru-RU-DmitryNeural, ru-RU-SvetlanaNeural, en-US-GuyNeural…; "
                        "espeak: ru, en)")
    g.add_argument("--rate", default="+5%", help="скорость речи, например +10%% или -5%%")

    g = p.add_argument_group("нарезка")
    g.add_argument("--preset", choices=PRESETS, default="film",
                   help="film — пропустить титры; anime — пропустить опенинг/эндинг")
    g.add_argument("--duration", type=float, default=60,
                   help="длина ролика в секундах, если нет --script")
    g.add_argument("--threshold", type=float, default=27.0,
                   help="чувствительность поиска сцен: меньше = больше сцен")
    g.add_argument("--min-clip", type=float, default=1.2, help="мин. длина клипа, с")
    g.add_argument("--max-clip", type=float, default=3.5, help="макс. длина клипа, с")
    g.add_argument("--skip-start", type=float, help="пропустить N секунд с начала")
    g.add_argument("--skip-end", type=float, help="пропустить N секунд с конца")

    g = p.add_argument_group("оформление")
    g.add_argument("--format", choices=["vertical", "horizontal"], default="vertical",
                   help="vertical = 9:16 для Shorts/TikTok")
    g.add_argument("--fit", choices=["blur", "crop"], default="blur",
                   help="blur — кадр целиком на размытом фоне; crop — обрезать по бокам")
    g.add_argument("--music", type=Path, help="фоновая музыка")
    g.add_argument("--music-volume", type=float, default=0.12)
    g.add_argument("--original-volume", type=float, default=None,
                   help="громкость звука фильма (по умолчанию 0.15 с озвучкой, 1.0 без)")
    g.add_argument("--no-subs", action="store_true", help="без субтитров")
    g.add_argument("--upper", action="store_true", help="субтитры капсом")
    g.add_argument("--words", type=int, default=4, help="слов в одном субтитре")

    p.add_argument("--keep-temp", action="store_true", help="не удалять временные файлы")
    return p.parse_args()


def main():
    args = parse_args()
    require_ffmpeg()
    if not args.video.exists():
        raise SystemExit(f"Нет файла {args.video}")
    if args.voice is None:
        args.voice = "ru" if args.engine == "espeak" else "ru-RU-DmitryNeural"

    workdir = Path(tempfile.mkdtemp(prefix="recap_"))
    try:
        duration = media_duration(args.video)
        skip_start, skip_end = PRESETS[args.preset](duration)
        if args.skip_start is not None:
            skip_start = args.skip_start
        if args.skip_end is not None:
            skip_end = args.skip_end

        narration, lines = None, []
        if args.script:
            print("1/4 Озвучиваю текст…")
            text = args.script.read_text(encoding="utf-8")
            narration, lines = tts.narrate(text, workdir, args.engine, args.voice, args.rate)
            target = lines[-1].end + 0.6
        else:
            print("1/4 Текста нет — делаю нарезку без озвучки.")
            target = args.duration
        original_volume = args.original_volume
        if original_volume is None:
            original_volume = 0.15 if narration else 1.0

        print("2/4 Ищу сцены и интересные моменты…")
        audio = has_audio(args.video)
        rms = scenes.audio_rms(args.video) if audio else []
        if len(rms) == 0:
            rms = np.zeros(int(duration / scenes.RMS_STEP) + 1)
        found = scenes.detect_scenes(args.video, args.threshold, min_scene_len=0.5)
        scenes.score_scenes(found, rms)
        clips = scenes.select_clips(found, rms, target, duration, args.min_clip, args.max_clip,
                                    skip_start, skip_end)
        print(f"   сцен найдено: {len(found)}, в ролик идёт клипов: {len(clips)}")

        print("3/4 Режу и склеиваю…")
        paths = render.render_clips(args.video, clips, workdir, args.format, args.fit, audio)
        joined = render.concat(paths, workdir)

        print("4/4 Свожу звук и субтитры…")
        subs = None
        if lines and not args.no_subs:
            subs = workdir / "subs.ass"
            subtitles.build_ass(lines, subs, args.format, args.words, args.upper)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        render.final_mix(joined, args.out, workdir, narration,
                         args.music.resolve() if args.music else None, subs,
                         original_volume, args.music_volume)

        length = media_duration(args.out)
        print(f"\nГотово: {args.out} ({length:.1f} с)")
        if length < 61:
            print("Подсказка: для TikTok Creator Rewards ролик должен быть длиннее 1 минуты.")
    finally:
        if args.keep_temp:
            print(f"Временные файлы: {workdir}")
        else:
            shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    main()
