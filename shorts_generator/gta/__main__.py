"""Gated workflow:
  gta source add game.mp4 --kind own_capture
  gta run game.mp4 --out clips          # detect + render, everything starts 'pending'
  gta approve clips 1 3                 # you watched them; mark the keepers
  gta publish clips --to youtube        # dry run; add --yes to upload (private by default)
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .captions import transcribe_words, words_to_ass
from .highlights import find_highlights
from .ledger import add_source, load_manifest, require_source, set_status, write_manifest
from .publish import publish
from .render import render_clip

LEDGER = "sources.jsonl"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="gta")
    ap.add_argument("--ledger", default=LEDGER)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("source")
    s.add_argument("action", choices=["add"])
    s.add_argument("video")
    s.add_argument("--kind", required=True, choices=["own_capture", "written_permission"])
    s.add_argument("--note", default="")

    d = sub.add_parser("detect")
    d.add_argument("video")
    d.add_argument("--n", type=int, default=5)
    d.add_argument("--length", type=float, default=30.0)

    r = sub.add_parser("run")
    r.add_argument("video")
    r.add_argument("--n", type=int, default=5)
    r.add_argument("--length", type=float, default=30.0)
    r.add_argument("--out", default="clips")
    r.add_argument("--layout", choices=["fit", "crop"], default="fit")
    r.add_argument("--captions", action="store_true", help="burn word captions (faster-whisper)")
    r.add_argument("--words", help="words JSON to caption from, instead of transcribing")

    a_ = sub.add_parser("approve")
    a_.add_argument("out")
    a_.add_argument("numbers", type=int, nargs="+")
    a_.add_argument("--reject", action="store_true")

    p = sub.add_parser("publish")
    p.add_argument("out")
    p.add_argument("--to", required=True, choices=["youtube", "tiktok", "instagram"])
    p.add_argument("--title", default="GTA 6 clip")
    p.add_argument("--privacy", default="private", choices=["private", "unlisted", "public"])
    p.add_argument("--yes", action="store_true", help="actually upload (default is dry run)")
    p.add_argument("--cap", type=int, default=3, help="max uploads per platform per 24h")

    a = ap.parse_args(argv)

    if a.cmd == "source":
        print(json.dumps(add_source(a.ledger, a.video, a.kind, a.note)))
        return 0
    if a.cmd == "detect":
        print(json.dumps([w.__dict__ for w in find_highlights(a.video, a.n, a.length)], indent=2))
        return 0
    if a.cmd == "approve":
        set_status(a.out, a.numbers, "rejected" if a.reject else "approved")
        return 0
    if a.cmd == "run":
        require_source(a.ledger, a.video)  # no footage of unknown origin gets processed
        wins = find_highlights(a.video, a.n, a.length)
        words = json.loads(Path(a.words).read_text()) if a.words else (
            transcribe_words(a.video) if a.captions else None)
        Path(a.out).mkdir(parents=True, exist_ok=True)
        clips = []
        for i, w in enumerate(wins, 1):
            ass = None
            if words:
                ass = f"{a.out}/clip{i}.ass"
                Path(ass).write_text(words_to_ass(words, offset=w.start))
            out = render_clip(a.video, w.start, w.end, f"{a.out}/clip{i}.mp4", a.layout, ass)
            clips.append({"n": i, "file": out, "start": w.start, "end": w.end, "score": w.score})
            print(f"{out}  [{w.start:.0f}s-{w.end:.0f}s score {w.score}]  pending approval")
        write_manifest(a.out, a.video, clips)
        return 0
    if a.cmd == "publish":
        m = load_manifest(a.out)
        require_source(a.ledger, m["source"])
        done = 0
        for c in m["clips"]:
            if c["status"] != "approved":
                continue
            rec = publish(c["file"], f"{a.title} #{c['n']}", "", ["GTA6", "GTAVI"], a.to,
                          a.privacy, dry_run=not a.yes, log=f"{a.out}/posted.jsonl", daily_cap=a.cap)
            print(f"clip{c['n']} ->", "DRY RUN" if rec["dry_run"] else rec.get("video_id"))
            done += 1
        if not done:
            print("nothing approved yet: run `gta approve <out> <numbers>` after watching the clips")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
