"""Карточка поста в стиле Reddit (PNG с прозрачным фоном) для начала ролика."""

from PIL import Image, ImageDraw

from utils import load_font, wrap_text


def make_card(title, out, subreddit="r/AskReddit", username="u/anonymous",
              upvotes="24.1k", comments="1.3k", width=960, font_path=None):
    pad, radius, avatar = 48, 36, 84
    title_font = load_font(56, font_path)
    name_font = load_font(38, font_path)
    meta_font = load_font(32, font_path)

    measure = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    title_lines = wrap_text(measure, title, title_font, width - 2 * pad)
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
