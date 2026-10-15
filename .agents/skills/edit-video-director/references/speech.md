# Speech and editorial decisions

`transcribe SOURCE OUTPUT.json --language th --model small` uses optional faster-whisper. CPU int8 is default; CUDA needs a compatible installation. A model name may download weights; use a local model path offline. `--vad` is opt-in because quiet speech can be removed. `--language auto` identifies a main language; mixed-language dialogue may still be inaccurate.

Outputs contain source-timed segments, words/probabilities and SRT. This is not translation, speaker diarization, identity inference or a best-take classifier. Check audio for hallucinations in silence, proper names, dates, amounts, negatives, jokes and mixed-language words. Word timings are approximate.

For repeated takes compare complete wording, delivery, noise, performance, focus, framing and continuity. Transcript alone cannot choose the best visual performance. Keep selected filename/in/out/reason. Avoid cutting phonemes and preserve the speaker's actual meaning.

`remap-captions PLAN OUTPUT.srt TRANSCRIPT1.json ...` maps reviewed source times through trims, speed changes and incoming overlaps. Every source needs a transcript; silent sources can have segments: []. Incoming captions take priority during overlaps; outgoing captions end at the next clip's start. Inspect speech crossfades against this policy.

Partial segments use fully included words. Without usable word timings, they are omitted with a warning instead of displaying speech that was removed. Correct the cut/caption as needed. For complex edits, transcribe a separate clean assembled export, review it, then use those final-output cues on the original plan. `--no-text` removes both titles and captions.

Ducking responds to signal amplitude, not semantic speech. Base clip audio plus voice tracks drives it; existing loud music can therefore trigger it. Supplied music/SFX only. Compare denoising before/after; keep it off when the source is clean. Loudness measurement is not listening.
