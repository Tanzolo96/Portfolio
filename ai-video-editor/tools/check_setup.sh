#!/usr/bin/env bash
# Reports which editing tools are installed, with the install command for anything missing.
ok() { printf "  \033[32mready\033[0m    %-10s %s\n" "$1" "$2"; }
miss() { printf "  \033[31mmissing\033[0m  %-10s install: %s\n" "$1" "$2"; MISSING=1; }
cd "$(dirname "$0")/.."
OS=$(uname -s)

echo "AI Video Editor - setup check"
if command -v ffmpeg >/dev/null; then ok FFmpeg "$(ffmpeg -version | head -1 | cut -d' ' -f3)"
else miss FFmpeg "$([ "$OS" = Darwin ] && echo 'brew install ffmpeg' || echo 'sudo apt install ffmpeg  (Windows: winget install ffmpeg)')"; fi

if command -v node >/dev/null; then ok Node.js "$(node -v)"
else miss Node.js "https://nodejs.org (LTS)  or  $([ "$OS" = Darwin ] && echo 'brew install node' || echo 'winget install OpenJS.NodeJS.LTS')"; fi

if command -v python3 >/dev/null; then ok Python "$(python3 --version | cut -d' ' -f2)"
else miss Python "https://www.python.org/downloads/"; fi

if python3 -c "import whisper" 2>/dev/null; then ok Whisper "openai-whisper $(python3 -c 'import importlib.metadata as m;print(m.version("openai-whisper"))')"
else miss Whisper "pip3 install -U openai-whisper"; fi

if [ -x remotion/node_modules/.bin/remotion ]; then ok Remotion "$(node -p "require('./remotion/node_modules/remotion/package.json').version")"
else miss Remotion "cd remotion && npm install"; fi

if ls .claude/skills/remotion-* >/dev/null 2>&1; then ok Skills "Remotion agent skills ($(ls -d .claude/skills/remotion-* | wc -l | tr -d ' '))"
else miss Skills "npx skills add remotion-dev/skills"; fi

[ -z "$MISSING" ] && echo "Everything is ready." || echo "Install the missing tools above, then run this again."
