"""Озвучка текста.

Движки:
  * edge  — бесплатные нейроголоса Microsoft (нужен интернет), звучат естественно;
  * espeak — офлайн, звучит роботизированно; подходит для проверки без интернета.
"""

import asyncio
import re
import shutil
from dataclasses import dataclass

from utils import media_duration, run

PAUSE = 0.25  # пауза между предложениями, секунд


@dataclass
class Line:
    text: str
    start: float
    end: float


def split_sentences(text):
    text = re.sub(r"\s+", " ", text).strip()
    return [p.strip() for p in re.split(r"(?<=[.!?…])\s+", text) if p.strip()]


def _edge(text, out_path, voice, rate):
    import edge_tts

    async def speak():
        await edge_tts.Communicate(text, voice, rate=rate).save(str(out_path))

    for attempt in range(3):
        try:
            asyncio.run(speak())
            return
        except Exception as exc:  # сеть иногда отваливается — пробуем ещё раз
            if attempt == 2:
                raise RuntimeError(f"edge-tts не смог озвучить текст: {exc}") from exc


def _espeak(text, out_path, voice, rate):
    exe = shutil.which("espeak-ng") or shutil.which("espeak")
    if exe is None:
        raise SystemExit("Не найден espeak-ng. Установите его или используйте --engine edge.")
    # rate в формате edge ("+10%") переводим в слова в минуту для espeak.
    percent = int(rate.strip("%")) if rate else 0
    run([exe, "-v", voice, "-s", str(int(165 * (1 + percent / 100))), "-w", out_path, text])


ENGINES = {"edge": _edge, "espeak": _espeak}


def narrate(text, workdir, engine="edge", voice="ru-RU-DmitryNeural", rate="+0%"):
    """Озвучивает текст по предложениям и склеивает в один narration.wav.
    Возвращает путь к файлу и тайминги каждого предложения (для субтитров)."""
    synth = ENGINES[engine]
    sentences = split_sentences(text)
    if not sentences:
        raise SystemExit("Файл с текстом пустой.")

    silence = workdir / "pause.wav"
    run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-t", PAUSE,
         "-i", "anullsrc=r=48000:cl=stereo", "-c:a", "pcm_s16le", silence])

    parts, lines, t = [], [], 0.0
    for i, sentence in enumerate(sentences, 1):
        print(f"  озвучка {i}/{len(sentences)}: {sentence[:60]}")
        raw = workdir / f"tts_{i:03d}.{'mp3' if engine == 'edge' else 'wav'}"
        wav = workdir / f"tts_{i:03d}_norm.wav"
        synth(sentence, raw, voice, rate)
        run(["ffmpeg", "-y", "-v", "error", "-i", raw,
             "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", wav])
        duration = media_duration(wav)
        lines.append(Line(sentence, t, t + duration))
        parts += [wav, silence]
        t += duration + PAUSE

    concat_list = workdir / "narration.txt"
    concat_list.write_text("".join(f"file '{p.name}'\n" for p in parts), encoding="utf-8")
    narration = workdir / "narration.wav"
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
         "-i", concat_list.name, "-c", "copy", narration.name], cwd=workdir)
    return narration, lines
