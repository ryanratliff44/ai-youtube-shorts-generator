"""Cut a window, lay it out as 1080x1920, optionally burn captions, encode crisp."""
from __future__ import annotations

import subprocess
from pathlib import Path

W, H = 1080, 1920


def build_filter(layout: str, ass: str | None) -> str:
    if layout == "crop":  # centre crop of the action, fills the frame
        v = f"crop=ih*9/16:ih,scale={W}:{H}:flags=lanczos"
    else:  # "fit": full frame over a blurred copy of itself, nothing is lost
        v = (f"split=2[bg][fg];[bg]scale={W}:{H}:force_original_aspect_ratio=increase,"
             f"crop={W}:{H},boxblur=30:5[b];[fg]scale={W}:-2:flags=lanczos[f];"
             f"[b][f]overlay=(W-w)/2:(H-h)/2")
    if ass:
        esc = ass.replace("\\", "/").replace(":", "\\:").replace("'", r"\'")
        v += f",subtitles='{esc}'"
    return v + ",format=yuv420p"


def render_clip(src: str, start: float, end: float, out: str, layout: str = "fit",
                ass: str | None = None, crf: int = 17, fps: int | None = None) -> str:
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-v", "error", "-ss", f"{start:.3f}", "-t", f"{end - start:.3f}",
           "-i", src, "-vf", build_filter(layout, ass),
           "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
           "-c:v", "libx264", "-preset", "slow", "-crf", str(crf),
           "-profile:v", "high", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
           "-movflags", "+faststart"]
    if fps:
        cmd += ["-r", str(fps)]
    subprocess.run(cmd + [out], check=True)
    return out
