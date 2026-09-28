"""Субтитры в стиле Shorts/TikTok: крупно, по несколько слов, с обводкой.

Субтитры рисуются картинками через Pillow и накладываются одним потоком
(ffconcat-список PNG). Так они работают с любой сборкой ffmpeg — не нужен
libass, которого нет, например, в ffmpeg из Homebrew.
"""

from PIL import Image, ImageDraw

from utils import load_font, wrap_text

SIZES = {
    # ширина, высота, размер шрифта, отступ снизу
    "vertical": (1080, 1920, 82, 560),
    "horizontal": (1920, 1080, 64, 90),
}


def _chunks(sentence, max_words):
    words = sentence.split()
    return [" ".join(words[i:i + max_words]) for i in range(0, len(words), max_words)]


def _events(lines, max_words, upper):
    for line in lines:
        chunks = _chunks(line.text, max_words)
        total_chars = sum(len(c) for c in chunks)
        t = line.start
        for chunk in chunks:
            # Время на кусок — пропорционально числу букв в нём.
            end = t + (line.end - line.start) * len(chunk) / total_chars
            yield t, end, chunk.upper() if upper else chunk
            t = end


def _render(text, path, width, height, font, center, margin):
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    if text:
        d = ImageDraw.Draw(img)
        rows = wrap_text(d, text, font, width - 120)
        line_h = int(font.size * 1.2)
        block = line_h * len(rows)
        top = (height - block) / 2 if center else height - margin - block
        for i, row in enumerate(rows):
            d.text((width / 2, top + i * line_h), row, font=font, fill="white", anchor="ma",
                   stroke_width=max(4, font.size // 14), stroke_fill="black")
    img.save(path)


def build_overlay(lines, workdir, fmt="vertical", max_words=4, upper=False, center=False,
                  font_path=None, name="subs"):
    """Рисует субтитры и возвращает ffconcat-список, который ffmpeg читает как
    видеопоток с прозрачностью. center — крупно посередине, как в Reddit-историях."""
    width, height, size, margin = SIZES[fmt]
    if center:
        size = int(size * 1.3)
    font = load_font(size, font_path)

    blank = workdir / f"{name}_blank.png"
    _render("", blank, width, height, font, center, margin)
    entries, t = [], 0.0
    for i, (start, end, text) in enumerate(_events(lines, max_words, upper)):
        if start > t:
            entries.append((blank, start - t))
        png = workdir / f"{name}_{i:04d}.png"
        _render(text, png, width, height, font, center, margin)
        entries.append((png, end - start))
        t = end
    entries.append((blank, 3600.0))  # хвост; видео обрезается по основному потоку

    listing = workdir / f"{name}.txt"
    listing.write_text(
        "ffconcat version 1.0\n"
        + "".join(f"file '{p.name}'\nduration {d:.3f}\n" for p, d in entries)
        # ffmpeg игнорирует длительность последнего файла — повторяем его.
        + f"file '{blank.name}'\n",
        encoding="utf-8",
    )
    return listing
