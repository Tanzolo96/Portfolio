# AI Video Editor

A folder-based video editor run by Claude Code. Film, drop the raw clip in `Raw Footage/`, and ask Claude:

> Edit the video in my Raw Footage folder using the style in style.md. Cut out pauses and mistakes, add captions,
> add background music, and add a text hook at the start. Before you render, show me a storyboard of the edit
> for my review. Save the final video to the Exports folder.

Then give feedback in plain words ("captions bigger", "music quieter", "cut the first 3 seconds") and it re-exports.

## On your computer (Claude Code desktop app)

1. Clone/pull this repo, open the Claude Code desktop app, start a **Local** chat and select this `ai-video-editor` folder.
2. Ask: *"Check whether FFmpeg, Node.js, Remotion and Whisper are installed. Install anything missing."*
   (Claude runs `tools/check_setup.sh`.) Manual equivalent:
   - FFmpeg: `brew install ffmpeg` (Mac) / `winget install ffmpeg` (Windows)
   - Node.js LTS: https://nodejs.org
   - Whisper: `pip3 install -U openai-whisper`
   - Remotion: `cd remotion && npm install`
3. Put a royalty-free track in `music/` (otherwise a soft placeholder pad is generated).
4. Drop a short clip (< 30 s to start) in `Raw Footage/` and use the prompt above.

`style.md` / `style.json` are already written from the 4 reference reels in `References/links.txt`.
To change the style, swap the references and ask Claude to *"study the References folder and rewrite style.md"*.

How it works and every option: see `CLAUDE.md`.
