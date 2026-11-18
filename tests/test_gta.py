import json
import subprocess

import pytest

from shorts_generator.gta.captions import words_to_ass
from shorts_generator.gta.highlights import find_highlights, pick_windows
from shorts_generator.gta.ledger import add_source, require_source
from shorts_generator.gta.publish import publish
from shorts_generator.gta.__main__ import main as cli
from shorts_generator.gta.render import render_clip


@pytest.fixture(scope="module")
def video(tmp_path_factory):
    """60s 1280x720: quiet, with a loud burst and fast cuts at 40-44s."""
    p = str(tmp_path_factory.mktemp("v") / "g.mp4")
    segs = [("blue", 40), ("red", 1), ("green", 1), ("yellow", 1), ("white", 1), ("black", 16)]
    ins, flt = [], ""
    for i, (c, d) in enumerate(segs):
        ins += ["-f", "lavfi", "-i", f"color=c={c}:s=1280x720:d={d}:r=30"]
        flt += f"[{i}:v]"
    flt += f"concat=n={len(segs)}:v=1:a=0[v]"
    subprocess.run(["ffmpeg", "-y", "-v", "error", *ins, "-f", "lavfi", "-i",
                    "aevalsrc='if(between(t,40,44),0.9,0.004)*sin(2*PI*440*t)':d=60:s=48000",
                    "-filter_complex", flt, "-map", "[v]", "-map", f"{len(segs)}:a",
                    "-c:v", "libx264", "-c:a", "aac", "-shortest", p], check=True)
    return p


def test_detects_the_loud_cut_heavy_window(video):
    wins = find_highlights(video, n=1, length=20)
    assert wins and wins[0].start <= 42 <= wins[0].end


def test_pick_windows_do_not_overlap():
    scores = [0.0] * 200
    scores[20] = scores[25] = scores[150] = 5.0
    wins = pick_windows(scores, 200, n=3, length=30, min_gap=10)
    for a, b in zip(wins, wins[1:]):
        assert b.start >= a.end + 10


@pytest.mark.parametrize("layout", ["fit", "crop"])
def test_render_is_1080x1920(video, tmp_path, layout):
    out = render_clip(video, 38, 46, str(tmp_path / "o.mp4"), layout)
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                        "-show_entries", "stream=width,height", "-of", "csv=p=0", out],
                       capture_output=True, text=True, check=True).stdout.strip()
    assert r == "1080,1920"


def test_render_with_captions(video, tmp_path):
    words = [{"word": "boom", "start": 1.0, "end": 1.4}, {"word": "wow", "start": 1.4, "end": 1.9}]
    ass = tmp_path / "c.ass"
    ass.write_text(words_to_ass(words))
    assert "BOOM" in ass.read_text()
    render_clip(video, 38, 46, str(tmp_path / "c.mp4"), "fit", str(ass))


def test_publish_dry_run_logs_and_never_calls_network(tmp_path):
    log = str(tmp_path / "p.jsonl")
    rec = publish("x.mp4", "t", "d", ["a"], "youtube", dry_run=True, log=log)
    assert rec["dry_run"] and "video_id" not in rec
    assert json.loads(open(log).read())["target"] == "youtube"


def test_unapproved_platforms_refuse_real_upload(tmp_path):
    with pytest.raises(NotImplementedError):
        publish("x.mp4", "t", "d", [], "tiktok", dry_run=False, log=str(tmp_path / "p.jsonl"))


def test_ledger_blocks_unregistered_and_requires_note(tmp_path, video):
    led = str(tmp_path / "s.jsonl")
    with pytest.raises(PermissionError):
        require_source(led, video)
    with pytest.raises(ValueError):
        add_source(led, video, "written_permission")  # no note
    add_source(led, video, "own_capture")
    assert require_source(led, video)["kind"] == "own_capture"


def test_daily_cap_blocks_extra_uploads(tmp_path):
    log = tmp_path / "p.jsonl"
    import time
    log.write_text("".join(json.dumps({"target": "youtube", "dry_run": False,
                                       "ts": int(time.time())}) + "\n" for _ in range(2)))
    with pytest.raises(RuntimeError):
        publish("x.mp4", "t", "d", [], "youtube", dry_run=False, log=str(log), daily_cap=2)


def test_full_gate_flow(video, tmp_path):
    led, out = str(tmp_path / "s.jsonl"), str(tmp_path / "clips")
    # unregistered footage is refused
    with pytest.raises(PermissionError):
        cli(["--ledger", led, "run", video, "--n", "1", "--length", "20", "--out", out])
    cli(["--ledger", led, "source", "add", video, "--kind", "own_capture"])
    cli(["--ledger", led, "run", video, "--n", "1", "--length", "20", "--out", out])
    # nothing approved -> nothing publishes
    cli(["--ledger", led, "publish", out, "--to", "youtube"])
    assert not (tmp_path / "clips" / "posted.jsonl").exists()
    cli(["--ledger", led, "approve", out, "1"])
    cli(["--ledger", led, "publish", out, "--to", "youtube"])
    rec = json.loads((tmp_path / "clips" / "posted.jsonl").read_text())
    assert rec["dry_run"] and rec["privacy"] == "private"
