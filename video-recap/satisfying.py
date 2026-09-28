"""Генератор «сатисфаинг»-анимаций для фона (9:16, без звука).

Видео рисует код, поэтому оно полностью ваше: ни у кого нет на него прав,
и каждый запуск (другой --seed) даёт новую картинку.

Режимы:
  bounce — шарик прыгает внутри круга и растёт с каждым ударом;
  orbits — точки на кольцах с разной скоростью, периодически выстраиваются в линию;
  spiro  — спирограф: узор рисуется линией, цвет плавно переливается.

Пример:
    python satisfying.py --mode bounce --duration 180 --out backgrounds/bounce1.mp4
    python satisfying.py --count 5 --out backgrounds/bg.mp4   # 5 разных фонов
"""

import argparse
import colorsys
import math
import random
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils import require_ffmpeg  # noqa: E402

# Рисуем в 720x1280 и масштабируем до 1080x1920 — так быстрее и края мягче.
W, H = 720, 1280
FPS = 30


def color(hue, light=0.6):
    r, g, b = colorsys.hls_to_rgb(hue % 1.0, light, 0.9)
    return int(r * 255), int(g * 255), int(b * 255)


def fade(img, amount):
    """Затемняет прошлый кадр — остаются красивые шлейфы."""
    return Image.blend(img, Image.new("RGB", img.size, (8, 8, 14)), amount)


class Bounce:
    def __init__(self, rng):
        self.rng = rng
        self.center = (W / 2, H / 2)
        self.ring = W * 0.44
        self.hue = rng.random()
        self.reset()

    def reset(self):
        self.r = 14.0
        self.x, self.y = self.center[0] + self.rng.uniform(-60, 60), self.center[1] - 150
        angle = self.rng.uniform(0, 2 * math.pi)
        self.vx, self.vy = 420 * math.cos(angle), 420 * math.sin(angle)

    def frame(self, img, t):
        img = fade(img, 0.12)
        dt = 1 / FPS / 4
        cx, cy = self.center
        for _ in range(4):
            self.vy += 900 * dt
            self.x += self.vx * dt
            self.y += self.vy * dt
            dx, dy = self.x - cx, self.y - cy
            dist = math.hypot(dx, dy)
            if dist + self.r >= self.ring:
                nx, ny = dx / dist, dy / dist
                dot = self.vx * nx + self.vy * ny
                self.vx -= 2 * dot * nx
                self.vy -= 2 * dot * ny
                self.x = cx + nx * (self.ring - self.r - 1)
                self.y = cy + ny * (self.ring - self.r - 1)
                self.r *= 1.05
                self.hue += 0.07
                if self.r > self.ring * 0.8:
                    self.reset()
        d = ImageDraw.Draw(img)
        d.ellipse((cx - self.ring, cy - self.ring, cx + self.ring, cy + self.ring),
                  outline=color(self.hue, 0.75), width=6)
        d.ellipse((self.x - self.r, self.y - self.r, self.x + self.r, self.y + self.r),
                  fill=color(self.hue), outline=(255, 255, 255), width=3)
        return img


class Orbits:
    def __init__(self, rng):
        self.count = rng.randint(12, 20)
        self.cycle = rng.uniform(40, 70)  # через столько секунд все точки выстраиваются
        self.base = rng.randint(20, 30)
        self.hue = rng.random()

    def frame(self, img, t):
        img = fade(img, 0.08)
        d = ImageDraw.Draw(img)
        cx, cy = W / 2, H / 2
        for i in range(self.count):
            radius = 40 + i * (W * 0.45 - 40) / (self.count - 1)
            angle = 2 * math.pi * (self.base + i) * t / self.cycle - math.pi / 2
            x, y = cx + radius * math.cos(angle), cy + radius * math.sin(angle)
            d.ellipse((cx - radius, cy - radius, cx + radius, cy + radius),
                      outline=(40, 40, 55), width=1)
            c = color(self.hue + i / self.count)
            d.ellipse((x - 11, y - 11, x + 11, y + 11), fill=c)
        return img


class Spiro:
    def __init__(self, rng):
        self.rng = rng
        self.hue = rng.random()
        self.new_pattern()

    def new_pattern(self):
        self.R = 1.0
        self.r = self.rng.choice([0.3, 0.35, 0.4, 0.45, 0.55, 0.6, 0.65, 0.7]) + \
            self.rng.uniform(-0.01, 0.01)
        self.d = self.rng.uniform(0.4, 0.9)
        self.theta = 0.0
        self.prev = None
        self.frames_left = FPS * 30  # один узор рисуется ~30 секунд

    def point(self, theta):
        R, r, d = self.R, self.r, self.d
        k = (R - r) / r
        scale = W * 0.42 / (R - r + d)
        x = (R - r) * math.cos(theta) + d * math.cos(k * theta)
        y = (R - r) * math.sin(theta) - d * math.sin(k * theta)
        return W / 2 + x * scale, H / 2 + y * scale

    def frame(self, img, t):
        self.frames_left -= 1
        if self.frames_left <= 0:
            img = fade(img, 0.5)
            self.new_pattern()
            self.hue += 0.3
        d = ImageDraw.Draw(img)
        for _ in range(12):
            self.theta += 0.02
            p = self.point(self.theta)
            if self.prev:
                d.line((self.prev, p), fill=color(self.hue + self.theta / 60), width=3)
            self.prev = p
        return img


MODES = {"bounce": Bounce, "orbits": Orbits, "spiro": Spiro}


def generate(out, mode, duration, seed):
    rng = random.Random(seed)
    scene = MODES[mode](rng)
    ffmpeg = subprocess.Popen([
        "ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-vf", "scale=1080:1920:flags=lanczos,format=yuv420p",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", str(out),
    ], stdin=subprocess.PIPE)
    img = Image.new("RGB", (W, H), (8, 8, 14))
    total = int(duration * FPS)
    for i in range(total):
        img = scene.frame(img, i / FPS)
        ffmpeg.stdin.write(img.tobytes())
        if i % (FPS * 10) == 0:
            print(f"\r  {out.name}: {i * 100 // total}%", end="", flush=True)
    ffmpeg.stdin.close()
    if ffmpeg.wait() != 0:
        raise RuntimeError("ffmpeg не смог записать видео")
    print(f"\r  {out.name}: готово")


def main():
    p = argparse.ArgumentParser(description="Генератор сатисфаинг-фонов")
    p.add_argument("--mode", choices=list(MODES) + ["random"], default="random")
    p.add_argument("--duration", type=float, default=180, help="длина, секунд")
    p.add_argument("--count", type=int, default=1, help="сколько разных видео сделать")
    p.add_argument("--seed", type=int, help="одинаковый seed = одинаковое видео")
    p.add_argument("--out", type=Path, default=Path("background.mp4"))
    args = p.parse_args()
    require_ffmpeg()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    seed = args.seed if args.seed is not None else random.randrange(1_000_000)
    for n in range(args.count):
        mode = args.mode if args.mode != "random" else random.Random(seed + n).choice(list(MODES))
        out = args.out if args.count == 1 else \
            args.out.with_name(f"{args.out.stem}_{n + 1}_{mode}{args.out.suffix}")
        generate(out, mode, args.duration, seed + n)


if __name__ == "__main__":
    main()
