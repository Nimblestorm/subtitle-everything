# Config Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add font/color/line/translation settings to config.toml, expose them via a JSON API, and serve a web settings page at `/settings` with live display hot-reload over WebSocket.

**Architecture:** `config.py` gains new fields and a `write_config` helper; `server.py` gets `/settings`, `GET /api/config`, and `POST /api/config` routes — POST mutates the in-memory `AppConfig`, writes `config.toml`, and broadcasts a `type:"config"` WebSocket message so `overlay.html` updates live. `transcriber.py` changes signature to accept `AppConfig`, splits long lines, and calls a new `translator.py` for LibreTranslate.

**Tech Stack:** Python 3.10+, aiohttp, faster-whisper, requests (new), tomllib/tomli, pytest, pytest-asyncio

---

## File Map

| File | Change |
|---|---|
| `config.py` | Add display/translation fields; extract `_validate_config`; add `write_config` |
| `translator.py` | New — LibreTranslate HTTP client |
| `transcriber.py` | New signature `(…, config: AppConfig, …)`; `split_to_lines`; translation call; new queue format |
| `settings.html` | New — settings form |
| `server.py` | Accept `AppConfig`; add `/settings`, `/api/config` GET/POST; send config on WS connect |
| `overlay.html` | CSS variables; live config handler; fade; dual-language rendering |
| `main.py` | Update `start_transcription` and `create_app` call sites |
| `requirements.txt` | Add `requests>=2.28.0` |
| `tests/test_config.py` | Tests for new fields, `write_config`, new validation |
| `tests/test_translator.py` | New — tests for translate() |
| `tests/test_transcriber.py` | Update for new signature/format; add split_to_lines tests |
| `tests/test_server.py` | Update for new signature; add API route tests |

---

## Task 1: Extend config.py

**Files:**
- Modify: `config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write failing tests for new fields and write_config**

Add to `tests/test_config.py`:

```python
def test_display_config_new_defaults(tmp_path):
    cfg = load_config(str(tmp_path / "config.toml"))
    assert cfg.display.font_family == "Arial"
    assert cfg.display.font_size == 36
    assert cfg.display.font_color == "#ffffff"
    assert cfg.display.bg_color == "#000000"
    assert cfg.display.bg_opacity == 0.75
    assert cfg.display.max_chars_per_line == 80
    assert cfg.display.fade_duration == 0.0


def test_translation_config_new_defaults(tmp_path):
    cfg = load_config(str(tmp_path / "config.toml"))
    assert cfg.translation.url == "http://localhost:5000"
    assert cfg.translation.source_lang == "en"
    assert cfg.translation.target_lang == "es"
    assert cfg.translation.dual_language is False


def test_load_config_raises_on_invalid_font_size(tmp_path):
    f = tmp_path / "config.toml"
    f.write_text("[display]\nfont_size = 4\n", encoding="utf-8")
    with pytest.raises(ValueError, match="font_size"):
        load_config(str(f))


def test_load_config_raises_on_invalid_bg_opacity(tmp_path):
    f = tmp_path / "config.toml"
    f.write_text("[display]\nbg_opacity = 1.5\n", encoding="utf-8")
    with pytest.raises(ValueError, match="bg_opacity"):
        load_config(str(f))


def test_load_config_raises_on_invalid_font_color(tmp_path):
    f = tmp_path / "config.toml"
    f.write_text('[display]\nfont_color = "red"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="font_color"):
        load_config(str(f))


def test_load_config_raises_on_invalid_max_chars(tmp_path):
    f = tmp_path / "config.toml"
    f.write_text("[display]\nmax_chars_per_line = 5\n", encoding="utf-8")
    with pytest.raises(ValueError, match="max_chars_per_line"):
        load_config(str(f))


def test_write_config_roundtrip(tmp_path):
    from config import write_config, AppConfig, DisplayConfig, TranslationConfig
    cfg = AppConfig()
    cfg.display.font_size = 48
    cfg.display.font_color = "#ffff00"
    cfg.translation.target_lang = "fr"
    p = str(tmp_path / "out.toml")
    write_config(cfg, p)
    loaded = load_config(p)
    assert loaded.display.font_size == 48
    assert loaded.display.font_color == "#ffff00"
    assert loaded.translation.target_lang == "fr"
```

- [ ] **Step 2: Run tests to confirm they fail**

```
pytest tests/test_config.py -v -k "new_defaults or invalid_font or invalid_bg or invalid_max or write_config"
```

Expected: FAIL (fields don't exist yet)

- [ ] **Step 3: Replace config.py with updated version**

```python
import re
import sys
from dataclasses import dataclass, field, fields as dc_fields
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

DEFAULT_CONFIG = """\
[audio]
mode = "microphone"
mic_device = "default"
loopback_device = "default"

[transcription]
model = "base"
language = "en"
device = "cpu"

[display]
lines = 3
port = 8765
font_family = "Arial"
font_size = 36
font_color = "#ffffff"
bg_color = "#000000"
bg_opacity = 0.75
max_chars_per_line = 80
fade_duration = 0.0

[translation]
enabled = false
url = "http://localhost:5000"
source_lang = "en"
target_lang = "es"
dual_language = false
"""

_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


@dataclass
class AudioConfig:
    mode: str = "microphone"
    mic_device: str = "default"
    loopback_device: str = "default"


@dataclass
class TranscriptionConfig:
    model: str = "base"
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


@dataclass
class TranslationConfig:
    enabled: bool = False
    url: str = "http://localhost:5000"
    source_lang: str = "en"
    target_lang: str = "es"
    dual_language: bool = False


@dataclass
class AppConfig:
    audio: AudioConfig = field(default_factory=AudioConfig)
    transcription: TranscriptionConfig = field(default_factory=TranscriptionConfig)
    display: DisplayConfig = field(default_factory=DisplayConfig)
    translation: TranslationConfig = field(default_factory=TranslationConfig)


def _build(cls, data: dict):
    known = {f.name for f in dc_fields(cls)}
    return cls(**{k: v for k, v in data.items() if k in known})


def _validate_config(cfg: "AppConfig") -> None:
    if not isinstance(cfg.display.port, int):
        raise ValueError(f"[display] port must be an integer, got {cfg.display.port!r}")
    if not isinstance(cfg.display.lines, int):
        raise ValueError(f"[display] lines must be an integer, got {cfg.display.lines!r}")
    if not isinstance(cfg.translation.enabled, bool):
        raise ValueError(f"[translation] enabled must be a boolean, got {cfg.translation.enabled!r}")
    if cfg.display.lines < 1:
        raise ValueError(f"[display] lines must be >= 1, got {cfg.display.lines!r}")
    if cfg.display.font_size < 8:
        raise ValueError(f"[display] font_size must be >= 8, got {cfg.display.font_size!r}")
    if not (0.0 <= cfg.display.bg_opacity <= 1.0):
        raise ValueError(f"[display] bg_opacity must be 0.0–1.0, got {cfg.display.bg_opacity!r}")
    if cfg.display.max_chars_per_line < 20:
        raise ValueError(f"[display] max_chars_per_line must be >= 20, got {cfg.display.max_chars_per_line!r}")
    if cfg.display.fade_duration < 0.0:
        raise ValueError(f"[display] fade_duration must be >= 0.0, got {cfg.display.fade_duration!r}")
    if not _HEX_COLOR_RE.match(cfg.display.font_color):
        raise ValueError(f"[display] font_color must be #rrggbb hex, got {cfg.display.font_color!r}")
    if not _HEX_COLOR_RE.match(cfg.display.bg_color):
        raise ValueError(f"[display] bg_color must be #rrggbb hex, got {cfg.display.bg_color!r}")


def write_config(config: "AppConfig", path: str = "config.toml") -> None:
    a, tr, d, t = config.audio, config.transcription, config.display, config.translation
    toml = (
        f'[audio]\n'
        f'mode = "{a.mode}"\n'
        f'mic_device = "{a.mic_device}"\n'
        f'loopback_device = "{a.loopback_device}"\n'
        f'\n'
        f'[transcription]\n'
        f'model = "{tr.model}"\n'
        f'language = "{tr.language}"\n'
        f'device = "{tr.device}"\n'
        f'\n'
        f'[display]\n'
        f'lines = {d.lines}\n'
        f'port = {d.port}\n'
        f'font_family = "{d.font_family}"\n'
        f'font_size = {d.font_size}\n'
        f'font_color = "{d.font_color}"\n'
        f'bg_color = "{d.bg_color}"\n'
        f'bg_opacity = {d.bg_opacity}\n'
        f'max_chars_per_line = {d.max_chars_per_line}\n'
        f'fade_duration = {d.fade_duration}\n'
        f'\n'
        f'[translation]\n'
        f'enabled = {"true" if t.enabled else "false"}\n'
        f'url = "{t.url}"\n'
        f'source_lang = "{t.source_lang}"\n'
        f'target_lang = "{t.target_lang}"\n'
        f'dual_language = {"true" if t.dual_language else "false"}\n'
    )
    Path(path).write_text(toml, encoding="utf-8")


def load_config(path: str = "config.toml") -> "AppConfig":
    config_path = Path(path)
    if not config_path.exists():
        config_path.write_text(DEFAULT_CONFIG, encoding="utf-8")
        print(f"Created default config at {config_path}")

    with open(config_path, "rb") as f:
        data = tomllib.load(f)

    cfg = AppConfig(
        audio=_build(AudioConfig, data.get("audio", {})),
        transcription=_build(TranscriptionConfig, data.get("transcription", {})),
        display=_build(DisplayConfig, data.get("display", {})),
        translation=_build(TranslationConfig, data.get("translation", {})),
    )

    _validate_config(cfg)
    return cfg
```

- [ ] **Step 4: Run tests to confirm they pass**

```
pytest tests/test_config.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```
git add config.py tests/test_config.py
git commit -m "feat: extend config with display styling and translation fields"
```

---

## Task 2: Create translator.py

**Files:**
- Create: `translator.py`
- Create: `tests/test_translator.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_translator.py`:

```python
from unittest.mock import patch, MagicMock
from config import TranslationConfig


def _cfg(**kwargs):
    defaults = dict(url="http://localhost:5000", source_lang="en", target_lang="es")
    return TranslationConfig(**{**defaults, **kwargs})


def test_translate_returns_translated_text():
    from translator import translate
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"translatedText": "Hola mundo"}
    mock_resp.raise_for_status = MagicMock()
    with patch("requests.post", return_value=mock_resp) as mock_post:
        result = translate("Hello world", _cfg())
    assert result == "Hola mundo"
    mock_post.assert_called_once_with(
        "http://localhost:5000/translate",
        json={"q": "Hello world", "source": "en", "target": "es", "format": "text"},
        timeout=5.0,
    )


def test_translate_returns_none_on_network_error():
    from translator import translate
    with patch("requests.post", side_effect=ConnectionError("down")):
        result = translate("Hello", _cfg())
    assert result is None


def test_translate_returns_none_on_bad_response():
    from translator import translate
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = Exception("500")
    with patch("requests.post", return_value=mock_resp):
        result = translate("Hello", _cfg())
    assert result is None


def test_translate_returns_none_on_missing_key():
    from translator import translate
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"unexpected": "key"}
    with patch("requests.post", return_value=mock_resp):
        result = translate("Hello", _cfg())
    assert result is None
```

- [ ] **Step 2: Run to confirm failure**

```
pytest tests/test_translator.py -v
```

Expected: FAIL (translator.py doesn't exist)

- [ ] **Step 3: Create translator.py**

```python
import requests
from config import TranslationConfig


def translate(text: str, config: TranslationConfig) -> str | None:
    try:
        response = requests.post(
            f"{config.url}/translate",
            json={
                "q": text,
                "source": config.source_lang,
                "target": config.target_lang,
                "format": "text",
            },
            timeout=5.0,
        )
        response.raise_for_status()
        return response.json()["translatedText"]
    except Exception:
        return None
```

- [ ] **Step 4: Run tests to confirm pass**

```
pytest tests/test_translator.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```
git add translator.py tests/test_translator.py
git commit -m "feat: add LibreTranslate translator module"
```

---

## Task 3: Update transcriber.py

**Files:**
- Modify: `transcriber.py`
- Modify: `tests/test_transcriber.py`

- [ ] **Step 1: Write failing tests for split_to_lines and new format**

Add to `tests/test_transcriber.py` (keep existing tests, update them, add new ones):

```python
def test_split_to_lines_short_text():
    from transcriber import split_to_lines
    assert split_to_lines("hello", 80) == ["hello"]


def test_split_to_lines_exact_limit():
    from transcriber import split_to_lines
    text = "a" * 80
    assert split_to_lines(text, 80) == [text]


def test_split_to_lines_wraps_at_word_boundary():
    from transcriber import split_to_lines
    result = split_to_lines("one two three four five", 12)
    assert all(len(line) <= 12 for line in result)
    assert " ".join(result).replace("  ", " ") == "one two three four five"


def test_split_to_lines_single_long_word():
    from transcriber import split_to_lines
    # A single word longer than max_chars stays as-is
    result = split_to_lines("superlongword", 5)
    assert result == ["superlongword"]
```

Also update the three existing tests to use new `AppConfig` signature and new message format:

```python
def test_transcriber_pushes_text_to_subtitle_queue():
    from transcriber import start_transcription
    from buffer import SubtitleBuffer
    from config import AppConfig

    audio_queue = queue.Queue()
    subtitle_queue = queue.Queue()
    stop_event = threading.Event()
    buf = SubtitleBuffer(max_lines=3)
    config = AppConfig()

    audio_queue.put(np.zeros(48000, dtype=np.float32))
    mock_model = _make_mock_model(["hello world"])

    with patch("transcriber.WhisperModel", lambda *a, **kw: mock_model):
        t = threading.Thread(
            target=start_transcription,
            args=(audio_queue, subtitle_queue, buf, config, stop_event),
            daemon=True,
        )
        t.start()
        result = subtitle_queue.get(timeout=3.0)
        stop_event.set()
        t.join(timeout=2)

    assert result["type"] == "subtitle"
    assert result["lines"] == ["hello world"]
    assert result["translated_lines"] == []


def test_transcriber_skips_empty_segments():
    from transcriber import start_transcription
    from buffer import SubtitleBuffer
    from config import AppConfig

    audio_queue = queue.Queue()
    subtitle_queue = queue.Queue()
    stop_event = threading.Event()
    buf = SubtitleBuffer(max_lines=3)
    config = AppConfig()

    audio_queue.put(np.zeros(48000, dtype=np.float32))
    mock_model = _make_mock_model(["   ", ""])

    with patch("transcriber.WhisperModel", lambda *a, **kw: mock_model):
        t = threading.Thread(
            target=start_transcription,
            args=(audio_queue, subtitle_queue, buf, config, stop_event),
            daemon=True,
        )
        t.start()
        stop_event.set()
        t.join(timeout=2)

    assert subtitle_queue.empty()


def test_transcriber_uses_auto_language():
    from transcriber import start_transcription
    from buffer import SubtitleBuffer
    from config import AppConfig, TranscriptionConfig

    audio_queue = queue.Queue()
    subtitle_queue = queue.Queue()
    stop_event = threading.Event()
    buf = SubtitleBuffer()
    config = AppConfig()
    config.transcription = TranscriptionConfig(language="auto")

    audio_queue.put(np.zeros(48000, dtype=np.float32))
    mock_model = _make_mock_model(["test"])

    with patch("transcriber.WhisperModel", lambda *a, **kw: mock_model):
        t = threading.Thread(
            target=start_transcription,
            args=(audio_queue, subtitle_queue, buf, config, stop_event),
            daemon=True,
        )
        t.start()
        subtitle_queue.get(timeout=3.0)
        stop_event.set()
        t.join(timeout=2)

    call_kwargs = mock_model.transcribe.call_args[1]
    assert call_kwargs.get("language") is None
```

- [ ] **Step 2: Run to confirm failures**

```
pytest tests/test_transcriber.py -v
```

Expected: FAIL (split_to_lines not defined, signature mismatch)

- [ ] **Step 3: Replace transcriber.py**

```python
import queue
import threading
from typing import Optional

import numpy as np
from faster_whisper import WhisperModel

from buffer import SubtitleBuffer
from config import AppConfig
from translator import translate


def split_to_lines(text: str, max_chars: int) -> list[str]:
    if max_chars <= 0 or len(text) <= max_chars:
        return [text]
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        if current and len(current) + 1 + len(word) > max_chars:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip() if current else word
    if current:
        lines.append(current)
    return lines if lines else [text]


def start_transcription(
    audio_queue: queue.Queue,
    subtitle_queue: queue.Queue,
    subtitle_buffer: SubtitleBuffer,
    config: AppConfig,
    stop_event: threading.Event,
) -> None:
    compute_type = "float16" if config.transcription.device == "cuda" else "int8"
    model = WhisperModel(
        config.transcription.model,
        device=config.transcription.device,
        compute_type=compute_type,
    )
    lang: Optional[str] = None if config.transcription.language == "auto" else config.transcription.language

    while not stop_event.is_set():
        try:
            audio_chunk: np.ndarray = audio_queue.get(timeout=0.5)
        except queue.Empty:
            continue

        segments, _ = model.transcribe(
            audio_chunk,
            language=lang,
            beam_size=1,
            vad_filter=True,
        )
        text = " ".join(seg.text.strip() for seg in segments).strip()
        if not text:
            continue

        for line in split_to_lines(text, config.display.max_chars_per_line):
            subtitle_buffer.push(line)

        original_lines = subtitle_buffer.get_lines()
        translated_lines: list[str] = []

        if config.translation.enabled:
            translated = [translate(line, config.translation) for line in original_lines]
            if config.translation.dual_language:
                translated_lines = [t if t is not None else "" for t in translated]
                lines = original_lines
            else:
                lines = [t if t is not None else orig for t, orig in zip(translated, original_lines)]
        else:
            lines = original_lines

        subtitle_queue.put({
            "type": "subtitle",
            "lines": lines,
            "translated_lines": translated_lines,
        })
```

- [ ] **Step 4: Run tests to confirm pass**

```
pytest tests/test_transcriber.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```
git add transcriber.py tests/test_transcriber.py
git commit -m "feat: update transcriber — AppConfig signature, line splitting, translation"
```

---

## Task 4: Create settings.html

**Files:**
- Create: `settings.html`

- [ ] **Step 1: Create settings.html**

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Subtitle Everything — Settings</title>
  <style>
    body { font-family: Arial, sans-serif; max-width: 620px; margin: 40px auto; padding: 0 20px; }
    h1 { font-size: 22px; }
    h2 { font-size: 16px; margin-top: 28px; border-bottom: 1px solid #ccc; padding-bottom: 4px; }
    label { display: block; margin: 10px 0 2px; font-size: 13px; font-weight: bold; }
    input[type=text], input[type=number], select {
      width: 100%; padding: 5px; box-sizing: border-box; font-size: 13px;
    }
    input[type=checkbox] { width: auto; margin-right: 6px; }
    input[type=color] { height: 34px; padding: 2px; width: 60px; }
    .row { display: flex; gap: 8px; align-items: center; }
    .row input[type=range] { flex: 1; }
    .note { font-size: 11px; color: #999; margin: 1px 0 0; }
    .restart { font-size: 11px; color: #b06000; margin: 1px 0 0; }
    button { margin-top: 28px; padding: 9px 22px; font-size: 14px; cursor: pointer; }
    #status { margin-top: 10px; font-size: 13px; min-height: 18px; }
  </style>
</head>
<body>
  <h1>Subtitle Everything — Settings</h1>

  <h2>Display</h2>
  <label>Font Family</label>
  <input type="text" id="font_family">
  <label>Font Size (px)</label>
  <input type="number" id="font_size" min="8">
  <label>Text Color</label>
  <input type="color" id="font_color">
  <label>Background Color</label>
  <input type="color" id="bg_color">
  <label>Background Opacity</label>
  <div class="row">
    <input type="range" id="bg_opacity" min="0" max="1" step="0.05">
    <span id="bg_opacity_val">0.75</span>
  </div>
  <label>Number of Lines</label>
  <input type="number" id="lines" min="1">
  <p class="restart">Requires restart</p>
  <label>Max Characters Per Line</label>
  <input type="number" id="max_chars_per_line" min="20">
  <p class="restart">Requires restart</p>
  <label>Fade Duration (seconds, 0 = no fade)</label>
  <input type="number" id="fade_duration" min="0" step="0.5">
  <label>Port</label>
  <input type="number" id="port" min="1024" max="65535">
  <p class="restart">Requires restart</p>

  <h2>Translation (LibreTranslate)</h2>
  <label><input type="checkbox" id="translation_enabled"> Enable Translation</label>
  <p class="restart">Requires restart</p>
  <label>LibreTranslate URL</label>
  <input type="text" id="translation_url">
  <p class="restart">Requires restart</p>
  <label>Source Language (e.g. en)</label>
  <input type="text" id="source_lang">
  <p class="restart">Requires restart</p>
  <label>Target Language (e.g. es)</label>
  <input type="text" id="target_lang">
  <p class="restart">Requires restart</p>
  <label><input type="checkbox" id="dual_language"> Dual Language (show original + translated)</label>
  <p class="restart">Requires restart</p>

  <h2>Audio <span class="restart">— all require restart</span></h2>
  <label>Mode</label>
  <select id="audio_mode">
    <option value="microphone">Microphone</option>
    <option value="loopback">Loopback (system audio)</option>
    <option value="both">Both</option>
  </select>
  <label>Mic Device</label>
  <input type="text" id="mic_device">
  <p class="note">Device index or "default"</p>
  <label>Loopback Device</label>
  <input type="text" id="loopback_device">
  <p class="note">Device index or "default"</p>

  <h2>Transcription <span class="restart">— all require restart</span></h2>
  <label>Model</label>
  <select id="transcription_model">
    <option value="tiny">tiny</option>
    <option value="base">base</option>
    <option value="small">small</option>
    <option value="medium">medium</option>
    <option value="large-v3">large-v3</option>
  </select>
  <label>Language (e.g. en, ja, auto)</label>
  <input type="text" id="transcription_language">
  <label>Device</label>
  <select id="transcription_device">
    <option value="cpu">cpu</option>
    <option value="cuda">cuda</option>
  </select>

  <br>
  <button onclick="save()">Save</button>
  <div id="status"></div>

  <script>
    async function load() {
      const res = await fetch('/api/config');
      if (!res.ok) { document.getElementById('status').textContent = 'Failed to load config'; return; }
      const cfg = await res.json();
      document.getElementById('font_family').value = cfg.display.font_family;
      document.getElementById('font_size').value = cfg.display.font_size;
      document.getElementById('font_color').value = cfg.display.font_color;
      document.getElementById('bg_color').value = cfg.display.bg_color;
      document.getElementById('bg_opacity').value = cfg.display.bg_opacity;
      document.getElementById('bg_opacity_val').textContent = cfg.display.bg_opacity;
      document.getElementById('lines').value = cfg.display.lines;
      document.getElementById('max_chars_per_line').value = cfg.display.max_chars_per_line;
      document.getElementById('fade_duration').value = cfg.display.fade_duration;
      document.getElementById('port').value = cfg.display.port;
      document.getElementById('translation_enabled').checked = cfg.translation.enabled;
      document.getElementById('translation_url').value = cfg.translation.url;
      document.getElementById('source_lang').value = cfg.translation.source_lang;
      document.getElementById('target_lang').value = cfg.translation.target_lang;
      document.getElementById('dual_language').checked = cfg.translation.dual_language;
      document.getElementById('audio_mode').value = cfg.audio.mode;
      document.getElementById('mic_device').value = cfg.audio.mic_device;
      document.getElementById('loopback_device').value = cfg.audio.loopback_device;
      document.getElementById('transcription_model').value = cfg.transcription.model;
      document.getElementById('transcription_language').value = cfg.transcription.language;
      document.getElementById('transcription_device').value = cfg.transcription.device;
    }

    document.getElementById('bg_opacity').addEventListener('input', e => {
      document.getElementById('bg_opacity_val').textContent = parseFloat(e.target.value).toFixed(2);
    });

    async function save() {
      const body = {
        audio: {
          mode: document.getElementById('audio_mode').value,
          mic_device: document.getElementById('mic_device').value,
          loopback_device: document.getElementById('loopback_device').value,
        },
        transcription: {
          model: document.getElementById('transcription_model').value,
          language: document.getElementById('transcription_language').value,
          device: document.getElementById('transcription_device').value,
        },
        display: {
          lines: parseInt(document.getElementById('lines').value),
          port: parseInt(document.getElementById('port').value),
          font_family: document.getElementById('font_family').value,
          font_size: parseInt(document.getElementById('font_size').value),
          font_color: document.getElementById('font_color').value,
          bg_color: document.getElementById('bg_color').value,
          bg_opacity: parseFloat(document.getElementById('bg_opacity').value),
          max_chars_per_line: parseInt(document.getElementById('max_chars_per_line').value),
          fade_duration: parseFloat(document.getElementById('fade_duration').value),
        },
        translation: {
          enabled: document.getElementById('translation_enabled').checked,
          url: document.getElementById('translation_url').value,
          source_lang: document.getElementById('source_lang').value,
          target_lang: document.getElementById('target_lang').value,
          dual_language: document.getElementById('dual_language').checked,
        },
      };
      const res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      const el = document.getElementById('status');
      if (res.ok) {
        el.style.color = '#060';
        el.textContent = data.requires_restart
          ? 'Saved — restart required for some changes'
          : 'Saved';
      } else {
        el.style.color = '#c00';
        el.textContent = `Error: ${data.error}`;
      }
    }

    load();
  </script>
</body>
</html>
```

- [ ] **Step 2: Commit**

```
git add settings.html
git commit -m "feat: add settings.html config page"
```

---

## Task 5: Update server.py

**Files:**
- Modify: `server.py`
- Modify: `tests/test_server.py`

- [ ] **Step 1: Write failing tests**

Replace `tests/test_server.py` entirely:

```python
import asyncio
import json
import os
import queue
import tempfile

import pytest
from config import AppConfig


def _make_app(config=None):
    from server import create_app
    if config is None:
        config = AppConfig()
    return create_app(queue.Queue(), config)


@pytest.mark.asyncio
async def test_get_root_serves_overlay():
    from aiohttp.test_utils import TestClient, TestServer
    app = await _make_app()
    async with TestClient(TestServer(app)) as client:
        resp = await client.get("/")
        assert resp.status == 200
        assert '<div id="subtitles">' in await resp.text()


@pytest.mark.asyncio
async def test_get_settings_serves_settings_page():
    from aiohttp.test_utils import TestClient, TestServer
    app = await _make_app()
    async with TestClient(TestServer(app)) as client:
        resp = await client.get("/settings")
        assert resp.status == 200
        assert "api/config" in await resp.text()


@pytest.mark.asyncio
async def test_get_api_config_returns_json():
    from aiohttp.test_utils import TestClient, TestServer
    config = AppConfig()
    app = await _make_app(config)
    async with TestClient(TestServer(app)) as client:
        resp = await client.get("/api/config")
        assert resp.status == 200
        data = await resp.json()
        assert data["display"]["font_family"] == "Arial"
        assert data["display"]["font_size"] == 36
        assert data["translation"]["target_lang"] == "es"


@pytest.mark.asyncio
async def test_post_api_config_updates_and_broadcasts():
    from aiohttp.test_utils import TestClient, TestServer
    config = AppConfig()
    with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as f:
        config_path = f.name
    try:
        from server import create_app
        app = await create_app(queue.Queue(), config, config_path)
        async with TestClient(TestServer(app)) as client:
            async with client.ws_connect("/ws") as ws:
                await asyncio.wait_for(ws.receive(), timeout=2.0)  # consume initial config
                resp = await client.post("/api/config", json={
                    "display": {"font_size": 48, "font_color": "#ff0000"}
                })
                assert resp.status == 200
                data = await resp.json()
                assert data["display"]["font_size"] == 48
                assert data["display"]["font_color"] == "#ff0000"
                assert data["requires_restart"] is False
                msg = await asyncio.wait_for(ws.receive(), timeout=2.0)
                cfg_msg = json.loads(msg.data)
                assert cfg_msg["type"] == "config"
                assert cfg_msg["display"]["font_size"] == 48
    finally:
        os.unlink(config_path)


@pytest.mark.asyncio
async def test_post_api_config_invalid_returns_400():
    from aiohttp.test_utils import TestClient, TestServer
    app = await _make_app()
    async with TestClient(TestServer(app)) as client:
        resp = await client.post("/api/config", json={"display": {"font_size": 2}})
        assert resp.status == 400
        data = await resp.json()
        assert "error" in data


@pytest.mark.asyncio
async def test_post_api_config_requires_restart_for_audio_change():
    from aiohttp.test_utils import TestClient, TestServer
    with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as f:
        config_path = f.name
    try:
        from server import create_app
        app = await create_app(queue.Queue(), AppConfig(), config_path)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post("/api/config", json={"audio": {"mode": "loopback"}})
            assert resp.status == 200
            data = await resp.json()
            assert data["requires_restart"] is True
    finally:
        os.unlink(config_path)


@pytest.mark.asyncio
async def test_websocket_receives_config_on_connect():
    from aiohttp.test_utils import TestClient, TestServer
    app = await _make_app()
    async with TestClient(TestServer(app)) as client:
        async with client.ws_connect("/ws") as ws:
            msg = await asyncio.wait_for(ws.receive(), timeout=2.0)
            data = json.loads(msg.data)
            assert data["type"] == "config"
            assert data["display"]["font_family"] == "Arial"


@pytest.mark.asyncio
async def test_websocket_receives_subtitle_broadcast():
    from aiohttp.test_utils import TestClient, TestServer
    subtitle_queue = queue.Queue()
    from server import create_app
    app = await create_app(subtitle_queue, AppConfig())
    async with TestClient(TestServer(app)) as client:
        async with client.ws_connect("/ws") as ws:
            await asyncio.wait_for(ws.receive(), timeout=2.0)  # config message
            subtitle_queue.put({"type": "subtitle", "lines": ["hello"], "translated_lines": []})
            msg = await asyncio.wait_for(ws.receive(), timeout=2.0)
            data = json.loads(msg.data)
            assert data["type"] == "subtitle"
            assert data["lines"] == ["hello"]


@pytest.mark.asyncio
async def test_multiple_clients_receive_broadcast():
    from aiohttp.test_utils import TestClient, TestServer
    subtitle_queue = queue.Queue()
    from server import create_app
    app = await create_app(subtitle_queue, AppConfig())
    async with TestClient(TestServer(app)) as client:
        async with client.ws_connect("/ws") as ws1:
            async with client.ws_connect("/ws") as ws2:
                await asyncio.wait_for(ws1.receive(), timeout=2.0)
                await asyncio.wait_for(ws2.receive(), timeout=2.0)
                subtitle_queue.put({"type": "subtitle", "lines": ["broadcast"], "translated_lines": []})
                msg1 = await asyncio.wait_for(ws1.receive(), timeout=2.0)
                msg2 = await asyncio.wait_for(ws2.receive(), timeout=2.0)
                assert json.loads(msg1.data)["lines"] == ["broadcast"]
                assert json.loads(msg2.data)["lines"] == ["broadcast"]
```

- [ ] **Step 2: Run to confirm failures**

```
pytest tests/test_server.py -v
```

Expected: FAIL (create_app still takes one arg, routes don't exist)

- [ ] **Step 3: Replace server.py**

```python
import asyncio
import json
import queue
from pathlib import Path

from aiohttp import web

from config import AppConfig, AudioConfig, TranscriptionConfig, DisplayConfig, TranslationConfig, _build, _validate_config, write_config


def _config_to_dict(config: AppConfig) -> dict:
    return {
        "audio": {
            "mode": config.audio.mode,
            "mic_device": config.audio.mic_device,
            "loopback_device": config.audio.loopback_device,
        },
        "transcription": {
            "model": config.transcription.model,
            "language": config.transcription.language,
            "device": config.transcription.device,
        },
        "display": {
            "lines": config.display.lines,
            "port": config.display.port,
            "font_family": config.display.font_family,
            "font_size": config.display.font_size,
            "font_color": config.display.font_color,
            "bg_color": config.display.bg_color,
            "bg_opacity": config.display.bg_opacity,
            "max_chars_per_line": config.display.max_chars_per_line,
            "fade_duration": config.display.fade_duration,
        },
        "translation": {
            "enabled": config.translation.enabled,
            "url": config.translation.url,
            "source_lang": config.translation.source_lang,
            "target_lang": config.translation.target_lang,
            "dual_language": config.translation.dual_language,
        },
    }


def _display_config_message(config: AppConfig) -> dict:
    return {
        "type": "config",
        "display": {
            "font_family": config.display.font_family,
            "font_size": config.display.font_size,
            "font_color": config.display.font_color,
            "bg_color": config.display.bg_color,
            "bg_opacity": config.display.bg_opacity,
            "fade_duration": config.display.fade_duration,
        },
    }


_RESTART_KEYS = {"audio", "transcription"}


async def create_app(
    subtitle_queue: queue.Queue,
    config: AppConfig,
    config_path: str = "config.toml",
) -> web.Application:
    clients: set[web.WebSocketResponse] = set()
    base = Path(__file__).parent
    overlay_path = base / "overlay.html"
    settings_path = base / "settings.html"

    if not overlay_path.is_file():
        raise RuntimeError(f"overlay.html not found at {overlay_path}")
    if not settings_path.is_file():
        raise RuntimeError(f"settings.html not found at {settings_path}")

    async def index(request: web.Request) -> web.FileResponse:
        return web.FileResponse(overlay_path)

    async def settings(request: web.Request) -> web.FileResponse:
        return web.FileResponse(settings_path)

    async def get_config(request: web.Request) -> web.Response:
        return web.json_response(_config_to_dict(config))

    async def post_config(request: web.Request) -> web.Response:
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "invalid JSON"}, status=400)

        current = _config_to_dict(config)
        try:
            new_audio = _build(AudioConfig, {**current["audio"], **body.get("audio", {})})
            new_transcription = _build(TranscriptionConfig, {**current["transcription"], **body.get("transcription", {})})
            new_display = _build(DisplayConfig, {**current["display"], **body.get("display", {})})
            new_translation = _build(TranslationConfig, {**current["translation"], **body.get("translation", {})})
        except (TypeError, ValueError) as e:
            return web.json_response({"error": str(e)}, status=400)

        new_cfg = AppConfig(audio=new_audio, transcription=new_transcription,
                            display=new_display, translation=new_translation)
        try:
            _validate_config(new_cfg)
        except ValueError as e:
            return web.json_response({"error": str(e)}, status=400)

        new_dict = _config_to_dict(new_cfg)
        requires_restart = (
            current["audio"] != new_dict["audio"]
            or current["transcription"] != new_dict["transcription"]
            or current["translation"] != new_dict["translation"]
            or current["display"]["lines"] != new_dict["display"]["lines"]
            or current["display"]["port"] != new_dict["display"]["port"]
            or current["display"]["max_chars_per_line"] != new_dict["display"]["max_chars_per_line"]
        )

        config.audio = new_cfg.audio
        config.transcription = new_cfg.transcription
        config.display = new_cfg.display
        config.translation = new_cfg.translation
        write_config(config, config_path)

        cfg_msg = json.dumps(_display_config_message(config))
        dead: set[web.WebSocketResponse] = set()
        for ws in list(clients):
            try:
                await ws.send_str(cfg_msg)
            except Exception:
                dead.add(ws)
        clients.difference_update(dead)

        return web.json_response({**_config_to_dict(config), "requires_restart": requires_restart})

    async def websocket_handler(request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        clients.add(ws)
        await ws.send_str(json.dumps(_display_config_message(config)))
        try:
            async for _ in ws:
                pass
        finally:
            clients.discard(ws)
        return ws

    async def broadcaster() -> None:
        while True:
            try:
                data = subtitle_queue.get_nowait()
            except queue.Empty:
                await asyncio.sleep(0.05)
                continue
            if data is None:
                break
            message = json.dumps(data)
            dead: set[web.WebSocketResponse] = set()
            for ws in list(clients):
                try:
                    await ws.send_str(message)
                except Exception:
                    dead.add(ws)
            clients.difference_update(dead)

    app = web.Application()
    app.router.add_get("/", index)
    app.router.add_get("/settings", settings)
    app.router.add_get("/api/config", get_config)
    app.router.add_post("/api/config", post_config)
    app.router.add_get("/ws", websocket_handler)

    async def on_startup(app: web.Application) -> None:
        app["broadcaster_task"] = asyncio.create_task(broadcaster())

    async def on_cleanup(app: web.Application) -> None:
        task = app.get("broadcaster_task")
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    return app
```

- [ ] **Step 4: Run tests to confirm pass**

```
pytest tests/test_server.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```
git add server.py tests/test_server.py
git commit -m "feat: add JSON config API and settings route to server"
```

---

## Task 6: Update overlay.html

**Files:**
- Modify: `overlay.html`

- [ ] **Step 1: Replace overlay.html**

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }

    body {
      background: transparent;
      width: 100vw;
      height: 100vh;
      display: flex;
      align-items: flex-end;
      justify-content: center;
      padding-bottom: 40px;
      font-family: var(--font-family, Arial), sans-serif;
    }

    #subtitles {
      max-width: 90%;
      text-align: center;
    }

    .line {
      display: block;
      background: var(--bg-rgba, rgba(0,0,0,0.75));
      color: var(--font-color, #ffffff);
      font-size: var(--font-size, 36px);
      font-weight: bold;
      padding: 6px 18px;
      border-radius: 8px;
      margin: 4px auto;
      text-shadow: 1px 1px 3px rgba(0,0,0,0.9);
      max-width: fit-content;
      transition: opacity 0.5s ease;
    }

    .line.translated {
      opacity: 0.75;
      font-size: calc(var(--font-size, 36px) * 0.85);
    }

    .line.fading {
      opacity: 0;
    }
  </style>
</head>
<body>
  <div id="subtitles"></div>
  <script>
    const container = document.getElementById('subtitles');
    const root = document.documentElement.style;
    let fadeTimers = [];

    function applyDisplayConfig(display) {
      root.setProperty('--font-family', display.font_family);
      root.setProperty('--font-size', display.font_size + 'px');
      root.setProperty('--font-color', display.font_color);
      const op = display.bg_opacity !== undefined ? display.bg_opacity : 0.75;
      const hex = display.bg_color || '#000000';
      const r = parseInt(hex.slice(1,3),16);
      const g = parseInt(hex.slice(3,5),16);
      const b = parseInt(hex.slice(5,7),16);
      root.setProperty('--bg-rgba', `rgba(${r},${g},${b},${op})`);
      root.setProperty('--fade-duration', (display.fade_duration || 0) + 's');
    }

    function escapeHtml(text) {
      return String(text)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    function render(lines, translatedLines, fadeDuration) {
      fadeTimers.forEach(clearTimeout);
      fadeTimers = [];

      const allSpans = [];
      lines.forEach(line => {
        allSpans.push(`<span class="line">${escapeHtml(line)}</span>`);
      });
      translatedLines.forEach(line => {
        if (line) allSpans.push(`<span class="line translated">${escapeHtml(line)}</span>`);
      });
      container.innerHTML = allSpans.join('');

      if (fadeDuration > 0) {
        const spans = container.querySelectorAll('.line');
        spans.forEach(span => {
          const timer = setTimeout(() => span.classList.add('fading'), fadeDuration * 1000);
          fadeTimers.push(timer);
        });
      }
    }

    let currentFadeDuration = 0;

    function connect() {
      const ws = new WebSocket(`ws://${location.host}/ws`);

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'config') {
            applyDisplayConfig(data.display);
            currentFadeDuration = data.display.fade_duration || 0;
          } else if (data.type === 'subtitle') {
            render(data.lines || [], data.translated_lines || [], currentFadeDuration);
          }
        } catch (e) {
          console.error('Bad message', e);
        }
      };

      ws.onclose = () => setTimeout(connect, 1000);
      ws.onerror = () => ws.close();
    }

    connect();
  </script>
</body>
</html>
```

- [ ] **Step 2: Commit**

```
git add overlay.html
git commit -m "feat: update overlay with CSS variables, live config, fade, dual-language"
```

---

## Task 7: Wire main.py

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Update main.py**

Update the `start_transcription` call (remove individual params, pass `config`) and the `create_app` call (add `config`):

```python
import asyncio
import queue
import threading

from aiohttp import web

from audio import start_microphone_capture, start_loopback_capture, list_input_devices, list_output_devices
from buffer import SubtitleBuffer
from config import load_config, AppConfig
from server import create_app
from transcriber import start_transcription


def _print_startup(config: AppConfig) -> None:
    mode = config.audio.mode
    if mode == "microphone":
        audio_desc = f"microphone ({config.audio.mic_device})"
    elif mode == "loopback":
        audio_desc = f"loopback ({config.audio.loopback_device})"
    else:
        audio_desc = "microphone + loopback"

    print("\n[Subtitle Everything]")
    print(f"  Model:    {config.transcription.model} ({config.transcription.device})")
    print(f"  Audio:    {audio_desc}")
    print(f"  Language: {config.transcription.language}")
    print(f"  Overlay:  http://localhost:{config.display.port}")
    print(f"  Settings: http://localhost:{config.display.port}/settings")
    print("\nAdd the Overlay URL as a Browser Source in OBS.")
    print("Press Ctrl+C to stop.\n")


def _resolve_device(config: AppConfig) -> AppConfig:
    if config.transcription.device == "cuda":
        try:
            import torch
            if not torch.cuda.is_available():
                print("Warning: CUDA requested but not available. Falling back to CPU.")
                config.transcription.device = "cpu"
        except ImportError:
            print("Warning: torch not installed. Falling back to CPU.")
            config.transcription.device = "cpu"
    return config


async def _run_server(config: AppConfig, subtitle_queue: queue.Queue) -> None:
    app = await create_app(subtitle_queue, config)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "localhost", config.display.port)
    await site.start()
    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        pass
    finally:
        await runner.cleanup()


def main() -> None:
    config = load_config()
    config = _resolve_device(config)

    audio_queue: queue.Queue = queue.Queue()
    subtitle_queue: queue.Queue = queue.Queue()
    stop_event = threading.Event()
    subtitle_buffer = SubtitleBuffer(max_lines=config.display.lines)

    _print_startup(config)

    threads: list[threading.Thread] = []

    if config.audio.mode in ("microphone", "both"):
        threads.append(threading.Thread(
            target=start_microphone_capture,
            args=(audio_queue, config.audio.mic_device, stop_event),
            daemon=True,
            name="mic-capture",
        ))

    if config.audio.mode in ("loopback", "both"):
        threads.append(threading.Thread(
            target=start_loopback_capture,
            args=(audio_queue, config.audio.loopback_device, stop_event),
            daemon=True,
            name="loopback-capture",
        ))

    threads.append(threading.Thread(
        target=start_transcription,
        args=(audio_queue, subtitle_queue, subtitle_buffer, config, stop_event),
        daemon=True,
        name="transcriber",
    ))

    for t in threads:
        t.start()

    try:
        asyncio.run(_run_server(config, subtitle_queue))
    except KeyboardInterrupt:
        pass
    finally:
        print("\nShutting down...")
        stop_event.set()
        for t in threads:
            t.join(timeout=3)
        print("Stopped.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run full test suite**

```
pytest -v
```

Expected: all PASS

- [ ] **Step 3: Commit**

```
git add main.py
git commit -m "feat: wire AppConfig through to server and transcriber in main.py"
```

---

## Task 8: Update requirements.txt

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add requests**

```
faster-whisper>=1.0.0
sounddevice>=0.4.6
pyaudiowpatch>=0.2.12
numpy>=1.24.0
aiohttp>=3.9.0
requests>=2.28.0
tomli>=2.0.0; python_version < "3.11"
pytest>=7.4.0
pytest-asyncio>=0.23.0
```

- [ ] **Step 2: Run full test suite one final time**

```
pytest -v
```

Expected: all PASS

- [ ] **Step 3: Commit**

```
git add requirements.txt
git commit -m "chore: add requests dependency for LibreTranslate client"
```
