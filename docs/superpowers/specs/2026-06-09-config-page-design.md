# Subtitle Everything — Config Page Design Spec
**Date:** 2026-06-09
**Status:** Approved

---

## Overview

Extend Subtitle Everything with a web-based configuration page and a JSON config API. Users can edit all settings (font, color, line length, fade duration, translation) through a browser form at `http://localhost:8765/settings`. Display changes apply live to the overlay without a restart. Audio, model, and translation-backend changes are saved to `config.toml` and take effect on the next restart.

---

## Goals

- Expose font family, font size, text color, background color/opacity, max chars per line, and fade duration as configurable settings
- Add LibreTranslate translation support with source/target language selection
- Add dual-language mode (original + translated subtitles shown simultaneously)
- Provide a web settings page so users never need to hand-edit `config.toml`
- Live-reload display settings to the overlay via WebSocket without restart

---

## New Config Fields

### `config.toml` additions

```toml
[display]
lines = 3
port = 8765
font_family = "Arial"
font_size = 36
font_color = "#ffffff"
bg_color = "#000000"
bg_opacity = 0.75
max_chars_per_line = 80
fade_duration = 0.0        # seconds a line stays visible before fading; 0 = no fade

[translation]
enabled = false
url = "http://localhost:5000"   # LibreTranslate server address
source_lang = "en"
target_lang = "es"
dual_language = false           # show original + translated simultaneously
```

### Updated dataclasses (`config.py`)

```python
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

@dataclass
class TranslationConfig:
    enabled: bool = False
    url: str = "http://localhost:5000"
    source_lang: str = "en"
    target_lang: str = "es"
    dual_language: bool = False
```

### Validation rules

| Field | Rule |
|---|---|
| `font_size` | >= 8 |
| `bg_opacity` | 0.0 – 1.0 |
| `max_chars_per_line` | >= 20 |
| `fade_duration` | >= 0.0 |
| `font_color`, `bg_color` | valid CSS hex color (#rrggbb) |

---

## Architecture Changes

### New routes in `server.py`

| Route | Method | Description |
|---|---|---|
| `/settings` | GET | Serves `settings.html` |
| `/api/config` | GET | Returns full current config as JSON |
| `/api/config` | POST | Validates JSON body, writes `config.toml`, mutates in-memory config, broadcasts display config via WebSocket. Returns saved config + `"requires_restart": true` if audio/model/translation-backend fields changed. |

The server receives the `AppConfig` object from `main.py` and mutates it in-place on POST. No module globals. No restart needed for display changes.

### WebSocket protocol

Messages gain a `type` field:

**Subtitle update:**
```json
{
  "type": "subtitle",
  "lines": ["transcribed text..."],
  "translated_lines": ["translated text..."]
}
```
`translated_lines` is `[]` when translation is disabled or `dual_language` is false. When translation is enabled and `dual_language` is false, `lines` contains the translated text (replacing the original). When `dual_language` is true, `lines` contains the original and `translated_lines` contains the translation.

**Config update (broadcast on POST /api/config and on new connection):**
```json
{
  "type": "config",
  "display": {
    "font_family": "Arial",
    "font_size": 36,
    "font_color": "#ffffff",
    "bg_color": "#000000",
    "bg_opacity": 0.75,
    "fade_duration": 0.0
  }
}
```

On each new WebSocket connection, the server immediately sends a `type: "config"` message before any subtitles arrive.

---

## Components

### `translator.py` (new)

```python
def translate(text: str, config: TranslationConfig) -> str | None
```

POSTs to the LibreTranslate `/translate` endpoint. Returns translated string on success, `None` on any error. Translation failures are silent — subtitles keep working even if LibreTranslate is unreachable.

### `transcriber.py` (modified)

After each Whisper segment, if `config.translation.enabled` is true, calls `translator.translate()`. Packages both original and translated text into the subtitle queue message. If `dual_language` is false, `lines` is set to the translated text (translation replaces the original). If `dual_language` is true, `lines` holds the original and `translated_lines` holds the translation.

`max_chars_per_line` enforcement: long segments are split into multiple lines at word boundaries before being pushed to the buffer.

### `server.py` (modified)

- Receives `AppConfig` reference from `main.py`
- Adds `/settings`, `GET /api/config`, `POST /api/config` routes
- On POST: validates, writes `config.toml`, mutates config in-place, broadcasts `type: "config"` to all WebSocket clients
- On new WebSocket connection: sends current `type: "config"` message immediately

### `overlay.html` (modified)

- All styling driven by CSS custom properties (`--font-family`, `--font-size`, `--font-color`, `--bg-color`, `--bg-opacity`, `--fade-duration`)
- `type: "config"` handler updates CSS variables on `document.documentElement.style` live
- `fade_duration > 0`: lines gain a CSS `opacity` transition; a `setTimeout` triggers fade-out after `fade_duration` seconds
- `type: "subtitle"` handler renders `lines` as before; if `translated_lines` is non-empty, renders them below in a second block at 80% text opacity

### `settings.html` (new)

Plain HTML page with four sections:

| Section | Fields | Notes |
|---|---|---|
| Display | font family, font size, text color, bg color, bg opacity, lines, max chars/line, fade duration | All live-reload |
| Translation | enabled, LibreTranslate URL, source lang, target lang, dual language | URL/langs require restart |
| Audio | mode, mic device, loopback device | Labelled "requires restart" |
| Transcription | model, language, device | Labelled "requires restart" |

Single Save button POSTs to `/api/config`. Status line shows "Saved" or validation error. If response contains `requires_restart: true`, shows "Saved — restart required for some changes."

---

## Data Flow (updated)

```
Audio capture → audio_queue
  → transcriber: Whisper inference
    → (if translation.enabled) translator: LibreTranslate HTTP call
    → max_chars_per_line split → buffer.push()
    → subtitle_queue: { type, lines, translated_lines }
      → WebSocket broadcast to overlay.html

POST /api/config
  → validate → write config.toml → mutate AppConfig in-place
  → broadcast { type: "config", display: {...} } to overlay.html
```

---

## File Changes Summary

| File | Change |
|---|---|
| `config.py` | Add display and translation fields to dataclasses + DEFAULT_CONFIG + validation |
| `server.py` | Add `/settings`, `/api/config` GET/POST routes; accept AppConfig reference; send config on WS connect |
| `transcriber.py` | Call translator if enabled; enforce max_chars_per_line; update queue message format |
| `main.py` | Pass AppConfig to server; update subtitle_queue message format |
| `overlay.html` | CSS variables; live config handler; fade logic; dual-language rendering |
| `translator.py` | New file — LibreTranslate HTTP client |
| `settings.html` | New file — settings form UI |
