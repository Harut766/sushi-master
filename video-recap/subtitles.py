"""Субтитры в стиле Shorts/TikTok: крупно, по 3–4 слова, по центру снизу."""

SIZES = {
    # PlayResX, PlayResY, размер шрифта, отступ снизу
    "vertical": (1080, 1920, 82, 560),
    "horizontal": (1920, 1080, 64, 90),
}


def _timestamp(seconds):
    cs = int(round(seconds * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _chunks(sentence, max_words):
    words = sentence.split()
    return [" ".join(words[i:i + max_words]) for i in range(0, len(words), max_words)]


def build_ass(lines, path, fmt="vertical", max_words=4, upper=False, font="Arial", center=False):
    width, height, size, margin = SIZES[fmt]
    # center — крупные слова посередине экрана, как в Reddit-историях.
    alignment = 5 if center else 2
    if center:
        size = int(size * 1.3)
    events = []
    for line in lines:
        chunks = _chunks(line.text, max_words)
        total_chars = sum(len(c) for c in chunks)
        t = line.start
        for chunk in chunks:
            # Время на кусок — пропорционально числу букв в нём.
            end = t + (line.end - line.start) * len(chunk) / total_chars
            text = chunk.upper() if upper else chunk
            text = text.replace("{", "(").replace("}", ")")
            events.append(f"Dialogue: 0,{_timestamp(t)},{_timestamp(end)},Default,,0,0,0,,{text}")
            t = end

    path.write_text(
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {width}\nPlayResY: {height}\n"
        "WrapStyle: 0\nScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,{font},{size},&H00FFFFFF,&H000000FF,&H00000000,&H64000000,"
        f"-1,0,0,0,100,100,0,0,1,5,2,{alignment},60,60,{margin},1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        + "\n".join(events) + "\n",
        encoding="utf-8",
    )
