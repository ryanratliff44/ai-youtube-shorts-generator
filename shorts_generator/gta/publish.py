"""Publish via OFFICIAL APIs only. Credentials come from files outside the repo.

YouTube: set GTA_YT_CLIENT_JSON and GTA_YT_TOKEN_JSON to the OAuth client and
refresh-token files for the GTA channel. Nothing here prints or logs secrets.
Default is a dry run; real uploads default to private so you can review first.
"""
from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path


def _read_json(env: str) -> dict:
    p = os.environ.get(env)
    if not p or not Path(p).is_file():
        raise RuntimeError(f"{env} must point to a credentials file (kept outside the repo)")
    return json.loads(Path(p).read_text())


def youtube_access_token() -> str:
    c = _read_json("GTA_YT_CLIENT_JSON")
    c = c.get("installed") or c.get("web") or c
    t = _read_json("GTA_YT_TOKEN_JSON")
    body = urllib.parse.urlencode({
        "client_id": c["client_id"], "client_secret": c["client_secret"],
        "refresh_token": t["refresh_token"], "grant_type": "refresh_token"}).encode()
    with urllib.request.urlopen(urllib.request.Request(
            "https://oauth2.googleapis.com/token", body)) as r:
        return json.load(r)["access_token"]


def youtube_upload(path: str, title: str, description: str, tags: list[str],
                   privacy: str = "private") -> str:
    token = youtube_access_token()
    meta = {"snippet": {"title": title[:100], "description": description + "\n#Shorts",
                        "tags": tags[:15], "categoryId": "20"},
            "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False}}
    size = os.path.getsize(path)
    init = urllib.request.Request(
        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
        json.dumps(meta).encode(), method="POST",
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json; charset=UTF-8",
                 "X-Upload-Content-Type": "video/mp4",
                 "X-Upload-Content-Length": str(size)})
    with urllib.request.urlopen(init) as r:
        url = r.headers["Location"]
    with open(path, "rb") as f:
        put = urllib.request.Request(url, f.read(), method="PUT",
                                     headers={"Content-Type": "video/mp4"})
    with urllib.request.urlopen(put) as r:
        return json.load(r)["id"]


def posts_last_24h(log: str, target: str) -> int:
    p = Path(log)
    if not p.is_file():
        return 0
    cutoff = time.time() - 86400
    n = 0
    for line in p.read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            if r.get("target") == target and not r.get("dry_run") and r["ts"] >= cutoff:
                n += 1
    return n


def publish(path: str, title: str, description: str, tags: list[str],
            target: str = "youtube", privacy: str = "private", dry_run: bool = True,
            log: str = "posted.jsonl", daily_cap: int = 3) -> dict:
    """Quota governor: refuses real uploads past `daily_cap` per platform per 24h."""
    if not dry_run and posts_last_24h(log, target) >= daily_cap:
        raise RuntimeError(f"daily cap of {daily_cap} {target} uploads reached")
    rec = {"file": path, "title": title, "target": target, "privacy": privacy,
           "dry_run": dry_run, "ts": int(time.time())}
    if not dry_run:
        if target != "youtube":
            raise NotImplementedError(
                f"{target}: needs your approved TikTok app / Meta Graph token first")
        rec["video_id"] = youtube_upload(path, title, description, tags, privacy)
    with open(log, "a") as f:
        f.write(json.dumps(rec) + "\n")
    return rec
