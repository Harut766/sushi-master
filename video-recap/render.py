"""Нарезка клипов, склейка и финальный рендер через ffmpeg."""

from utils import run

FPS = 30


def _video_filter(fmt, fit):
    if fmt == "horizontal":
        return ("scale=1920:1080:force_original_aspect_ratio=decrease,"
                "pad=1920:1080:(ow-iw)/2:(oh-ih)/2")
    if fit == "crop":
        return "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
    # Картинка целиком по центру, сверху и снизу — размытая копия кадра.
    return ("split[a][b];"
            "[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:5[bg];"
            "[b]scale=1080:-2[fg];"
            "[bg][fg]overlay=(W-w)/2:(H-h)/2")


def render_clips(video, clips, workdir, fmt="vertical", fit="blur", with_audio=True):
    vf = f"[0:v]{_video_filter(fmt, fit)},fps={FPS},setsar=1,format=yuv420p[v]"
    paths = []
    for i, clip in enumerate(clips, 1):
        print(f"  клип {i}/{len(clips)}: {clip.start:.1f}s, {clip.duration:.1f}s")
        out = workdir / f"clip_{i:03d}.mp4"
        cmd = ["ffmpeg", "-y", "-v", "error", "-ss", f"{clip.start:.3f}", "-i", video]
        if with_audio:
            audio_map = "0:a:0"
        else:
            cmd += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
            audio_map = "1:a"
        cmd += [
            "-t", f"{clip.duration:.3f}", "-filter_complex", vf,
            "-map", "[v]", "-map", audio_map, "-ar", "48000", "-ac", "2",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "17",
            "-c:a", "aac", "-b:a", "192k", out,
        ]
        run(cmd)
        paths.append(out)
    return paths


def concat(paths, workdir):
    listing = workdir / "clips.txt"
    listing.write_text("".join(f"file '{p.name}'\n" for p in paths), encoding="utf-8")
    out = workdir / "joined.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
         "-i", listing.name, "-c", "copy", out.name], cwd=workdir)
    return out


def final_mix(joined, out, workdir, narration=None, music=None, subs=None,
              original_volume=0.15, music_volume=0.12):
    """Смешивает звук фильма, озвучку и музыку и вжигает субтитры."""
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", joined.name]
    audio = [f"[0:a]volume={original_volume}[a0]"]
    labels = ["[a0]"]
    idx = 1
    if narration:
        cmd += ["-i", narration.name]
        audio.append(f"[{idx}:a]volume=1.0[a{idx}]")
        labels.append(f"[a{idx}]")
        idx += 1
    if music:
        cmd += ["-stream_loop", "-1", "-i", music]
        audio.append(f"[{idx}:a]volume={music_volume}[a{idx}]")
        labels.append(f"[a{idx}]")
        idx += 1
    audio.append(f"{''.join(labels)}amix=inputs={len(labels)}:duration=first:normalize=0,"
                 "alimiter=limit=0.95[aout]")
    # Путь к субтитрам — относительный (ffmpeg запускается из workdir),
    # так не нужно экранировать двоеточия в путях Windows.
    video = f"[0:v]subtitles={subs.name}[vout]" if subs else "[0:v]null[vout]"

    cmd += [
        "-filter_complex", ";".join(audio + [video]),
        "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out.resolve(),
    ]
    run(cmd, cwd=workdir)
