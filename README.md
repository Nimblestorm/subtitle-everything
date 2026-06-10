# Subtitle Everything

Real-time subtitles for OBS. Captures microphone or system audio (or both simultaneously), transcribes it with [faster-whisper](https://github.com/guillaumekynast/faster-whisper), and serves an overlay you add as a Browser Source.

---

## Requirements

- Python 3.11+
- Windows (loopback capture uses WASAPI)
- A CUDA-capable GPU is optional but speeds up transcription significantly

---

## Installation

```bash
pip install -r requirements.txt
```

---

## Usage

```bash
python main.py
```

On first run, a `config.toml` is created with defaults. The overlay is served at:

```
http://localhost:8765
```

Add that URL as a **Browser Source** in OBS (recommended size: 1920×200, positioned at the bottom of your scene).

Open `http://localhost:8765/settings` in a browser to configure everything without editing files.

---

## Configuration

Settings are saved to `config.toml` and can be edited there or through the settings page at `/settings`.

### Audio

| Setting | Default | Notes |
|---|---|---|
| `audio.mode` | `microphone` | `microphone`, `loopback`, or `both` |
| `audio.mic_device` | `default` | Device index or `"default"` |
| `audio.loopback_device` | `default` | Device index or `"default"` |

### Transcription

| Setting | Default | Notes |
|---|---|---|
| `transcription.mic_model` | `base` | Whisper model for microphone: `tiny` or `base` |
| `transcription.loopback_model` | `base` | Whisper model for loopback: `tiny` or `base` |
| `transcription.language` | `en` | BCP-47 language code, or `auto` for detection |
| `transcription.device` | `cpu` | `cpu` or `cuda` |

> **Note:** When `audio.mode = "both"`, two Whisper models load simultaneously. Use `tiny` for one or both sources if memory usage is a concern.

### Display

| Setting | Default | Notes |
|---|---|---|
| `display.font_family` | `Arial` | Any font available in OBS |
| `display.font_size` | `36` | Minimum 8 |
| `display.font_color` | `#ffffff` | CSS hex color |
| `display.bg_color` | `#000000` | CSS hex color |
| `display.bg_opacity` | `0.75` | 0.0 – 1.0 |
| `display.max_chars_per_line` | `80` | Long segments wrap at word boundaries |
| `display.fade_duration` | `0.0` | Seconds before a line fades out; 0 = no fade |
| `display.mic_color` | `#ffffff` | Subtitle text color for microphone source |
| `display.mic_position` | `bottom` | `top` or `bottom` |
| `display.loopback_color` | `#00d4ff` | Subtitle text color for loopback source |
| `display.loopback_position` | `top` | `top` or `bottom` |

Display changes (font, color, opacity, fade) apply live to the overlay without a restart. Audio, model, and language changes require a restart.

### Dual-source mode

When `audio.mode = "both"`, mic and loopback audio are transcribed by independent pipelines and displayed in separate color-coded containers. By default, mic subtitles appear at the bottom (white) and loopback subtitles at the top (cyan). Both color and position are configurable per-source from the settings page.

---

## Translation (optional)

Translation is disabled by default. To enable it, you need a running [LibreTranslate](https://github.com/LibreTranslate/LibreTranslate) instance:

```bash
docker run -p 5000:5000 libretranslate/libretranslate
```

Then in the settings page at `/settings`, enable translation and set your source and target languages. If LibreTranslate is unreachable, subtitles continue working in the original language.

**Dual-language mode** shows the original and translated subtitles simultaneously.

---

## Development

```bash
pip install -r requirements.txt
pytest
```
