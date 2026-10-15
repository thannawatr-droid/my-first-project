# Plan v1

## Root

Required: `version: 1`, `output` ending `.mp4`, nonempty `clips` list. Optional: `video`, `texts`, `subtitles`, `audio`, `overlays`. Unknown keys are rejected. Paths are absolute or relative to the JSON plan directory. Inputs must exist. Seconds must be finite numbers. Timed elements use FINAL output time, not source time.

## Video

`video`: width (1920), height (1080), fps (30), crf (20), preset (`medium`). Dimensions are even integers 128–7680, fps integer 1–120, CRF integer 0–40. Presets: ultrafast, veryfast, fast, medium, slow. Lower CRF = higher quality/larger file. Draft 960×540 or 540×960, final 1920×1080 or 1080×1920. Explicit text `size` values are pixels; scale them in draft plans.

## Clips

| Key | Values/default |
| --- | --- |
| source | Required video path; first video/audio streams used |
| in / out | Source seconds; defaults 0 / duration |
| speed | .25–4, default 1; tempo adjustment without intentional pitch shift |
| fit | contain (default, letterbox) / cover (crop) |
| crop_x / crop_y | Anchor 0–1, default .5; static, no tracking |
| zoom | Static scale 1–2, default 1 |
| volume | 0–4, default 1; 0 mutes source |
| grade | natural (default), cinematic, horror, warm, mono |
| denoise | Boolean, default false; high-pass + mild spectral denoise |
| fade_in / fade_out | Seconds, default 0; <= half output clip length |
| transition | INCOMING transition object: type, duration |

Transitions: cut, fade, dissolve, wipeleft, wiperight, slideleft, slideright, circleopen. First clip must be cut. Cut duration = 0. Other durations default .4 seconds, must be positive and shorter than both adjacent clips. Transition audio crossfades. Picture fade_in/out is fade to/from black, distinct from overlap transition.

Clip duration = (out-in)/speed rounded to output frame. Timeline duration = sum(clip durations) minus overlaps. Every title/subtitle/overlay must fall within it. Tiny source rounding tolerance is .05 seconds. Minimum clip duration is two frames. Silent sources receive stereo silence. Rotation metadata is handled by FFmpeg autorotation.

## Titles and subtitles

`texts`: list of objects, required `text`, `start`, `end`. Text must be nonempty. End > start by at least .02 seconds. Literal line breaks supported. User text cannot inject raw ASS overrides.

| Key | Meaning |
| --- | --- |
| style | clean default; bold, smooth, horror, neon, caption |
| animation | none, fade, slide, pop, ghost, typewriter; default by style |
| position | top, center default, bottom; centered at y=.18/.5/.78 |
| x / y | Optional center overrides, normalized .05–.95 |
| size | Pixels, default fraction of shorter frame dimension |
| color | RGB hex, e.g. #FFFFFF; overrides main text |
| max_width | Frame width fraction .1–.9, default .82 |
| max_lines | Integer 1–5, default 3; shrinks text or rejects oversized copy |
| reveal | Typewriter seconds, default 1, capped at 70% of cue duration |

Text uses bundled Noto Sans Thai with libass shaping. Typewriter keeps a fixed layout and reveals combining-safe clusters. Automatic wrap is not Thai linguistic segmentation: manually break semantic phrases. Use fade/slide for dialogue. Unsupported glyphs (including many emoji) fail explicitly; use a supplied image overlay for such graphics. No rapid strobe effect is bundled.

`subtitles`: object with required `source` SRT path, optional `style` (caption) and `position` (bottom). UTF-8, plain text, no HTML styling. Timecodes refer to output; remap source transcripts first. SRT is burned into video. Thai + English can be two literal lines; translation must be provided/reviewed separately.

## Audio

`audio`: `tracks` list, `duck_music` boolean (true), optional `normalize_lufs` (-24 to -9, e.g. -16). Single-pass loudnorm: inspect reported measurements, not guaranteed broadcast compliance. Limiter approximately -1.5 dBFS before AAC; encoding may introduce intersample overshoot.

Track keys: `source` required; `role` music (default)/voice/sfx; `start` output seconds (0); `in` source seconds (0); `duration` (defaults shorter of remaining source or timeline); `volume` (music .2, others 1), `fade_in`, `fade_out` (0, <= half track duration); `loop` boolean (false). Explicit duration required to loop longer than source. Loop input follows FFmpeg seeking/looping behavior; use in=0 for predictable full-track repeats. All tracks mixed at stereo 48 kHz. SFX are not ducked.

Ducking responds to base clip audio plus voice tracks; music already embedded in source also triggers it. Not semantic speech detection. No voice/music generation or automatic beat synchronization.

## Overlays

`overlays`: still PNG/JPG/JPEG/WebP objects with required source, start, end. x/y are normalized top-left (default .05), width is normalized .01–1 (default .2); opacity 0–1 (1). Height preserves image ratio. Must fit entirely inside frame. Alpha preserved. No keyframe motion or video overlay; add SFX separately.

## Example

Replace with inspected real files; a.mp4/b.mp4 need >=5 seconds and music.wav >=9.6 seconds.

```json
{
  "version": 1,
  "output": "outputs/horror-v1.mp4",
  "video": {"width": 1080, "height": 1920, "fps": 30, "crf": 20, "preset": "medium"},
  "clips": [
    {"source": "a.mp4", "in": 0, "out": 5, "fit": "cover", "grade": "horror", "denoise": true},
    {"source": "b.mp4", "in": 0, "out": 5, "fit": "cover", "transition": {"type": "fade", "duration": 0.4}}
  ],
  "texts": [
    {"text": "อย่าเปิดประตู", "start": 0.2, "end": 3.2, "style": "horror", "animation": "ghost"},
    {"text": "DON'T OPEN THE DOOR", "start": 0.5, "end": 3.2, "style": "clean", "size": 30, "y": 0.59},
    {"text": "เรื่องราวเพิ่งเริ่มต้น", "start": 7, "end": 9.4, "style": "smooth"}
  ],
  "audio": {"duck_music": true, "normalize_lufs": -16, "tracks": [
    {"source": "music.wav", "role": "music", "duration": 9.6, "volume": 0.15, "fade_in": 0.5, "fade_out": 1}
  ]}
}
```

## Outputs and limits

MP4 H.264/AAC, yuv420p, fixed output fps, faststart. Sidecars: .report.json (decode/dimensions/duration/codecs/loudness), .timeline.csv (source cuts and output timing), .ass (when text enabled). CSV/ASS are not native CapCut projects. MP4 titles are permanent pixels. Intermediates are re-encoded video and PCM sound; this is not lossless. Require sufficient disk/RAM; split lengthy episodes into reviewed chapters if needed.

`render --no-text` suppresses titles and captions, retains image overlays. Use a distinct output name. Output/source identity check prevents overwriting inputs. Existing render/sidecars require `--overwrite`. Automatic QA does not certify visual/editorial quality or claim the audio was heard.
