"""Find highlight windows in gameplay by loudness spikes and scene-cut density.

Gameplay has little speech, so transcript ranking fails; explosions, gunfire and
fast camera changes show up as audio-energy jumps and visual cuts instead.
"""
from __future__ import annotations

import re
import statistics
import subprocess
from dataclasses import dataclass

_PTS = re.compile(r"pts_time:([0-9.]+)")
_RMS = re.compile(r"lavfi\.astats\.Overall\.RMS_level=(-?[0-9.]+|-inf)")
_SCENE = re.compile(r"lavfi\.scene_score=([0-9.]+)")


@dataclass
class Window:
    start: float
    end: float
    score: float


def probe_duration(path: str) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", path],
        capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def _run(cmd: list[str]) -> str:
    p = subprocess.run(cmd, capture_output=True, text=True)
    # ametadata/metadata print to stdout via file=-, ffmpeg noise goes to stderr
    return p.stdout


def loudness_per_second(path: str) -> dict[int, float]:
    """Mean RMS level (dB) per whole second. Silence is floored at -90 dB."""
    out = _run(["ffmpeg", "-v", "error", "-i", path, "-vn", "-af",
                "aresample=48000,asetnsamples=n=24000,astats=metadata=1:reset=1,"
                "ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-",
                "-f", "null", "-"])
    buckets: dict[int, list[float]] = {}
    t = None
    for line in out.splitlines():
        m = _PTS.search(line)
        if m:
            t = float(m.group(1))
            continue
        m = _RMS.search(line)
        if m and t is not None:
            v = -90.0 if m.group(1) == "-inf" else max(float(m.group(1)), -90.0)
            buckets.setdefault(int(t), []).append(v)
    return {s: sum(v) / len(v) for s, v in buckets.items()}


def scene_cuts(path: str, threshold: float = 0.3) -> list[float]:
    out = _run(["ffmpeg", "-v", "error", "-i", path, "-an", "-vf",
                f"scale=320:-2,select='gt(scene,{threshold})',metadata=print:file=-",
                "-f", "null", "-"])
    cuts, t = [], None
    for line in out.splitlines():
        m = _PTS.search(line)
        if m:
            t = float(m.group(1))
        elif _SCENE.search(line) and t is not None:
            cuts.append(t)
    return cuts


def second_scores(path: str, duration: float, cut_weight: float = 1.0) -> list[float]:
    loud = loudness_per_second(path)
    n = int(duration) + 1
    levels = [loud.get(i, -90.0) for i in range(n)]
    base = statistics.median(levels)
    # How far above the video's own typical level each second is (never negative).
    scores = [max(0.0, (lv - base)) / 6.0 for lv in levels]
    for c in scene_cuts(path):
        i = min(int(c), n - 1)
        scores[i] += cut_weight
    return scores


def pick_windows(scores: list[float], duration: float, n: int = 5,
                 length: float = 30.0, min_gap: float = 10.0) -> list[Window]:
    """Greedy top-n non-overlapping windows; each window is centred on its peak
    with a lead-in so the action is not cut at the first frame."""
    length = min(length, duration)
    span = int(length)
    prefix = [0.0]
    for s in scores:
        prefix.append(prefix[-1] + s)
    cands = []
    last_start = max(0, int(duration - length))
    for st in range(0, last_start + 1):
        en = min(st + span, len(scores))
        cands.append((prefix[en] - prefix[st], st))
    cands.sort(reverse=True)
    chosen: list[Window] = []
    for score, st in cands:
        if score <= 0 or len(chosen) >= n:
            break
        if all(st >= w.end + min_gap or st + length <= w.start - min_gap for w in chosen):
            chosen.append(Window(float(st), float(st) + length, round(score, 2)))
    return sorted(chosen, key=lambda w: w.start)


def find_highlights(path: str, n: int = 5, length: float = 30.0) -> list[Window]:
    d = probe_duration(path)
    return pick_windows(second_scores(path, d), d, n=n, length=length)
