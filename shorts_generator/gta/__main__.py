"""python -m shorts_generator.gta run gameplay.mp4 --n 5 --out clips/"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .captions import transcribe_words, words_to_ass
from .highlights import find_highlights
from .publish import publish
from .render import render_clip


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="gta")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("detect", "run"):
        p = sub.add_parser(name)
        p.add_argument("video")
        p.add_argument("--n", type=int, default=5)
        p.add_argument("--length", type=float, default=30.0)
    r = sub.choices["run"]
    r.add_argument("--out", default="clips")
    r.add_argument("--layout", choices=["fit", "crop"], default="fit")
    r.add_argument("--captions", action="store_true", help="burn word captions (faster-whisper)")
    r.add_argument("--words", help="words JSON to caption from, instead of transcribing")
    r.add_argument("--title", default="GTA 6 clip")
    r.add_argument("--publish", choices=["youtube", "tiktok", "instagram"])
    r.add_argument("--privacy", default="private", choices=["private", "unlisted", "public"])
    r.add_argument("--yes", action="store_true", help="actually upload (default is dry run)")
    a = ap.parse_args(argv)

    wins = find_highlights(a.video, a.n, a.length)
    if a.cmd == "detect":
        print(json.dumps([w.__dict__ for w in wins], indent=2))
        return 0
    words = json.loads(Path(a.words).read_text()) if a.words else (
        transcribe_words(a.video) if a.captions else None)
    for i, w in enumerate(wins, 1):
        ass = None
        if words:
            ass = f"{a.out}/clip{i}.ass"
            Path(a.out).mkdir(parents=True, exist_ok=True)
            Path(ass).write_text(words_to_ass(words, offset=w.start))
        out = render_clip(a.video, w.start, w.end, f"{a.out}/clip{i}.mp4", a.layout, ass)
        print(f"{out}  [{w.start:.0f}s-{w.end:.0f}s score {w.score}]")
        if a.publish:
            rec = publish(out, f"{a.title} #{i}", "", ["GTA6", "GTAVI"], a.publish,
                          a.privacy, dry_run=not a.yes, log=f"{a.out}/posted.jsonl")
            print("  ->", "DRY RUN" if rec["dry_run"] else rec.get("video_id"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
