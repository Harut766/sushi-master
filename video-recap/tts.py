"""Озвучка текста.

Движки:
  * edge  — бесплатные нейроголоса Microsoft (нужен интернет), звучат естественно;
  * espeak — офлайн, звучит роботизированно; подходит для проверки без интернета.
"""

import asyncio
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

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


@dataclass
class Spoken:
    text: str
    wav: Path
    duration: float


def synthesize(sentences, workdir, engine="edge", voice="ru-RU-DmitryNeural", rate="+0%",
               prefix="tts"):
    """Озвучивает каждое предложение в отдельный wav (48 кГц, стерео)."""
    synth = ENGINES[engine]
    result = []
    for i, sentence in enumerate(sentences, 1):
        print(f"  озвучка {i}/{len(sentences)}: {sentence[:60]}")
        raw = workdir / f"{prefix}_{i:03d}.{'mp3' if engine == 'edge' else 'wav'}"
        wav = workdir / f"{prefix}_{i:03d}_norm.wav"
        synth(sentence, raw, voice, rate)
        run(["ffmpeg", "-y", "-v", "error", "-i", raw,
             "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", wav])
        result.append(Spoken(sentence, wav, media_duration(wav)))
    return result


def assemble(spoken, workdir, name="narration"):
    """Склеивает озвученные предложения с паузами в один wav.
    Возвращает путь к файлу и тайминги каждого предложения (для субтитров)."""
    silence = workdir / "pause.wav"
    if not silence.exists():
        run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-t", PAUSE,
             "-i", "anullsrc=r=48000:cl=stereo", "-c:a", "pcm_s16le", silence])

    parts, lines, t = [], [], 0.0
    for item in spoken:
        lines.append(Line(item.text, t, t + item.duration))
        parts += [item.wav, silence]
        t += item.duration + PAUSE

    concat_list = workdir / f"{name}.txt"
    concat_list.write_text("".join(f"file '{p.name}'\n" for p in parts), encoding="utf-8")
    narration = workdir / f"{name}.wav"
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
         "-i", concat_list.name, "-c", "copy", narration.name], cwd=workdir)
    return narration, lines


def narrate(text, workdir, engine="edge", voice="ru-RU-DmitryNeural", rate="+0%"):
    sentences = split_sentences(text)
    if not sentences:
        raise SystemExit("Файл с текстом пустой.")
    return assemble(synthesize(sentences, workdir, engine, voice, rate), workdir)
