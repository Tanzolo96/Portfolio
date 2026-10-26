# AI Video Editor

This folder is a video editor that Claude runs. The user films, drops raw clips in `Raw Footage/`, and asks for an edit. You cut it, caption it, add music and a hook, show a storyboard, and export to `Exports/` once they approve.

## Folders

| Path | What |
|---|---|
| `Raw Footage/` | the user's raw clips (input) |
| `References/` | videos of the editing style to copy (`links.txt` lists where they came from) |
| `Exports/` | finished videos (output) |
| `music/` | background tracks; the first audio file here is used by default |
| `style.md` | brand sheet: the editing style in words |
| `style.json` | the same style as numbers the pipeline reads (caption size, colours, pause length...) |
| `tools/edit.py` | the pipeline: Whisper → cut → captions/hook/zoom/music → storyboard → Remotion render |
| `tools/analyze_refs.py` | measures reference videos (cut rate, shot lengths, loudness) and makes contact sheets |
| `remotion/` | Remotion project (`src/Edit.tsx` draws captions, hook, zooms, music) |
| `work/<clip>/` | per-clip scratch: transcript, edit.json, storyboard |

## Setup check ("is everything installed?")

Run `tools/check_setup.sh`. It reports FFmpeg, Node.js, Python, Whisper and Remotion and prints the install command for anything missing.

## Studying references → style.md

1. `python3 tools/analyze_refs.py` (reads every video in `References/`; for links, download them first with `yt-dlp` if the user is allowed to).
2. Look at the contact sheets it writes to `work/_refs/` (Read the PNGs), and at single full-size frames for caption font, colour, position and size.
3. Rewrite `style.md` (pacing, cut frequency, captions, zooms, transitions, music, SFX, hook) and update `style.json` so the numbers match: e.g. `maxPause` from the cut rate, `captionMaxWords`, `captionFontSize` (px at 1080 wide), `captionY` (0 top → 1 bottom), colours, `captionUppercase`, `zoomScale`, `musicVolume`.
4. Show the user the brand sheet.

## Editing a clip

1. Run `python3 tools/edit.py "Raw Footage/<clip>"` once to get the transcript (`work/<clip>/transcript.json`).
2. From the transcript, write a title hook (≤ 8 words, the story's premise, per style.md) and pick emphasis words
   (one per emotional beat, about one every 5–10 s: verbs/outcomes like *rejected, quit, 48 hours*).
   Re-run: `python3 tools/edit.py "Raw Footage/<clip>" --hook "<hook>" --emphasize "word1,word2"` writes the storyboard and does not render.
3. Show the storyboard: read `work/<clip>/storyboard.png` and give the user the path to `work/<clip>/storyboard.html`. Summarise what was cut (the "Removed" list) and the final length.
4. After the user approves, re-run the same command with `--render`. Output: `Exports/<clip>_edit.mp4`.

Useful flags: `--emphasize a,b`, `--model small|medium` (better transcripts), `--language en|hi`, `--aspect 9:16|16:9|1:1|4:5|source`, `--music path|none`, `--music-volume 0.08`, `--trim-start 3`, `--trim-end 1`, `--cut 4.2-6.0` (source seconds), `--max-gap 0.3` (tighter pacing), `--keep-retakes`, `--no-hook`, `--preview` (fast half-size render), `--set captionFontSize=96` (any style.json key, this video only).

## Revisions ("captions too small", "music too loud", "cut the first 3 seconds")

Map the request to flags or style keys and re-run with `--render`:
- bigger/smaller captions → `--set captionFontSize=…` (default 62; emphasis words `emphasisFontSize`, default 120)
- move captions → `--set captionY=0.5` (centre, default) / `0.72` (lower third) / `0.2` (top)
- karaoke highlight / outline → `--set captionHighlight='"#FFE14D"'` / `--set captionStroke='"#000000"'`
- hook bigger/smaller/other colour → `--set hookFontSize=…` (default 130) / `--set hookColor='"#FFFFFF"'`
- music quieter/louder → `--music-volume …` (default 0.15)
- cut the first N seconds → `--trim-start N`
- wrong caption words → re-run with `--model medium` (delete `work/<clip>/transcript.json` only if it's still wrong) or fix words in `work/<clip>/transcript.json` by hand and re-run
If the user wants the change on every future video, put it in `style.json` (and style.md) instead of a flag. One change at a time when results get messy.

Anything the pipeline can't do (B-roll, sound effects, transitions, emoji, animated titles): edit `remotion/src/Edit.tsx` and use the Remotion skills in `.claude/skills/`.

## Notes

- Transcripts and cuts are cached in `work/`; re-runs only redo what changed.
- If Remotion can't find a browser, set `REMOTION_BROWSER=/path/to/chrome` before rendering.
- Music must be royalty-free / licensed for the platform. With an empty `music/`, a soft placeholder pad is generated; tell the user to swap it for a real track.
- Review every export before the user posts it.
