# Setup and portability

Requires Python 3.10+, FFmpeg/ffprobe 6.1+ with libx264/AAC/libass, and Python packages in scripts/requirements.txt. `doctor` checks filters and fonts. Optional speech dependencies are in scripts/requirements-transcribe.txt. Model names may download weights; local model directories work offline. Keep caches out of Git.

Bundled Noto Sans Thai Regular/Bold are static instances of the Google Fonts variable font, with SIL OFL included. Thai and Latin glyphs are checked; emoji and unsupported glyphs fail explicitly. No font download is required to render.

Mac with Homebrew already installed:
```bash
brew install ffmpeg python
python3 -m venv .venv
.venv/bin/python -m pip install -r /path/to/edit-video-director/scripts/requirements.txt
.venv/bin/python /path/to/edit-video-director/scripts/director.py doctor
```
Windows: install an FFmpeg build containing libass/libx264, add ffmpeg/ffprobe to PATH, create a venv with `py -m venv .venv`, and install requirements with that environment's Python. Linux: use the available package manager and a venv. Network access may be needed. Never replace system Python or claim prerequisites were installed on a different computer.

Copy the ENTIRE edit-video-director folder to `.agents/skills/edit-video-director/` in a target Codex repository. Include scripts/references/assets/fonts/agents, not just SKILL.md. Saving this Work skill does not install it in a separate GitHub repo, desktop Codex or cloud environment. Code may be committed to Git; keep footage in media/ and outputs in outputs/, excluded with .gitignore along with .venv/, __pycache__/ and model caches. Cloud tasks need explicit access to media and cannot assume access to desktop paths.

Commands (resolve scripts against the skill directory):
```bash
python scripts/director.py doctor
python scripts/director.py inspect /media/clip.mp4
python scripts/director.py analyze /media/clip.mp4 /job/analysis.json
python scripts/director.py frames /media/clip.mp4 /job/frames --times 0.5 3 7
python scripts/director.py proxy /media/clip.mp4 /job/proxy.mp4 --width 960
python scripts/director.py transcribe /media/clip.mp4 /job/transcript.json --language th --model small
python scripts/director.py remap-captions /job/edit.json /job/edited.srt /job/transcript.json
python scripts/director.py validate /job/edit.json
python scripts/director.py render /job/edit.json
python scripts/director.py verify /job/final.mp4
python scripts/create_demo.py /job/demo
python scripts/director.py render /job/demo/showcase.json
```
New analytical/transcription/proxy outputs fail when a target exists. `render --overwrite` explicitly replaces the selected render and its sidecars. Frames need times inside the source duration.

Implementation references:
- https://ffmpeg.org/ffmpeg-filters.html
- https://aegisub.org/docs/latest/ass_tags/
- https://github.com/SYSTRAN/faster-whisper
- https://learn.chatgpt.com/docs/build-skills
- https://github.com/google/fonts/tree/main/ofl/notosansthai
