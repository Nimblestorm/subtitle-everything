# Dual-Source Transcription Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run two independent Whisper transcription pipelines when `audio.mode = "both"`, with each source displayed in its own color-coded, independently-positioned overlay container.

**Architecture:** Replace the single `transcription.model` field with per-source `mic_model`/`loopback_model` fields (both restricted to `tiny`/`base`). Add per-source color and position fields to `DisplayConfig`. When mode is `both`, `main.py` creates two audio queues, two transcription threads, and two subtitle buffers. The overlay routes subtitle messages by `source` field to one of two fixed-position containers.

**Tech Stack:** Python dataclasses, faster-whisper, aiohttp WebSocket, vanilla JS/HTML

---

## File Map

| File | Change |
|---|---|
| `config.py` | Replace `TranscriptionConfig.model` with `mic_model`/`loopback_model`; add 4 new `DisplayConfig` fields; update `DEFAULT_CONFIG`, `validate_config`, `write_config` |
| `server.py` | Update `_config_to_dict` and `_display_config_message` to include new fields — **must follow config.py** |
| `transcriber.py` | Add `source: str = "mic"` param; load model by source; tag messages with `source` |
| `main.py` | Fix pre-existing call-site bugs; dual-queue/thread setup for `both` mode; RAM warning |
| `overlay.html` | Two containers; per-source color CSS vars; JS routes messages by `source` |
| `settings.html` | Split model dropdown into two; RAM warning; add color/position fields |
| `tests/test_config.py` | Update broken assertions; add 7 new tests for new fields/validation |
| `tests/test_transcriber.py` | Update message format assertions; add source-tagging test |
| `tests/test_server.py` | Update overlay assertion; update transcription dict assertion; add source-fields test |

**Important ordering note:** Task 1 (config.py) removes `TranscriptionConfig.model`. Task 2 (server.py) must immediately follow because `server.py` references `config.transcription.model` — leaving it unfixed would break `test_server.py` after Task 1.

---

### Task 1: Update config.py

**Files:**
- Modify: `config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing tests**

Add these tests to `tests/test_config.py`. Run them first to confirm they fail.

```python
def test_transcription_config_new_defaults(tmp_path):
    from config import load_config
    cfg = load_config(str(tmp_path / "config.toml"))
    assert cfg.transcription.mic_model == "base"
    assert cfg.transcription.loopback_model == "base"
    assert not hasattr(cfg.transcription, "model")


def test_display_source_defaults(tmp_path):
    from config import load_config
    cfg = load_config(str(tmp_path / "config.toml"))
    assert cfg.display.mic_color == "#ffffff"
    assert cfg.display.mic_position == "bottom"
    assert cfg.display.loopback_color == "#00d4ff"
    assert cfg.display.loopback_position == "top"


def test_load_config_raises_on_invalid_mic_model(tmp_path):
    f = tmp_path / "config.toml"
    f.write_text('[transcription]\nmic_model = "large"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="mic_model"):
        load_config(str(f))


def test_load_config_raises_on_invalid_loopback_model(tmp_path):
    f = tmp_path / "config.toml"
    f.write_text('[transcription]\nloopback_model = "medium"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="loopback_model"):
        load_config(str(f))


def test_load_config_raises_on_invalid_mic_position(tmp_path):
    f = tmp_path / "config.toml"
    f.write_text('[display]\nmic_position = "center"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="mic_position"):
        load_config(str(f))


def test_load_config_raises_on_invalid_mic_color(tmp_path):
    f = tmp_path / "config.toml"
    f.write_text('[display]\nmic_color = "blue"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="mic_color"):
        load_config(str(f))


def test_write_config_roundtrip_source_fields(tmp_path):
    from config import write_config, AppConfig
    cfg = AppConfig()
    cfg.transcription.mic_model = "tiny"
    cfg.transcription.loopback_model = "base"
    cfg.display.mic_color = "#ff0000"
    cfg.display.mic_position = "top"
    cfg.display.loopback_color = "#00ff00"
    cfg.display.loopback_position = "bottom"
    p = str(tmp_path / "out.toml")
    write_config(cfg, p)
    loaded = load_config(p)
    assert loaded.transcription.mic_model == "tiny"
    assert loaded.transcription.loopback_model == "base"
    assert loaded.display.mic_color == "#ff0000"
    assert loaded.display.mic_position == "top"
    assert loaded.display.loopback_color == "#00ff00"
    assert loaded.display.loopback_position == "bottom"
```

Also update these **existing** tests that reference the removed `model` field:

```python
def test_load_config_creates_default_file(tmp_path):
    config_file = tmp_path / "config.toml"
    cfg = load_config(str(config_file))
    assert config_file.exists()
    assert cfg.audio.mode == "microphone"
    assert cfg.transcription.mic_model == "base"
    assert cfg.transcription.loopback_model == "base"
    assert cfg.display.lines == 3
    assert cfg.display.port == 8765
    assert cfg.translation.enabled is False


def test_load_config_reads_existing_file(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[audio]\nmode = "loopback"\n\n[transcription]\nmic_model = "tiny"\nloopback_model = "base"\nlanguage = "ja"\ndevice = "cpu"\n\n[display]\nlines = 2\nport = 9000\n\n[translation]\nenabled = false\n',
        encoding="utf-8",
    )
    cfg = load_config(str(config_file))
    assert cfg.audio.mode == "loopback"
    assert cfg.transcription.mic_model == "tiny"
    assert cfg.transcription.loopback_model == "base"
    assert cfg.transcription.language == "ja"
    assert cfg.display.lines == 2
    assert cfg.display.port == 9000


def test_load_config_partial_file_uses_defaults(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text('[audio]\nmode = "both"\n', encoding="utf-8")
    cfg = load_config(str(config_file))
    assert cfg.audio.mode == "both"
    assert cfg.transcription.mic_model == "base"
    assert cfg.transcription.loopback_model == "base"
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_config.py -v
```

Expected: new tests fail, updated tests fail on `model` attribute.

- [ ] **Step 3: Update `TranscriptionConfig` in `config.py`**

Replace the existing `TranscriptionConfig` dataclass:

```python
@dataclass
class TranscriptionConfig:
    mic_model: str = "base"
    loopback_model: str = "base"
    language: str = "en"
    device: str = "cpu"
```

- [ ] **Step 4: Add new fields to `DisplayConfig` in `config.py`**

Replace the existing `DisplayConfig` dataclass:

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
    mic_color: str = "#ffffff"
    mic_position: str = "bottom"
    loopback_color: str = "#00d4ff"
    loopback_position: str = "top"
```

- [ ] **Step 5: Update `DEFAULT_CONFIG` in `config.py`**

Replace the existing `DEFAULT_CONFIG` string:

```python
DEFAULT_CONFIG = """\
[audio]
mode = "microphone"
mic_device = "default"
loopback_device = "default"

[transcription]
mic_model = "base"
loopback_model = "base"
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
mic_color = "#ffffff"
mic_position = "bottom"
loopback_color = "#00d4ff"
loopback_position = "top"

[translation]
enabled = false
url = "http://localhost:5000"
source_lang = "en"
target_lang = "es"
dual_language = false
"""
```

- [ ] **Step 6: Update `validate_config` in `config.py`**

Add these validation rules at the end of the `validate_config` function (after the existing `bg_color` check):

```python
    if cfg.transcription.mic_model not in ("tiny", "base"):
        raise ValueError(f"[transcription] mic_model must be 'tiny' or 'base', got {cfg.transcription.mic_model!r}")
    if cfg.transcription.loopback_model not in ("tiny", "base"):
        raise ValueError(f"[transcription] loopback_model must be 'tiny' or 'base', got {cfg.transcription.loopback_model!r}")
    if not _HEX_COLOR_RE.match(cfg.display.mic_color):
        raise ValueError(f"[display] mic_color must be #rrggbb hex, got {cfg.display.mic_color!r}")
    if not _HEX_COLOR_RE.match(cfg.display.loopback_color):
        raise ValueError(f"[display] loopback_color must be #rrggbb hex, got {cfg.display.loopback_color!r}")
    if cfg.display.mic_position not in ("top", "bottom"):
        raise ValueError(f"[display] mic_position must be 'top' or 'bottom', got {cfg.display.mic_position!r}")
    if cfg.display.loopback_position not in ("top", "bottom"):
        raise ValueError(f"[display] loopback_position must be 'top' or 'bottom', got {cfg.display.loopback_position!r}")
```

- [ ] **Step 7: Update `write_config` in `config.py`**

Replace the `[transcription]` block in the `write_config` f-string:

```python
        f'[transcription]\n'
        f'mic_model = "{_toml_str(tr.mic_model)}"\n'
        f'loopback_model = "{_toml_str(tr.loopback_model)}"\n'
        f'language = "{_toml_str(tr.language)}"\n'
        f'device = "{_toml_str(tr.device)}"\n'
        f'\n'
```

Add the four new fields at the end of the `[display]` block, after the `fade_duration` line:

```python
        f'mic_color = "{_toml_str(d.mic_color)}"\n'
        f'mic_position = "{_toml_str(d.mic_position)}"\n'
        f'loopback_color = "{_toml_str(d.loopback_color)}"\n'
        f'loopback_position = "{_toml_str(d.loopback_position)}"\n'
        f'\n'
```

- [ ] **Step 8: Run config tests to verify they pass**

```
pytest tests/test_config.py -v
```

Expected: all tests pass.

- [ ] **Step 9: Commit**

```bash
git add config.py tests/test_config.py
git commit -m "feat: per-source model and display config fields"
```

---

### Task 2: Update server.py

**Files:**
- Modify: `server.py`
- Test: `tests/test_server.py`

Note: This task must follow Task 1. After Task 1 removes `TranscriptionConfig.model`, `server.py` references `config.transcription.model` which no longer exists. This task fixes that immediately.

- [ ] **Step 1: Write the failing tests**

Update `test_get_api_config_returns_json` in `tests/test_server.py` to assert the new transcription and display fields:

```python
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
        assert data["display"]["mic_color"] == "#ffffff"
        assert data["display"]["mic_position"] == "bottom"
        assert data["display"]["loopback_color"] == "#00d4ff"
        assert data["display"]["loopback_position"] == "top"
        assert data["transcription"]["mic_model"] == "base"
        assert data["transcription"]["loopback_model"] == "base"
        assert data["translation"]["target_lang"] == "es"
```

Add a new test for the WebSocket config message:

```python
@pytest.mark.asyncio
async def test_websocket_config_includes_source_fields():
    from aiohttp.test_utils import TestClient, TestServer
    app = await _make_app()
    async with TestClient(TestServer(app)) as client:
        async with client.ws_connect("/ws") as ws:
            msg = await asyncio.wait_for(ws.receive(), timeout=2.0)
            data = json.loads(msg.data)
            assert data["type"] == "config"
            assert data["display"]["mic_color"] == "#ffffff"
            assert data["display"]["mic_position"] == "bottom"
            assert data["display"]["loopback_color"] == "#00d4ff"
            assert data["display"]["loopback_position"] == "top"
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_server.py::test_get_api_config_returns_json tests/test_server.py::test_websocket_config_includes_source_fields -v
```

Expected: failures.

- [ ] **Step 3: Update `_config_to_dict` in `server.py`**

Replace the full function:

```python
def _config_to_dict(config: AppConfig) -> dict:
    return {
        "audio": {
            "mode": config.audio.mode,
            "mic_device": config.audio.mic_device,
            "loopback_device": config.audio.loopback_device,
        },
        "transcription": {
            "mic_model": config.transcription.mic_model,
            "loopback_model": config.transcription.loopback_model,
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
            "mic_color": config.display.mic_color,
            "mic_position": config.display.mic_position,
            "loopback_color": config.display.loopback_color,
            "loopback_position": config.display.loopback_position,
        },
        "translation": {
            "enabled": config.translation.enabled,
            "url": config.translation.url,
            "source_lang": config.translation.source_lang,
            "target_lang": config.translation.target_lang,
            "dual_language": config.translation.dual_language,
        },
    }
```

- [ ] **Step 4: Update `_display_config_message` in `server.py`**

Replace the full function:

```python
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
            "mic_color": config.display.mic_color,
            "mic_position": config.display.mic_position,
            "loopback_color": config.display.loopback_color,
            "loopback_position": config.display.loopback_position,
        },
    }
```

- [ ] **Step 5: Run full test suite**

```
pytest -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add server.py tests/test_server.py
git commit -m "feat: include source color/position fields in config API and WS messages"
```

---

### Task 3: Update transcriber.py

**Files:**
- Modify: `transcriber.py`
- Test: `tests/test_transcriber.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_transcriber.py`:

```python
def test_transcriber_tags_message_with_source():
    from transcriber import start_transcription
    from buffer import SubtitleBuffer
    from config import AppConfig

    audio_queue = queue.Queue()
    subtitle_queue = queue.Queue()
    stop_event = threading.Event()
    buf = SubtitleBuffer(max_lines=3)
    config = AppConfig()

    audio_queue.put(np.zeros(48000, dtype=np.float32))
    mock_model = _make_mock_model(["hello"])

    with patch("transcriber.WhisperModel", lambda *a, **kw: mock_model):
        t = threading.Thread(
            target=start_transcription,
            args=(audio_queue, subtitle_queue, buf, config, stop_event),
            kwargs={"source": "loopback"},
            daemon=True,
        )
        t.start()
        result = subtitle_queue.get(timeout=3.0)
        stop_event.set()
        t.join(timeout=2)

    assert result["source"] == "loopback"
```

Also update `test_transcriber_pushes_text_to_subtitle_queue` to assert the default source field:

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
    assert result["source"] == "mic"
    assert result["lines"] == ["hello world"]
    assert result["translated_lines"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_transcriber.py::test_transcriber_tags_message_with_source tests/test_transcriber.py::test_transcriber_pushes_text_to_subtitle_queue -v
```

Expected: failures.

- [ ] **Step 3: Update `start_transcription` in `transcriber.py`**

Replace the full `start_transcription` function:

```python
def start_transcription(
    audio_queue: queue.Queue,
    subtitle_queue: queue.Queue,
    subtitle_buffer: SubtitleBuffer,
    config: AppConfig,
    stop_event: threading.Event,
    source: str = "mic",
) -> None:
    compute_type = "float16" if config.transcription.device == "cuda" else "int8"
    model_name = config.transcription.mic_model if source == "mic" else config.transcription.loopback_model
    model = WhisperModel(
        model_name,
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
            "source": source,
            "lines": lines,
            "translated_lines": translated_lines,
        })
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_transcriber.py -v
```

Expected: all 8 tests pass.

- [ ] **Step 5: Commit**

```bash
git add transcriber.py tests/test_transcriber.py
git commit -m "feat: add source parameter to start_transcription"
```

---

### Task 4: Update main.py

**Files:**
- Modify: `main.py`

No new tests — `main.py` is integration wiring covered by existing unit tests. This task also fixes two pre-existing bugs:
1. `_run_server` calls `create_app(subtitle_queue)` — missing `config` argument
2. The transcription `Thread` passes individual string args instead of `config`

- [ ] **Step 1: Replace `main.py` with the corrected version**

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
    print(f"  Model:    mic={config.transcription.mic_model} loopback={config.transcription.loopback_model} ({config.transcription.device})")
    print(f"  Audio:    {audio_desc}")
    print(f"  Language: {config.transcription.language}")
    print(f"  Overlay:  http://localhost:{config.display.port}")
    print(f"  Settings: http://localhost:{config.display.port}/settings")
    print("\nAdd this URL as a Browser Source in OBS.")
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

    subtitle_queue: queue.Queue = queue.Queue()
    stop_event = threading.Event()

    _print_startup(config)

    threads: list[threading.Thread] = []

    if config.audio.mode == "both":
        print(
            'Warning: dual-source mode loads two Whisper models. '
            'Consider using "tiny" for one or both sources if you experience high memory usage.\n'
        )
        mic_audio_queue: queue.Queue = queue.Queue()
        loopback_audio_queue: queue.Queue = queue.Queue()
        mic_buffer = SubtitleBuffer(max_lines=config.display.lines)
        loopback_buffer = SubtitleBuffer(max_lines=config.display.lines)

        threads.append(threading.Thread(
            target=start_microphone_capture,
            args=(mic_audio_queue, config.audio.mic_device, stop_event),
            daemon=True,
            name="mic-capture",
        ))
        threads.append(threading.Thread(
            target=start_loopback_capture,
            args=(loopback_audio_queue, config.audio.loopback_device, stop_event),
            daemon=True,
            name="loopback-capture",
        ))
        threads.append(threading.Thread(
            target=start_transcription,
            args=(mic_audio_queue, subtitle_queue, mic_buffer, config, stop_event),
            kwargs={"source": "mic"},
            daemon=True,
            name="transcriber-mic",
        ))
        threads.append(threading.Thread(
            target=start_transcription,
            args=(loopback_audio_queue, subtitle_queue, loopback_buffer, config, stop_event),
            kwargs={"source": "loopback"},
            daemon=True,
            name="transcriber-loopback",
        ))
    else:
        audio_queue: queue.Queue = queue.Queue()
        subtitle_buffer = SubtitleBuffer(max_lines=config.display.lines)

        if config.audio.mode == "microphone":
            threads.append(threading.Thread(
                target=start_microphone_capture,
                args=(audio_queue, config.audio.mic_device, stop_event),
                daemon=True,
                name="mic-capture",
            ))
            source = "mic"
        else:
            threads.append(threading.Thread(
                target=start_loopback_capture,
                args=(audio_queue, config.audio.loopback_device, stop_event),
                daemon=True,
                name="loopback-capture",
            ))
            source = "loopback"

        threads.append(threading.Thread(
            target=start_transcription,
            args=(audio_queue, subtitle_queue, subtitle_buffer, config, stop_event),
            kwargs={"source": source},
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

Expected: all tests pass.

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "feat: dual-pipeline wiring for both mode, fix create_app and transcription call sites"
```

---

### Task 5: Update overlay.html

**Files:**
- Modify: `overlay.html`
- Test: `tests/test_server.py` (update one existing assertion)

- [ ] **Step 1: Update the overlay assertion in `tests/test_server.py`**

`test_get_root_serves_overlay` currently checks for `<div id="subtitles">` which will no longer exist. Update it:

```python
@pytest.mark.asyncio
async def test_get_root_serves_overlay():
    from aiohttp.test_utils import TestClient, TestServer
    app = await _make_app()
    async with TestClient(TestServer(app)) as client:
        resp = await client.get("/")
        assert resp.status == 200
        text = await resp.text()
        assert 'id="subtitles-mic"' in text
        assert 'id="subtitles-loopback"' in text
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/test_server.py::test_get_root_serves_overlay -v
```

Expected: FAIL (overlay still has old single container).

- [ ] **Step 3: Replace `overlay.html`**

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
      font-family: var(--font-family, Arial), sans-serif;
    }

    .subtitle-container {
      position: fixed;
      left: 0;
      right: 0;
      width: 100%;
      text-align: center;
      padding: 0 5%;
    }

    .line {
      display: block;
      background: var(--bg-rgba, rgba(0,0,0,0.75));
      font-size: var(--font-size, 36px);
      font-weight: bold;
      padding: 6px 18px;
      border-radius: 8px;
      margin: 4px auto;
      text-shadow: 1px 1px 3px rgba(0,0,0,0.9);
      max-width: fit-content;
      transition: opacity 0.5s ease;
    }

    #subtitles-mic .line {
      color: var(--mic-color, #ffffff);
    }

    #subtitles-loopback .line {
      color: var(--loopback-color, #00d4ff);
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
  <div id="subtitles-mic" class="subtitle-container"></div>
  <div id="subtitles-loopback" class="subtitle-container"></div>
  <script>
    const root = document.documentElement.style;
    let fadeTimers = [];
    let currentFadeDuration = 0;

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
      root.setProperty('--mic-color', display.mic_color || '#ffffff');
      root.setProperty('--loopback-color', display.loopback_color || '#00d4ff');

      const micEl = document.getElementById('subtitles-mic');
      if (display.mic_position === 'top') {
        micEl.style.top = '40px';
        micEl.style.bottom = 'auto';
      } else {
        micEl.style.bottom = '40px';
        micEl.style.top = 'auto';
      }

      const loopbackEl = document.getElementById('subtitles-loopback');
      if (display.loopback_position === 'top') {
        loopbackEl.style.top = '40px';
        loopbackEl.style.bottom = 'auto';
      } else {
        loopbackEl.style.bottom = '40px';
        loopbackEl.style.top = 'auto';
      }
    }

    function escapeHtml(text) {
      return String(text)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    function render(containerId, lines, translatedLines, fadeDuration) {
      fadeTimers.forEach(clearTimeout);
      fadeTimers = [];

      const container = document.getElementById(containerId);
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

    function connect() {
      const ws = new WebSocket(`ws://${location.host}/ws`);

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'config') {
            applyDisplayConfig(data.display);
            currentFadeDuration = data.display.fade_duration || 0;
          } else if (data.type === 'subtitle') {
            const source = data.source || 'mic';
            const containerId = source === 'loopback' ? 'subtitles-loopback' : 'subtitles-mic';
            render(containerId, data.lines || [], data.translated_lines || [], currentFadeDuration);
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

- [ ] **Step 4: Run full test suite**

```
pytest -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add overlay.html tests/test_server.py
git commit -m "feat: dual-container overlay with per-source color and position"
```

---

### Task 6: Update settings.html

**Files:**
- Modify: `settings.html`

No new automated tests — the existing `test_get_settings_serves_settings_page` confirms the page loads and contains `api/config`, which is sufficient.

- [ ] **Step 1: Verify existing settings test still passes before touching the file**

```
pytest tests/test_server.py::test_get_settings_serves_settings_page -v
```

Expected: PASS.

- [ ] **Step 2: Replace `settings.html`**

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
    .warning { font-size: 11px; color: #b06000; background: #fff8e1; border: 1px solid #f0c040; padding: 6px 8px; border-radius: 4px; margin: 6px 0 0; }
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

  <label>Mic Color</label>
  <input type="color" id="mic_color">
  <label>Mic Position</label>
  <select id="mic_position">
    <option value="bottom">Bottom</option>
    <option value="top">Top</option>
  </select>
  <label>Loopback Color</label>
  <input type="color" id="loopback_color">
  <label>Loopback Position</label>
  <select id="loopback_position">
    <option value="top">Top</option>
    <option value="bottom">Bottom</option>
  </select>

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
  <label>Mic Model</label>
  <select id="mic_model">
    <option value="tiny">tiny</option>
    <option value="base">base</option>
  </select>
  <label>Loopback Model</label>
  <select id="loopback_model">
    <option value="tiny">tiny</option>
    <option value="base">base</option>
  </select>
  <p id="dual_model_warning" class="warning" style="display:none">
    Running two Whisper models simultaneously. Use "tiny" for one or both sources if memory usage is high.
  </p>
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
      document.getElementById('mic_color').value = cfg.display.mic_color;
      document.getElementById('mic_position').value = cfg.display.mic_position;
      document.getElementById('loopback_color').value = cfg.display.loopback_color;
      document.getElementById('loopback_position').value = cfg.display.loopback_position;
      document.getElementById('translation_enabled').checked = cfg.translation.enabled;
      document.getElementById('translation_url').value = cfg.translation.url;
      document.getElementById('source_lang').value = cfg.translation.source_lang;
      document.getElementById('target_lang').value = cfg.translation.target_lang;
      document.getElementById('dual_language').checked = cfg.translation.dual_language;
      document.getElementById('audio_mode').value = cfg.audio.mode;
      updateDualWarning(cfg.audio.mode);
      document.getElementById('mic_device').value = cfg.audio.mic_device;
      document.getElementById('loopback_device').value = cfg.audio.loopback_device;
      document.getElementById('mic_model').value = cfg.transcription.mic_model;
      document.getElementById('loopback_model').value = cfg.transcription.loopback_model;
      document.getElementById('transcription_language').value = cfg.transcription.language;
      document.getElementById('transcription_device').value = cfg.transcription.device;
    }

    function updateDualWarning(mode) {
      document.getElementById('dual_model_warning').style.display = mode === 'both' ? 'block' : 'none';
    }

    document.getElementById('bg_opacity').addEventListener('input', e => {
      document.getElementById('bg_opacity_val').textContent = parseFloat(e.target.value).toFixed(2);
    });

    document.getElementById('audio_mode').addEventListener('change', e => {
      updateDualWarning(e.target.value);
    });

    async function save() {
      const body = {
        audio: {
          mode: document.getElementById('audio_mode').value,
          mic_device: document.getElementById('mic_device').value,
          loopback_device: document.getElementById('loopback_device').value,
        },
        transcription: {
          mic_model: document.getElementById('mic_model').value,
          loopback_model: document.getElementById('loopback_model').value,
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
          mic_color: document.getElementById('mic_color').value,
          mic_position: document.getElementById('mic_position').value,
          loopback_color: document.getElementById('loopback_color').value,
          loopback_position: document.getElementById('loopback_position').value,
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

- [ ] **Step 3: Run full test suite**

```
pytest -v
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add settings.html
git commit -m "feat: dual-source model selection and color/position fields in settings"
```
