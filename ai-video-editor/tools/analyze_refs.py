#!/usr/bin/env python3
"""Measure the editing style of the videos in References/.

    python3 tools/analyze_refs.py [--transcribe]

For each video: resolution, length, cut count, cuts per second, average shot
length, loudness and silence, plus a contact sheet (work/_refs/<name>.png) and
one full-size frame per shot for reading caption font, size and position.
With --transcribe it also measures speech rate and pauses using Whisper.
Writes work/_refs/report.json and prints a summary to base style.md on.
"""
import json
import re
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REFS = ROOT / "References"
OUT = ROOT / "work" / "_refs"
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}


def ff(args):
    return subprocess.run(["ffmpeg", "-hide_banner", *args], capture_output=True, text=True).stderr


def analyze(path, transcribe):
    info = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
        capture_output=True, text=True, check=True).stdout)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    dur = float(info["format"]["duration"])
    has_audio = any(s["codec_type"] == "audio" for s in info["streams"])

    log = ff(["-i", str(path), "-vf", "select='gt(scene,0.3)',showinfo", "-an", "-f", "null", "-"])
    cuts = [float(x) for x in re.findall(r"pts_time:([0-9.]+)", log)]
    bounds = [0.0, *cuts, dur]
    shots = [b - a for a, b in zip(bounds, bounds[1:]) if b - a > 0.05]

    name = re.sub(r"[^\w-]+", "_", path.stem)
    ff(["-y", "-i", str(path), "-vf", "fps=2,scale=180:-2,tile=8x4", "-frames:v", "1", str(OUT / f"{name}.png")])
    frames = OUT / name
    frames.mkdir(exist_ok=True)
    for i, (a, b) in enumerate(zip(bounds, bounds[1:])):
        ff(["-y", "-ss", f"{(a + b) / 2:.2f}", "-i", str(path), "-frames:v", "1", str(frames / f"shot{i:02d}.jpg")])

    r = {"file": path.name, "size": f"{v['width']}x{v['height']}", "duration": round(dur, 2),
         "cuts": len(cuts), "cuts_per_10s": round(len(cuts) / dur * 10, 2),
         "avg_shot": round(statistics.mean(shots), 2) if shots else dur,
         "median_shot": round(statistics.median(shots), 2) if shots else dur,
         "contact_sheet": str((OUT / f"{name}.png").relative_to(ROOT)),
         "shot_frames": str(frames.relative_to(ROOT))}
    if has_audio:
        lo = ff(["-i", str(path), "-af", "ebur128", "-vn", "-f", "null", "-"])
        m = re.findall(r"I:\s+(-?[0-9.]+) LUFS", lo)
        r["loudness_lufs"] = float(m[-1]) if m else None
        sil = ff(["-i", str(path), "-af", "silencedetect=n=-35dB:d=0.25", "-vn", "-f", "null", "-"])
        gaps = [float(x) for x in re.findall(r"silence_duration: ([0-9.]+)", sil)]
        r["silences_over_0.25s"] = len(gaps)
        r["longest_silence"] = round(max(gaps), 2) if gaps else 0
    if has_audio and transcribe:
        import whisper
        res = whisper.load_model("small").transcribe(str(path), word_timestamps=True, verbose=False)
        words = [w for s in res["segments"] for w in s.get("words", [])]
        if words:
            pauses = [b["start"] - a["end"] for a, b in zip(words, words[1:])]
            r["words_per_min"] = round(len(words) / dur * 60)
            r["max_pause"] = round(max(pauses), 2) if pauses else 0
            r["language"] = res.get("language")
            r["transcript"] = res["text"].strip()
    return r


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    vids = sorted(p for p in REFS.rglob("*") if p.suffix.lower() in VIDEO_EXT)
    if not vids:
        sys.exit("No videos in References/. Add 3-5 clips (or download links there first).")
    report = [analyze(p, "--transcribe" in sys.argv) for p in vids]
    (OUT / "report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False))
    for r in report:
        print(json.dumps({k: v for k, v in r.items() if k != "transcript"}, ensure_ascii=False))
    print(f"\nAverage shot length across refs: {statistics.mean(r['avg_shot'] for r in report):.2f}s")
    print(f"Report: {OUT / 'report.json'}   Contact sheets + shot frames: {OUT}/")


if __name__ == "__main__":
    main()
