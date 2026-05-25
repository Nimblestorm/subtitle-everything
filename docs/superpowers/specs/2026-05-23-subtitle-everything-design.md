# Subtitle Everything — Design Spec
**Date:** 2026-05-23  
**Status:** Approved

---

## Overview

A single Python application that transcribes live audio (microphone, system loopback, or both) using faster-whisper and serves real-time subtitles to OBS via a Browser Source. The overlay is a local HTML page styled for stream readability. Everything is configurable via `config.toml`.

---

## Goals

- Low-latency subtitles (~1-3 seconds end-to-end) on `base` model
- OBS-ready Browser Source overlay at `http://localhost:8765`
- Configurable audio source: microphone, system loopback, or mixed
- Configurable language (default: English), model size, line count, port
- Graceful first-run experience (auto-generates `config.toml`, downloads model if needed)
- Extensible for future LibreTranslate translation support

---

## Architecture

Single Python process. Four responsibilities wired together in `main.py`:

```
Thread 1: Audio Capture
  └─ reads audio chunks → audio_queue

Thread 2: Transcription
  └─ audio_queue → faster-whisper → subtitle_queue

Async Event Loop (main thread): WebSocket Server
  └─ serves overlay.html on GET /
  └─ accepts WebSocket connections from OBS
  └─ subtitle_queue → broadcast JSON to all clients
```

---

## Components

### `audio.py`
Captures audio using `sounddevice` (microphone) and/or `pyaudiowpatch` (WASAPI loopback for system audio). Accumulates a rolling ~3-second buffer and feeds it into `audio_queue` as numpy arrays.

**Modes:**
- `microphone` — Windows default input device (or configured device index)
- `loopback` — Windows default output device via WASAPI loopback
- `both` — captures both, mixes (averages) the streams before queuing

### `transcriber.py`
Loads a faster-whisper model on startup. Runs in a dedicated thread, pulling audio chunks from `audio_queue` and producing text segments into `subtitle_queue`. Language and model size are read from config.

### `buffer.py`
Maintains a rolling list of the last N subtitle lines (N from config, default 3). Provides a `push(text)` method that appends and trims, and a `get_lines()` method that returns the current window.

### `server.py`
Uses `aiohttp` to:
- Serve `overlay.html` at `GET /`
- Accept WebSocket connections at `ws://localhost:{port}/ws`
- Watch `subtitle_queue` in the async loop and broadcast updates to all connected clients as JSON: `{ "lines": ["...", "..."] }`

### `config.py`
Loads `config.toml` using `tomllib` (stdlib in Python 3.11+) or `tomli`. If no `config.toml` exists, writes a default one and logs a notice.

### `main.py`
Entry point. Loads config, prints startup summary, starts audio and transcription threads, runs the async event loop for the WebSocket server. Handles `KeyboardInterrupt` for clean shutdown.

### `overlay.html`
Static HTML file served by `server.py`. Vanilla HTML/CSS/JS — no framework. On load, connects to the WebSocket and re-renders the subtitle lines on every message. Styled for OBS: large white text, dark semi-transparent background pill, centered at the bottom of the frame.

---

## Configuration (`config.toml`)

```toml
[audio]
mode = "microphone"        # "microphone" | "loopback" | "both"
mic_device = "default"     # device index or "default"
loopback_device = "default"

[transcription]
model = "base"             # "tiny" | "base" | "small" | "medium" | "large-v3"
language = "en"            # whisper language code, or "auto" for auto-detect
device = "cpu"             # "cpu" | "cuda"

[display]
lines = 3                  # number of subtitle lines shown simultaneously
port = 8765

[translation]
enabled = false            # reserved for future LibreTranslate integration
```

---

## Data Flow Detail

1. Audio capture thread fills a rolling numpy buffer (~3 seconds of audio at 16kHz mono).
2. Every ~3 seconds, the buffer is copied and put into `audio_queue`.
3. Transcription thread picks up the chunk, runs `faster_whisper.WhisperModel.transcribe()`, extracts segment text.
4. Each segment is pushed to `buffer.py` and the updated line list is put into `subtitle_queue`.
5. Async loop reads `subtitle_queue` and broadcasts `{ "lines": [...] }` to all connected WebSocket clients.
6. OBS browser source renders the updated lines.

---

## Error Handling

| Scenario | Behavior |
|---|---|
| CUDA configured but unavailable | Falls back to CPU with a warning |
| Default mic/loopback device not found | Prints available devices, exits cleanly |
| Model not cached | Downloads on first run, logs progress |
| No `config.toml` | Writes default config, continues |
| OBS browser source reconnects | Client tracked in a set; connect/disconnect handled gracefully |
| `Ctrl+C` | Stops audio capture, drains queues, closes WebSocket connections |

---

## Startup Output

```
[Subtitle Everything]
  Model:    base (cpu)
  Audio:    microphone (default input)
  Language: en
  Overlay:  http://localhost:8765

Add this URL as a Browser Source in OBS.
Press Ctrl+C to stop.
```

---

## Dependencies

| Package | Purpose |
|---|---|
| `faster-whisper` | Speech-to-text transcription |
| `sounddevice` | Microphone audio capture |
| `pyaudiowpatch` | WASAPI loopback (system audio) |
| `numpy` | Audio buffer manipulation |
| `aiohttp` | HTTP server + WebSocket server for serving overlay.html and subtitle updates |
| `tomli` | TOML config parsing (if Python < 3.11) |

---

## Future: Translation

When LibreTranslate support is added:
- `[translation]` section in config gains `url`, `source_lang`, `target_lang` fields
- A `translator.py` component sits between `transcriber.py` and `buffer.py`
- Translated text is appended below the transcribed line in the overlay

---

## File Structure

```
Subtitle Everything/
├── main.py
├── config.py
├── audio.py
├── transcriber.py
├── buffer.py
├── server.py
├── overlay.html
├── config.toml          # auto-generated on first run
├── requirements.txt
└── docs/
    └── superpowers/
        └── specs/
            └── 2026-05-23-subtitle-everything-design.md
```
