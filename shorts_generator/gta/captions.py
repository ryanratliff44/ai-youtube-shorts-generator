"""Word-level captions rendered to an ASS file (burned in by ffmpeg).

Captions sit above the bottom UI zone of TikTok/Reels/Shorts; the active word is
highlighted. Transcription needs faster-whisper (optional); without it, pass in
your own words JSON: [{"word": "hi", "start": 0.1, "end": 0.4}, ...]
"""
from __future__ import annotations

HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Default,Arial,92,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,6,2,2,80,80,520,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
ACTIVE = "&H0000D7FF&"  # amber (BGR)


def _ts(t: float) -> str:
    cs = int(round(t * 100))
    h, rem = divmod(cs, 360000)
    m, rem = divmod(rem, 6000)
    s, cs = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def words_to_ass(words: list[dict], per_card: int = 3, offset: float = 0.0) -> str:
    """One event per word; the card shows up to `per_card` words, active one lit."""
    lines = [HEADER]
    ws = [w for w in words if w["end"] > offset]
    for i in range(0, len(ws), per_card):
        group = ws[i:i + per_card]
        for j, w in enumerate(group):
            start = max(w["start"] - offset, 0.0)
            end = max(w["end"] - offset, start + 0.05)
            text = " ".join(
                (f"{{\\c{ACTIVE}}}{x['word'].strip().upper()}{{\\c&HFFFFFF&}}" if k == j
                 else x["word"].strip().upper())
                for k, x in enumerate(group))
            lines.append(f"Dialogue: 0,{_ts(start)},{_ts(end)},Default,,0,0,0,,{text}\n")
    return "".join(lines)


def transcribe_words(path: str, model: str = "small") -> list[dict]:
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:  # optional dependency
        raise RuntimeError("pip install faster-whisper, or pass --words words.json") from e
    segs, _ = WhisperModel(model).transcribe(path, word_timestamps=True)
    return [{"word": w.word, "start": w.start, "end": w.end}
            for s in segs for w in (s.words or [])]
