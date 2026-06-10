# Subtitle Everything — Dual-Source Transcription Design Spec
**Date:** 2026-06-09
**Status:** Approved

---

## Overview

When `audio.mode = "both"`, run two fully independent transcription pipelines — one for microphone, one for loopback — each with its own Whisper model instance and subtitle buffer. The overlay displays each source in its own container, color-coded and independently positioned. Single-source modes are unchanged.

---

## Goals

- Prevent mic and loopback audio from being interleaved into one Whisper stream
- Display each source's subtitles independently (color, vertical position)
- Keep RAM manageable by restricting dual-mode models to `tiny` or `base`
- Warn users at startup and in the settings page when running dual-source mode

---

## Config Changes

### `config.toml`

Replace the existing `transcription.model` field with two per-source model fields. Add four new display fields:

```toml
[transcription]
language = "en"
device = "cpu"
mic_model = "base"       # "tiny" or "base"
loopback_model = "base"  # "tiny" or "base"

[display]
# ...existing fields...
mic_color = "#ffffff"
mic_position = "bottom"    # "top" or "bottom"
loopback_color = "#00d4ff"
loopback_position = "top"  # "top" or "bottom"
```

### Updated dataclasses (`config.py`)

```python
@dataclass
class TranscriptionConfig:
    mic_model: str = "base"
    loopback_model: str = "base"
    language: str = "en"
    device: str = "cpu"

@dataclass
class DisplayConfig:
    lines: int = 3
    port: int = 8765
    font_family: str = "Arial"
    font_size: int = 36
    font_color: str = "#ffffff"
    bg_color: str = "#000000"
    bg_opacity: float = 0.75
    max_chars_per_line: int = 80
    fade_duration: float = 0.0
    mic_color: str = "#ffffff"
    mic_position: str = "bottom"
    loopback_color: str = "#00d4ff"
    loopback_position: str = "top"
```

### Migration

Existing `config.toml` files with the old `transcription.model` field will have it silently ignored — `mic_model` and `loopback_model` both default to `"base"`, matching the previous default.

### Validation rules

| Field | Rule |
|---|---|
| `mic_model` | `"tiny"` or `"base"` |
| `loopback_model` | `"tiny"` or `"base"` |
| `mic_color` | valid CSS hex color (#rrggbb) |
| `loopback_color` | valid CSS hex color (#rrggbb) |
| `mic_position` | `"top"` or `"bottom"` |
| `loopback_position` | `"top"` or `"bottom"` |

---

## Architecture Changes

### Pipeline — `main.py`

**Single-source mode** (`microphone` or `loopback`): unchanged — one audio queue, one transcription thread, one buffer. The transcription thread is passed `source="mic"` or `source="loopback"` respectively.

**Dual-source mode** (`both`): two separate audio queues, two transcription threads, two buffers. A RAM warning is printed at startup:

```
Warning: dual-source mode loads two Whisper models. Consider using "tiny" for
one or both sources if you experience high memory usage.
```

### `transcriber.py`

`start_transcription` gains one new parameter:

```python
def start_transcription(
    audio_queue: queue.Queue,
    subtitle_queue: queue.Queue,
    subtitle_buffer: SubtitleBuffer,
    config: AppConfig,
    stop_event: threading.Event,
    source: str = "mic",   # "mic" or "loopback"
) -> None:
```

The model loaded is `config.transcription.mic_model` when `source="mic"`, and `config.transcription.loopback_model` when `source="loopback"`.

All subtitle queue messages include the `source` field:

```json
{ "type": "subtitle", "source": "mic", "lines": [...], "translated_lines": [...] }
{ "type": "subtitle", "source": "loopback", "lines": [...], "translated_lines": [...] }
```

### `server.py`

`_display_config_message` extended to include the four new display fields:

```json
{
  "type": "config",
  "display": {
    "mic_color": "#ffffff",
    "mic_position": "bottom",
    "loopback_color": "#00d4ff",
    "loopback_position": "top",
    "font_family": "Arial",
    "font_size": 36,
    "font_color": "#ffffff",
    "bg_color": "#000000",
    "bg_opacity": 0.75,
    "fade_duration": 0.0
  }
}
```

No other server changes required.

### `overlay.html`

Two subtitle containers replace the single container:

```html
<div id="subtitles-mic"></div>
<div id="subtitles-loopback"></div>
```

Each is `position: fixed; left: 0; right: 0; width: 100%`. Position (top/bottom) and color are applied dynamically from the `type: "config"` message via CSS variables:

- `--mic-color` → text color for mic container
- `--loopback-color` → text color for loopback container
- `--mic-position` → `top: 0` or `bottom: 0`
- `--loopback-position` → `top: 0` or `bottom: 0`

Incoming `type: "subtitle"` messages route to `#subtitles-mic` or `#subtitles-loopback` based on `source`. In single-source mode, the unused container is hidden (`display: none`).

### `settings.html`

The Transcription section replaces the single model dropdown with two:

- **Mic model** — dropdown: `tiny`, `base`
- **Loopback model** — dropdown: `tiny`, `base`

A RAM warning is shown dynamically when audio mode is set to `both`:

```
Running two models simultaneously. Use "tiny" for one or both sources if
memory usage is high.
```

The Display section gains four new fields:

- **Mic color** — color input
- **Mic position** — dropdown: `top`, `bottom`
- **Loopback color** — color input
- **Loopback position** — dropdown: `top`, `bottom`

---

## Data Flow

```
[mode = "both"]

Mic capture → mic_audio_queue
  → transcription thread (mic_model, source="mic")
    → subtitle_queue: { type, source: "mic", lines, translated_lines }

Loopback capture → loopback_audio_queue
  → transcription thread (loopback_model, source="loopback")
    → subtitle_queue: { type, source: "loopback", lines, translated_lines }

subtitle_queue → WebSocket broadcast → overlay.html
  → routes to #subtitles-mic or #subtitles-loopback by source
```

---

## File Changes Summary

| File | Change |
|---|---|
| `config.py` | Replace `model` with `mic_model`/`loopback_model`; add display position/color fields; update validation |
| `transcriber.py` | Add `source` parameter; load model by source; tag queue messages with source |
| `main.py` | Dual-queue/thread setup for `both` mode; RAM warning; update transcription thread args |
| `server.py` | Extend `_display_config_message` with new display fields |
| `overlay.html` | Two containers; per-source color/position CSS variables; route messages by source |
| `settings.html` | Split model dropdown into two; RAM warning; add color/position fields for each source |
