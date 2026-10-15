# Video editing project

For video editing, read `.agents/skills/edit-video-director/SKILL.md` and use its bundled scripts.

- Use the project-local `.venv/bin/python` (Windows `.venv\Scripts\python.exe`) if present.
- Prepare a new environment with `python3 setup_video.py --transcribe` after checking FFmpeg/ffprobe. To also fetch a multilingual small model, add `--download-model small`.
- Models belong in `models/`; media in `media/`; renders/plans/reports in `outputs/`. These folders are ignored by Git. Keep user footage, transcripts and credentials out of commits.
- A cloud task does not have automatic access to the user's computer or CapCut. Do not claim local desktop installation from a cloud-only setup.
- Preserve source media, inspect video/audio before choosing edits, validate the edit plan, then render and verify.
- Use the bundled Thai fonts for Thai captions. Speech transcription requires reviewed source audio and is not guaranteed to be accurate.
- Integration test: `.venv/bin/python .agents/skills/edit-video-director/scripts/test_workflow.py`.
- Do not automatically upload media or publish videos. Repository setup does not authorize media publication.
