# Subtitle Everything

Real-time subtitles for OBS. Captures microphone or system audio, transcribes it with [faster-whisper](https://github.com/guillaumekynast/faster-whisper), and serves an overlay you add as a Browser Source.

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

| Setting | Default | Notes |
|---|---|---|
| `audio.mode` | `microphone` | `microphone`, `loopback`, or `both` |
| `transcription.model` | `base` | Whisper model size: `tiny`, `base`, `small`, `medium`, `large` |
| `transcription.device` | `cpu` | `cpu` or `cuda` |
| `display.font_family` | `Arial` | Any font available in OBS |
| `display.font_size` | `36` | Minimum 8 |
| `display.font_color` | `#ffffff` | CSS hex color |
| `display.bg_color` | `#000000` | CSS hex color |
| `display.bg_opacity` | `0.75` | 0.0 – 1.0 |
| `display.max_chars_per_line` | `80` | Long segments wrap at word boundaries |
| `display.fade_duration` | `0.0` | Seconds before a line fades out; 0 = no fade |

Display changes (font, color, opacity, fade) apply live to the overlay without a restart. Audio, model, and language changes require a restart.

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
