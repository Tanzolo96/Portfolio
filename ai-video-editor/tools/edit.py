#!/usr/bin/env python3
"""AI Video Editor pipeline.

    python3 tools/edit.py "Raw Footage/clip.mp4"            # transcribe, cut, plan, storyboard (no render)
    python3 tools/edit.py "Raw Footage/clip.mp4" --render   # same, then render to Exports/

Steps, all cached in work/<clip>/ so a re-run after a tweak is fast:
  1. Whisper transcript with word timestamps      -> work/<clip>/transcript.json
  2. Keep-list: drop pauses, filler words, retakes -> work/<clip>/segments.json
  3. FFmpeg cut + reframe to the output size       -> remotion/public/<clip>/cut.mp4
  4. Captions, hook, zooms, music                  -> work/<clip>/edit.json (Remotion props)
  5. Storyboard for review                         -> work/<clip>/storyboard.html (+ .png)
  6. Remotion render (only with --render)          -> Exports/<clip>_edit.mp4

Look settings come from style.json; override per video with --set key=value.
"""
import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REMOTION = ROOT / "remotion"
PUBLIC = REMOTION / "public"
MUSIC_DIR = ROOT / "music"
EXPORTS = ROOT / "Exports"

FILLERS = {"um", "umm", "uh", "uhh", "erm", "er", "ah", "hmm", "mm", "mhm"}
ASPECTS = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080), "4:5": (1080, 1350)}


def run(cmd, **kw):
    print("  $", " ".join(str(c) for c in cmd)[:220], flush=True)
    return subprocess.run(cmd, check=True, **kw)


def probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
        check=True, capture_output=True, text=True).stdout
    info = json.loads(out)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    w, h = int(v["width"]), int(v["height"])
    rot = 0
    for sd in v.get("side_data_list", []):
        rot = int(sd.get("rotation", 0) or 0)
    rot = int(v.get("tags", {}).get("rotate", rot))
    if abs(rot) in (90, 270):
        w, h = h, w
    num, den = (v.get("avg_frame_rate") or "30/1").split("/")
    fps = float(num) / float(den or 1) if float(num) else 30.0
    has_audio = any(s["codec_type"] == "audio" for s in info["streams"])
    return {"w": w, "h": h, "fps": fps, "dur": float(info["format"]["duration"]), "audio": has_audio}


# ---------------------------------------------------------------- 1. transcript
def transcribe(src, work, model_name, language):
    out = work / "transcript.json"
    meta = {"model": model_name, "language": language}
    if out.exists():
        cached = json.loads(out.read_text())
        if cached.get("meta") == meta:
            print("1/6 transcript: cached")
            return cached
    print(f"1/6 transcribing with Whisper ({model_name}) ...")
    import whisper  # imported lazily so --help works without it

    model = whisper.load_model(model_name)
    res = model.transcribe(str(src), word_timestamps=True, language=language, verbose=False,
                           condition_on_previous_text=False)
    words = []
    for seg in res["segments"]:
        for w in seg.get("words", []):
            text = w["word"].strip()
            if text:
                words.append({"text": text, "start": round(w["start"], 3), "end": round(w["end"], 3),
                              "p": round(w.get("probability", 1.0), 3)})
    data = {"meta": meta, "language": res.get("language"), "text": res["text"].strip(), "words": words}
    out.write_text(json.dumps(data, indent=1, ensure_ascii=False))
    return data


# ---------------------------------------------------------------- 2. keep-list
def norm(t):
    return re.sub(r"[^\w']", "", t.lower())


def plan_segments(words, dur, a):
    """Group words into spoken runs, then drop fillers, retakes and manual cuts."""
    dropped = []
    kept_words = []
    for w in words:
        if norm(w["text"]) in FILLERS:
            dropped.append({"start": w["start"], "end": w["end"], "reason": f"filler '{w['text']}'"})
        elif w["end"] <= a.trim_start or (a.trim_end and w["start"] >= dur - a.trim_end):
            dropped.append({"start": w["start"], "end": w["end"], "reason": "trimmed"})
        elif any(c0 <= w["start"] < c1 for c0, c1 in a.cut):
            dropped.append({"start": w["start"], "end": w["end"], "reason": "manual cut"})
        else:
            kept_words.append(w)

    runs = []
    for w in kept_words:
        if runs and w["start"] - runs[-1][-1]["end"] <= a.max_gap:
            runs[-1].append(w)
        else:
            runs.append([w])

    # Retakes: a run whose opening words are repeated by the next run is a false start.
    final = []
    for i, r in enumerate(runs):
        nxt = runs[i + 1] if i + 1 < len(runs) else None
        if nxt and not a.keep_retakes:
            n = min(3, len(r), len(nxt))
            if n >= 2 and [norm(x["text"]) for x in r[:n]] == [norm(x["text"]) for x in nxt[:n]]:
                dropped.append({"start": r[0]["start"], "end": r[-1]["end"],
                                "reason": "retake: " + " ".join(x["text"] for x in r)})
                continue
        final.append(r)

    segs = []
    for r in final:
        s = max(0.0, r[0]["start"] - a.pad_in, a.trim_start)
        e = min(dur - (a.trim_end or 0), r[-1]["end"] + a.pad_out)
        if segs and s <= segs[-1]["end"] + 0.05:
            segs[-1]["end"] = e
            segs[-1]["words"] += r
        else:
            segs.append({"start": s, "end": e, "words": list(r)})
    return segs, dropped


# ---------------------------------------------------------------- 3. cut
def cut_video(src, segs, info, out, size, fps):
    W, H = size
    if out.exists() and out.with_suffix(".key").exists() and \
            out.with_suffix(".key").read_text() == json.dumps([segs_key(segs), size, fps]):
        print("3/6 cut: cached")
        return
    print(f"3/6 cutting {len(segs)} segments with FFmpeg ...")
    parts = []
    for i, s in enumerate(segs):
        parts.append(f"[0:v]trim={s['start']:.3f}:{s['end']:.3f},setpts=PTS-STARTPTS[v{i}];")
        if info["audio"]:
            parts.append(f"[0:a]atrim={s['start']:.3f}:{s['end']:.3f},asetpts=PTS-STARTPTS,"
                         f"afade=t=in:d=0.02,afade=t=out:st={max(0, s['end'] - s['start'] - 0.03):.3f}:d=0.03[a{i}];")
    n = len(segs)
    streams = "".join(f"[v{i}]" + (f"[a{i}]" if info["audio"] else "") for i in range(n))
    graph = "".join(parts) + f"{streams}concat=n={n}:v=1:a={1 if info['audio'] else 0}[cv]" + \
        ("[ca];[ca]loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000[oa]" if info["audio"] else "") + ";" + \
        f"[cv]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={fps},setsar=1[ov]"
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(src), "-filter_complex", graph, "-map", "[ov]"]
    if info["audio"]:
        cmd += ["-map", "[oa]", "-c:a", "aac", "-b:a", "192k"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-pix_fmt", "yuv420p", str(out)]
    run(cmd)
    out.with_suffix(".key").write_text(json.dumps([segs_key(segs), size, fps]))


def segs_key(segs):
    return [[round(s["start"], 3), round(s["end"], 3)] for s in segs]


# ---------------------------------------------------------------- 4. captions / zooms / music
def remap(segs):
    """Source-time words -> output-time words."""
    out, offset = [], 0.0
    for s in segs:
        for w in s["words"]:
            out.append({"text": w["text"], "start": round(w["start"] - s["start"] + offset, 3),
                        "end": round(w["end"] - s["start"] + offset, 3)})
        s["out_start"] = offset
        offset += s["end"] - s["start"]
        s["out_end"] = offset
    return out, offset


def group_captions(words, max_words, max_chars, emphasize):
    """Short caption chunks; each emphasis word gets a beat of its own."""
    caps, cur = [], []
    is_emph = lambda w: norm(w["text"]) in emphasize
    for i, w in enumerate(words):
        if is_emph(w):
            if cur:
                caps.append(cur)
            caps.append([w])
            cur = []
            continue
        cur.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        text = " ".join(x["text"] for x in cur)
        if (len(cur) >= max_words or len(text) >= max_chars or re.search(r"[.!?,:;]$", w["text"])
                or nxt is None or is_emph(nxt) or nxt["start"] - w["end"] > 0.3):
            caps.append(cur)
            cur = []
    result = []
    for i, c in enumerate(caps):
        end = c[-1]["end"]
        if i + 1 < len(caps):
            end = max(end, min(caps[i + 1][0]["start"], end + 0.4))
        result.append({"start": c[0]["start"], "end": round(end, 3), "emphasis": len(c) == 1 and is_emph(c[0]),
                       "words": [{**w, "text": re.sub(r"[.,!?;:]$", "", w["text"])} for w in c]})
    return result


def make_zooms(segs, scale):
    # Alternate punch-in on every other jump cut so cuts feel intentional.
    return [{"start": round(s["out_start"], 3), "end": round(s["out_end"], 3), "scale": scale}
            for i, s in enumerate(segs) if i % 2 == 1 and scale > 1]


def pick_music(arg, total, pub):
    if arg == "none":
        return None
    src = Path(arg) if arg else next((p for p in sorted(MUSIC_DIR.glob("*"))
                                      if p.suffix.lower() in (".mp3", ".wav", ".m4a", ".aac", ".ogg")), None)
    dest = pub / "music.m4a"
    if src:
        print(f"    music: {src.name}")
        run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-t", f"{total + 1:.2f}", "-af",
             f"afade=t=out:st={max(0, total - 1.5):.2f}:d=1.5", "-c:a", "aac", str(dest)])
    else:
        print("    music: none in music/ - generating a soft placeholder bed (swap in a real track)")
        # Am - F - C - G pad, 4s per chord, with a gentle pulse
        chords = [(220.0, 261.63, 329.63), (174.61, 220.0, 261.63), (261.63, 329.63, 392.0), (196.0, 246.94, 293.66)]
        expr = "+".join(
            f"if(between(mod(t,16),{i*4},{i*4+4}),(" + "+".join(f"sin(2*PI*{f}*t)" for f in c) + ")/3,0)"
            for i, c in enumerate(chords))
        run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
             f"aevalsrc='0.35*({expr})*(0.75+0.25*sin(2*PI*2*t))':s=44100:d={total + 1:.2f}",
             "-af", f"lowpass=f=1800,afade=t=in:d=1,afade=t=out:st={max(0, total - 1.5):.2f}:d=1.5",
             "-c:a", "aac", str(dest)])
    return dest


# ---------------------------------------------------------------- 5. storyboard
def storyboard(work, cut, edit, segs, dropped, transcript, name):
    print("5/6 building storyboard (rendering frames through Remotion) ...")
    frames = work / "frames"
    if frames.exists():
        shutil.rmtree(frames)
    beats = edit["captions"] or [{"start": s["out_start"], "end": s["out_end"], "words": []} for s in segs]
    fps = edit["fps"]
    # the frame where the last word of each caption is lit, so the highlight shows
    picks = [int(((b["words"][-1]["start"] + b["words"][-1]["end"]) / 2 if b["words"] else (b["start"] + b["end"]) / 2)
                 * fps) for b in beats]
    try:
        run(["node", "storyboard.mjs", str(work / "edit.json"), str(frames), *map(str, picks)],
            cwd=REMOTION, stdout=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        print("    Remotion stills failed - falling back to plain frames (no captions drawn)")
        frames.mkdir(exist_ok=True)
        for i, f in enumerate(picks):
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{f / fps:.3f}", "-i", str(cut), "-frames:v", "1",
                            "-vf", "scale=270:-2", "-q:v", "4", str(frames / f"{i:03d}.jpg")], check=True)

    cards = []
    for i, b in enumerate(beats):
        zoom = any(z["start"] <= b["start"] < z["end"] for z in edit["zooms"])
        said = html.escape(" ".join(w["text"] for w in b["words"]))
        cards.append(f'''<figure><img src="frames/{i:03d}.jpg"><figcaption><b>{b["start"]:.1f}s</b>'''
                     f'''{" · zoom" if zoom else ""}<br>{said}</figcaption></figure>''')
    drops = "".join(f"<li><b>{d['start']:.2f}-{d['end']:.2f}s</b> {html.escape(d['reason'])}</li>" for d in dropped) \
        or "<li>nothing</li>"
    seglist = "".join(f"<li>{s['start']:.2f}-{s['end']:.2f}s → {s['out_start']:.2f}s: "
                      f"{html.escape(' '.join(w['text'] for w in s['words']))}</li>" for s in segs)
    page = f"""<!doctype html><meta charset="utf-8"><title>Storyboard · {html.escape(name)}</title>
<style>
body{{font:14px system-ui,sans-serif;background:#111;color:#eee;margin:24px}}
h1{{margin:0 0 4px}} .meta{{color:#aaa;margin-bottom:18px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:12px}}
figure{{margin:0}} img{{width:100%;display:block;border-radius:8px;background:#000}}
figcaption{{color:#aaa;font-size:12px;padding:4px 2px}} ul{{color:#ccc}}
</style>
<h1>Storyboard · {html.escape(name)}</h1>
<div class="meta">{edit['width']}×{edit['height']} · {edit['durationInFrames'] / edit['fps']:.1f}s
(raw {transcript['raw_dur']:.1f}s, {len(segs)} segments) · hook: “{html.escape(edit['hook']['text']) if edit['hook'] else 'none'}”
· music: {'on, volume ' + str(edit['music']['volume']) if edit['music'] else 'off'}</div>
<div class="grid">{''.join(cards)}</div>
<h2>Removed</h2><ul>{drops}</ul>
<h2>Kept segments (source → output)</h2><ul>{seglist}</ul>
<h2>Full transcript</h2><p style="color:#ccc">{html.escape(transcript['text'])}</p>
"""
    (work / "storyboard.html").write_text(page)
    cols = min(6, len(beats))
    run(["ffmpeg", "-v", "error", "-y", "-framerate", "1", "-i", str(frames / "%03d.jpg"), "-vf",
         f"tile={cols}x{(len(beats) + cols - 1) // cols}:padding=6:color=black", "-frames:v", "1",
         str(work / "storyboard.png")])


# ---------------------------------------------------------------- 6. render
def render(edit_path, out, scale):
    print("6/6 rendering with Remotion ...")
    cmd = ["npx", "remotion", "render", "Edit", str(out), f"--props={edit_path}", f"--scale={scale}"]
    if os.environ.get("REMOTION_BROWSER"):
        cmd.append(f"--browser-executable={os.environ['REMOTION_BROWSER']}")
    run(cmd, cwd=REMOTION)


def parse_set(pairs):
    out = {}
    for p in pairs:
        k, _, v = p.partition("=")
        try:
            out[k] = json.loads(v)
        except json.JSONDecodeError:
            out[k] = v
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", help="raw clip, e.g. 'Raw Footage/take1.mp4'")
    ap.add_argument("--emphasize", default="", help="comma-separated words shown big and red, e.g. 'rejected,quit'")
    ap.add_argument("--hook", help="text hook shown at the start (default: first sentence)")
    ap.add_argument("--hook-duration", type=float, default=None)
    ap.add_argument("--no-hook", action="store_true")
    ap.add_argument("--music", default="", help="audio file, 'none', or empty = first file in music/")
    ap.add_argument("--music-volume", type=float, default=None)
    ap.add_argument("--aspect", choices=list(ASPECTS) + ["source"], default=None)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--model", default="small", help="Whisper model: tiny/base/small/medium/large")
    ap.add_argument("--language", default=None, help="e.g. en, hi (default: auto-detect)")
    ap.add_argument("--max-gap", type=float, default=None, help="pause (s) longer than this gets cut")
    ap.add_argument("--pad-in", type=float, default=0.08)
    ap.add_argument("--pad-out", type=float, default=0.15)
    ap.add_argument("--trim-start", type=float, default=0.0, help="always drop the first N seconds")
    ap.add_argument("--trim-end", type=float, default=0.0, help="always drop the last N seconds")
    ap.add_argument("--cut", action="append", default=[], help="drop a source range, e.g. --cut 4.2-6.0")
    ap.add_argument("--keep-retakes", action="store_true")
    ap.add_argument("--set", action="append", default=[], help="style override, e.g. --set captionFontSize=96")
    ap.add_argument("--render", action="store_true", help="render the final video to Exports/")
    ap.add_argument("--preview", action="store_true", help="fast half-size render to work/<clip>/preview.mp4")
    a = ap.parse_args()

    style = json.loads((ROOT / "style.json").read_text()) if (ROOT / "style.json").exists() else {}
    style.update(parse_set(a.set))
    a.max_gap = a.max_gap if a.max_gap is not None else style.get("maxPause", 0.4)
    a.cut = [tuple(float(x) for x in c.split("-", 1)) for c in a.cut]

    src = Path(a.video).resolve()
    if not src.exists():
        sys.exit(f"not found: {src}")
    name = re.sub(r"[^\w-]+", "_", src.stem)
    work = ROOT / "work" / name
    pub = PUBLIC / name
    work.mkdir(parents=True, exist_ok=True)
    pub.mkdir(parents=True, exist_ok=True)

    info = probe(src)
    aspect = a.aspect or style.get("aspect", "9:16")
    size = (info["w"] - info["w"] % 2, info["h"] - info["h"] % 2) if aspect == "source" else ASPECTS[aspect]

    tr = transcribe(src, work, a.model, a.language) if info["audio"] else {"text": "", "words": []}
    tr["raw_dur"] = info["dur"]
    if not tr["words"]:
        print("    no speech found - keeping the whole clip, no captions")
        segs = [{"start": a.trim_start, "end": info["dur"] - a.trim_end, "words": []}]
        dropped = []
    else:
        segs, dropped = plan_segments(tr["words"], info["dur"], a)
    print(f"2/6 keep-list: {len(segs)} segments, {len(dropped)} removals")

    cut = pub / "cut.mp4"
    cut_video(src, segs, info, cut, size, a.fps)
    words, total = remap(segs)
    total = probe(cut)["dur"]

    print("4/6 captions, hook, zooms, music ...")
    emphasize = {norm(w) for w in a.emphasize.split(",") if w.strip()}
    caps = group_captions(words, style.get("captionMaxWords", 3), style.get("captionMaxChars", 18), emphasize) \
        if style.get("captions", True) else []
    hook = None
    if not a.no_hook and style.get("hook", True):
        text = a.hook
        if not text and tr["text"]:
            text = re.split(r"(?<=[.!?])\s", tr["text"].strip())[0]
            text = " ".join(text.split()[:9])
        if text:
            hook = {"text": text, "duration": a.hook_duration or style.get("hookDuration", 2.5)}
    music_file = pick_music(a.music, total, pub) if style.get("music", True) or a.music else None
    music = {"src": f"{name}/{music_file.name}",
             "volume": a.music_volume if a.music_volume is not None else style.get("musicVolume", 0.12)} \
        if music_file else None

    edit = {
        "video": f"{name}/cut.mp4",
        "width": size[0], "height": size[1], "fps": a.fps,
        "durationInFrames": max(1, int(total * a.fps)),
        "captions": caps, "hook": hook, "music": music,
        "zooms": make_zooms(segs, style.get("zoomScale", 1.08)),
        "style": {k: v for k, v in style.items() if k.startswith(("caption", "hook", "emphasis"))},
    }
    edit_path = work / "edit.json"
    edit_path.write_text(json.dumps(edit, indent=1, ensure_ascii=False))
    (work / "segments.json").write_text(json.dumps({"kept": segs, "removed": dropped}, indent=1, ensure_ascii=False))

    storyboard(work, cut, edit, segs, dropped, tr, name)
    print(f"\nStoryboard: {work / 'storyboard.html'}\n            {work / 'storyboard.png'}")
    print(f"Length: {info['dur']:.1f}s raw -> {total:.1f}s edited")

    if a.preview:
        render(edit_path, work / "preview.mp4", 0.5)
        print(f"Preview: {work / 'preview.mp4'}")
    if a.render:
        EXPORTS.mkdir(exist_ok=True)
        out = EXPORTS / f"{name}_edit.mp4"
        render(edit_path, out, 1)
        print(f"Exported: {out}")
    elif not a.preview:
        print("Review the storyboard, then re-run with --render to export.")


if __name__ == "__main__":
    main()
