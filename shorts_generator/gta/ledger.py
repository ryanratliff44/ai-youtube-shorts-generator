"""Source-permission ledger and approval manifest.

Nothing is published unless (1) its source video is in the ledger as the user's own
capture or covered by written permission, and (2) a human approved that clip.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

KINDS = ("own_capture", "written_permission")


def _key(path: str) -> str:
    return str(Path(path).resolve())


def add_source(ledger: str, video: str, kind: str, note: str = "") -> dict:
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}")
    if kind == "written_permission" and not note.strip():
        raise ValueError("written_permission needs a note: who granted it and where it is stored")
    rec = {"video": _key(video), "kind": kind, "note": note, "added": int(time.time())}
    with open(ledger, "a") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


def source_for(ledger: str, video: str) -> dict | None:
    p = Path(ledger)
    if not p.is_file():
        return None
    found = None
    for line in p.read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            if r["video"] == _key(video):
                found = r
    return found


def require_source(ledger: str, video: str) -> dict:
    rec = source_for(ledger, video)
    if not rec:
        raise PermissionError(
            f"{video} is not in the source ledger. Register it first: "
            "`gta source add <video> --kind own_capture` (or written_permission --note ...)")
    return rec


# ---- approval manifest (one per output folder) ----

def write_manifest(out_dir: str, video: str, clips: list[dict]) -> str:
    m = {"source": _key(video),
         "clips": [{**c, "status": "pending"} for c in clips]}
    path = Path(out_dir) / "manifest.json"
    path.write_text(json.dumps(m, indent=2))
    return str(path)


def load_manifest(out_dir: str) -> dict:
    return json.loads((Path(out_dir) / "manifest.json").read_text())


def set_status(out_dir: str, numbers: list[int], status: str) -> dict:
    m = load_manifest(out_dir)
    for c in m["clips"]:
        if c["n"] in numbers:
            c["status"] = status
    (Path(out_dir) / "manifest.json").write_text(json.dumps(m, indent=2))
    return m
