"""Общие помощники: запуск ffmpeg/ffprobe и чтение длительности файлов."""

import shutil
import subprocess


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
