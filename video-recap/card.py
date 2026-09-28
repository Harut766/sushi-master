"""Карточка поста в стиле Reddit (PNG с прозрачным фоном) для начала ролика."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT_CANDIDATES = [
    "C:/Windows/Fonts/arialbd.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]


def _font(size, path=None):
    for candidate in [path] + FONT_CANDIDATES:
        if candidate and Path(candidate).exists():
            return ImageFont.truetype(str(candidate), size)
    raise SystemExit("Не найден шрифт с кириллицей. Укажите путь к .ttf через --font.")


def _wrap(draw, text, font, width):
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


def make_card(title, out, subreddit="r/AskReddit", username="u/anonymous",
              upvotes="24.1k", comments="1.3k", width=960, font_path=None):
    pad, radius, avatar = 48, 36, 84
    title_font = _font(56, font_path)
    name_font = _font(38, font_path)
    meta_font = _font(32, font_path)

    measure = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    title_lines = _wrap(measure, title, title_font, width - 2 * pad)
    line_h = 70
    height = pad + avatar + 32 + line_h * len(title_lines) + 28 + 40 + pad

    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, width - 1, height - 1), radius, fill=(255, 255, 255, 255))

    # Шапка: кружок-аватар, сабреддит, автор.
    d.ellipse((pad, pad, pad + avatar, pad + avatar), fill=(255, 69, 0, 255))
    d.text((pad + avatar / 2, pad + avatar / 2), subreddit[2:3].upper() or "R",
           font=name_font, fill="white", anchor="mm")
    d.text((pad + avatar + 24, pad + 4), subreddit, font=name_font, fill=(26, 26, 27))
    d.text((pad + avatar + 24, pad + 50), username, font=meta_font, fill=(120, 124, 126))

    y = pad + avatar + 32
    for line in title_lines:
        d.text((pad, y), line, font=title_font, fill=(26, 26, 27))
        y += line_h

    y += 28
    d.text((pad, y), f"▲ {upvotes}     ● {comments}", font=meta_font, fill=(120, 124, 126))
    img.save(out)
    return out
