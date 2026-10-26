# Brand sheet (style.md)

Built from 4 reference reels in `References/`:

| Ref | Format | Length | Cuts | Avg / median shot | Talk speed |
|---|---|---|---|---|---|
| `Dc0PdAest6S`: "Hi, I'm Dhruv… quit my job" (founder story) | 9:16 | 85.7 s | 54 | 1.6 s / 1.2 s | 256 wpm, longest pause 0.32 s |
| `DXKYyphuTYu`: "We built an app in 48 hours" | 9:16 | 33.2 s | 24 | 1.3 s / 0.8 s | 242 wpm, longest pause 0.5 s |
| `DdyT8aQsdXR`: "A week in the life of a 22 y/o creative director" | 16:9 | 17.3 s | 24 | 0.7 s / 0.5 s | music-led, no voice-over |
| `DSC3Zq5AZNW`: "The reality of being a 'content creator'" | 4:3, B&W | 34.7 s | 10 | 3.2 s / 2.3 s | music + text only |

All four are mastered to **−14 LUFS** and contain **no silent gaps** (no gap over 0.25 s).

## The style in one line
Fast, talky, story-driven reels: a big red title hook, tiny clean one-to-three-word captions in the
centre of the frame, a new shot roughly every 1.5 s, and one huge red word on each emotional beat.

## Format
- Vertical **9:16, 1080×1920, 30 fps** by default (the cinematic refs are 16:9 / 4:3; use `--aspect 16:9` for that look).
- Length 30–90 s.

## Pacing
- **A cut every ~1.2–1.6 s** (2.9–7 cuts per 10 s in the talking refs, up to 14 per 10 s in the montage ref).
- Rapid, no-breath delivery (~240–255 words/min). **Every pause over 0.25 s is cut**, along with fillers and false starts.
- Talking head is interrupted constantly by **B-roll that literally shows the line being said**
  ("quit my job" → office, "parents' house" → walking in the door, "CAT exam" → prep books).
- On talking-head stretches, jump cuts alternate between normal and a **110% punch-in**.

## Captions
- **1–3 words at a time**, swapping in time with speech (the "Dhruv" style). Never full sentences.
- **Inter SemiBold (≈ SF Pro / Instagram "Modern")**, **~62 px at 1080 wide** (small, about 6% of frame width per word),
  **sentence case**, tight letter-spacing (−0.04 em).
- **Pure white, no outline, no box**, only a faint soft shadow so it reads on bright shots.
- **Dead centre of the frame (50% down)**, over the subject's chest or face.
- No karaoke colour highlight. Each chunk just pops in quickly.

## Emphasis words
- One per emotional beat (about one every 5–10 s): the word goes **ALL CAPS, ~120 px, Inter ExtraBold, red #E3122B with a thin white outline**,
  alone on screen, punching in from 70% (like "REJECTED").
- Pick verbs/outcomes: *rejected, quit, failed, 48 hours, $10k*.

## Hook (first ~2 s)
- A **big red title over the opening shot**: **Anton (condensed), ALL CAPS, ~130 px, red #E3122B**, no box,
  top of frame, words landing one after another ("THE REALITY OF BEING A…", "we built an app in 48 hours").
- It states the story's premise in ≤ 8 words. Captions start after it.

## Graphics & transitions
- **Hard cuts only.** No wipes or dissolves.
- Occasional **full-screen flat colour cards** (pastel butter-yellow `#FFF3C4`, dusty blue `#A9BEDC`) with a single
  word, used as a beat between scenes.
- Small UI stickers/screenshots (score sheets, "Challenge complete" badges) pop into a corner when a fact is mentioned.
- Optional mood variants: **black & white grade with red serif text** (DSC3), **warm cinematic grade** (DdyT).

## Music & sound
- Music under everything, **voice clearly on top** (music ≈ 15% volume), fading out at the end.
- Final mix at **−14 LUFS**.
- Upbeat/lo-fi bed for story reels, a trending track for montage reels. Light whooshes/pops on emphasis words are optional.

## What the pipeline does automatically vs. what needs B-roll
- Automatic: pause/filler/retake cutting, captions, emphasis words (`--emphasize`), red title hook, punch-ins, music, loudness.
- Needs footage from you: B-roll and cutaways. Drop the clips in `Raw Footage/` named after what they show, and ask Claude to cut them in.
