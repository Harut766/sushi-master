"""Общие помощники: запуск ffmpeg/ffprobe, длительность файлов, шрифты."""

import shutil
import subprocess
from pathlib import Path

from PIL import ImageFont


def require_ffmpeg():
    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            raise SystemExit(
                f"Не найден {tool}. Установите ffmpeg и добавьте его в PATH (см. README.md)."
            )


def run(cmd, cwd=None):
    """Запускает команду и падает с понятной ошибкой, если она не удалась."""
    cmd = [str(c) for c in cmd]
    proc = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        stderr = proc.stderr.decode(errors="replace")[-3000:]
        raise RuntimeError(f"Команда завершилась с ошибкой:\n{' '.join(cmd)}\n\n{stderr}")
    return proc


def media_duration(path):
    out = run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", path,
    ]).stdout
    return float(out.strip())


def has_audio(path):
    out = run([
        "ffprobe", "-v", "error", "-select_streams", "a",
        "-show_entries", "stream=index", "-of", "csv=p=0", path,
    ]).stdout
    return bool(out.strip())


FONT_CANDIDATES = [
    "C:/Windows/Fonts/arialbd.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]


def load_font(size, path=None):
    for candidate in [path] + FONT_CANDIDATES:
        if candidate and Path(candidate).exists():
            return ImageFont.truetype(str(candidate), size)
    raise SystemExit("Не найден шрифт с кириллицей. Укажите путь к .ttf через --font.")


def wrap_text(draw, text, font, width):
    lines, line = [], ""
    for word in text.split():
        candidate = f"{line} {word}".strip()
        if draw.textlength(candidate, font=font) <= width or not line:
            line = candidate
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines
