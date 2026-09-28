"""Поиск сцен и выбор «интересных» моментов.

Интересность сцены считается по двум признакам:
  * громкость звука (крики, взрывы, музыка на пике, драки);
  * темп монтажа вокруг сцены (много коротких склеек = экшен).
"""

import subprocess
from dataclasses import dataclass

import numpy as np

RMS_STEP = 0.1  # шаг анализа громкости, секунд


@dataclass
class Scene:
    start: float
    end: float
    score: float = 0.0

    @property
    def duration(self):
        return self.end - self.start


@dataclass
class Clip:
    start: float
    duration: float


def detect_scenes(video, threshold=27.0, min_scene_len=0.5):
    from scenedetect import ContentDetector, SceneManager, open_video

    stream = open_video(str(video))
    manager = SceneManager()
    manager.auto_downscale = True
    manager.add_detector(ContentDetector(
        threshold=threshold,
        min_scene_len=max(1, int(min_scene_len * stream.frame_rate)),
    ))
    manager.detect_scenes(stream, show_progress=True)
    return [
        Scene(start.get_seconds(), end.get_seconds())
        for start, end in manager.get_scene_list(start_in_scene=True)
    ]


def audio_rms(video, sample_rate=8000):
    """Громкость звука окнами по RMS_STEP секунд. Читает поток кусками, чтобы
    не держать в памяти звук двухчасового фильма целиком."""
    hop = int(sample_rate * RMS_STEP)
    cmd = [
        "ffmpeg", "-v", "error", "-i", str(video), "-vn",
        "-ac", "1", "-ar", str(sample_rate), "-f", "f32le", "-",
    ]
    values = []
    leftover = np.empty(0, dtype=np.float32)
    with subprocess.Popen(cmd, stdout=subprocess.PIPE) as proc:
        while True:
            chunk = proc.stdout.read(hop * 4 * 1000)
            if not chunk:
                break
            samples = np.concatenate([leftover, np.frombuffer(chunk, dtype=np.float32)])
            n = len(samples) // hop
            frames = samples[: n * hop].reshape(n, hop)
            values.append(np.sqrt((frames ** 2).mean(axis=1)))
            leftover = samples[n * hop:]
    if not values:
        return np.zeros(0, dtype=np.float32)
    return np.concatenate(values)


def _rank(values):
    """Переводит значения в ранги 0..1 — устойчиво к выбросам."""
    values = np.asarray(values, dtype=float)
    if len(values) < 2 or np.ptp(values) == 0:
        return np.zeros(len(values))
    return values.argsort().argsort() / (len(values) - 1)


def _window(rms, start, end):
    a, b = int(start / RMS_STEP), max(int(start / RMS_STEP) + 1, int(end / RMS_STEP))
    return rms[a:b]


def score_scenes(scenes, rms, pace_window=8.0):
    loudness = []
    for s in scenes:
        w = _window(rms, s.start, s.end)
        loudness.append(20 * np.log10(np.percentile(w, 75) + 1e-6) if len(w) else -120.0)

    cuts = np.array([s.start for s in scenes])
    pace = []
    for s in scenes:
        center = (s.start + s.end) / 2
        pace.append(np.sum(np.abs(cuts - center) <= pace_window))

    scores = 0.65 * _rank(loudness) + 0.35 * _rank(pace)
    for s, score in zip(scenes, scores):
        s.score = float(score)
    return scenes


def _loudest_window(rms, scene, length):
    """Самый громкий отрезок нужной длины внутри сцены."""
    if scene.duration <= length:
        return scene.start
    w = _window(rms, scene.start, scene.end)
    n = max(1, int(length / RMS_STEP))
    if len(w) <= n:
        return scene.start
    sums = np.convolve(w, np.ones(n), mode="valid")
    offset = int(np.argmax(sums)) * RMS_STEP
    return min(scene.start + offset, scene.end - length)


def select_clips(scenes, rms, target, video_duration, min_clip=1.2, max_clip=3.5,
                 skip_start=0.0, skip_end=0.0):
    """Берёт лучшие сцены, пока их суммарная длина не покроет target секунд,
    и возвращает клипы в хронологическом порядке (чтобы сюжет не путался)."""
    usable = [
        s for s in scenes
        if s.duration >= min_clip and s.start >= skip_start and s.end <= video_duration - skip_end
    ]
    if not usable:
        usable = [s for s in scenes if s.duration >= min_clip] or list(scenes)

    chosen, total = [], 0.0
    for s in sorted(usable, key=lambda s: s.score, reverse=True):
        if total >= target:
            break
        chosen.append(s)
        total += min(s.duration, max_clip)
    chosen.sort(key=lambda s: s.start)

    clips = []
    for s in chosen:
        length = min(s.duration, max_clip)
        clips.append(Clip(_loudest_window(rms, s, length), length))

    if total < target:
        print(f"[!] Интересных сцен хватает только на {total:.1f} из {target:.1f} с — "
              "клипы пойдут по кругу. Попробуйте уменьшить --threshold или --min-clip.")
        base = list(clips)
        while total < target and base:
            for c in base:
                clips.append(Clip(c.start, c.duration))
                total += c.duration
                if total >= target:
                    break

    # Подрезаем все клипы пропорционально, чтобы попасть в target точно.
    ratio = target / total if total else 1.0
    for c in clips:
        c.duration *= ratio
    return clips
