# Subtitle Everything Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a single Python app that transcribes live audio (mic, system loopback, or both) with faster-whisper and serves real-time subtitles to OBS via a local Browser Source at `http://localhost:8765`.

**Architecture:** A single Python process with two background threads (audio capture, transcription) and an asyncio event loop (aiohttp HTTP + WebSocket server). Threads communicate via `queue.Queue`. OBS connects to the overlay HTML page, which updates subtitles via WebSocket push.

**Tech Stack:** Python 3.11+, faster-whisper, sounddevice, pyaudiowpatch, numpy, aiohttp, tomllib (stdlib), pytest, pytest-asyncio

---

## File Map

| File | Responsibility |
|---|---|
| `config.py` | Load/write `config.toml`, expose typed `AppConfig` dataclass |
| `buffer.py` | Rolling window of N subtitle lines |
| `overlay.html` | Static OBS Browser Source — connects to WebSocket, renders lines |
| `server.py` | aiohttp HTTP + WebSocket server; broadcasts subtitle updates |
| `audio.py` | Mic / loopback / both audio capture → `audio_queue` |
| `transcriber.py` | faster-whisper transcription loop → `subtitle_queue` |
| `main.py` | Entry point — wires all components, startup banner, clean shutdown |
| `requirements.txt` | Pinned dependencies |
| `tests/test_config.py` | Unit tests for config loading |
| `tests/test_buffer.py` | Unit tests for subtitle buffer |
| `tests/test_server.py` | Unit tests for server broadcast logic |
| `tests/test_audio.py` | Unit tests for audio capture (mocked hardware) |
| `tests/test_transcriber.py` | Unit tests for transcription loop (mocked model) |

---

## Task 1: Project Setup

**Files:**
- Create: `requirements.txt`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create `requirements.txt`**

```
faster-whisper>=1.0.0
sounddevice>=0.4.6
pyaudiowpatch>=0.2.12
numpy>=1.24.0
aiohttp>=3.9.0
tomli>=2.0.0; python_version < "3.11"
pytest>=7.4.0
pytest-asyncio>=0.23.0
```

- [ ] **Step 2: Create `tests/__init__.py`**

Empty file — makes `tests/` a package.

```python
```

- [ ] **Step 3: Create `tests/conftest.py`**

```python
import sys
from pathlib import Path

# make root importable in all test modules
sys.path.insert(0, str(Path(__file__).parent.parent))
```

- [ ] **Step 4: Create `pytest.ini` at the project root**

```ini
[pytest]
asyncio_mode = auto
```

This tells pytest-asyncio 0.23+ to automatically handle `async def` test functions without needing `@pytest.mark.asyncio` decorators.

- [ ] **Step 5: Install dependencies**

```
pip install -r requirements.txt
```

Expected: all packages install without errors. `faster-whisper` may download model weights on first transcription run — that's fine for now.

- [ ] **Step 6: Commit**

```bash
git init
git add requirements.txt tests/__init__.py tests/conftest.py pytest.ini
git commit -m "chore: project setup with dependencies and test structure"
```

---

## Task 2: Config (`config.py`)

**Files:**
- Create: `config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_config.py
import pytest
from config import load_config


def test_load_config_creates_default_file(tmp_path):
    config_file = tmp_path / "config.toml"
    cfg = load_config(str(config_file))
    assert config_file.exists()
    assert cfg.audio.mode == "microphone"
    assert cfg.transcription.model == "base"
    assert cfg.display.lines == 3
    assert cfg.display.port == 8765
    assert cfg.translation.enabled is False


def test_load_config_reads_existing_file(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[audio]\nmode = "loopback"\n\n[transcription]\nmodel = "tiny"\nlanguage = "ja"\ndevice = "cpu"\n\n[display]\nlines = 2\nport = 9000\n\n[translation]\nenabled = false\n',
        encoding="utf-8",
    )
    cfg = load_config(str(config_file))
    assert cfg.audio.mode == "loopback"
    assert cfg.transcription.model == "tiny"
    assert cfg.transcription.language == "ja"
    assert cfg.display.lines == 2
    assert cfg.display.port == 9000


def test_load_config_partial_file_uses_defaults(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text('[audio]\nmode = "both"\n', encoding="utf-8")
    cfg = load_config(str(config_file))
    assert cfg.audio.mode == "both"
    assert cfg.transcription.model == "base"  # default
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_config.py -v
```

Expected: `ModuleNotFoundError: No module named 'config'`

- [ ] **Step 3: Implement `config.py`**

```python
import sys
from dataclasses import dataclass, field
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

[translation]
enabled = false
"""


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


@dataclass
class TranslationConfig:
    enabled: bool = False


@dataclass
class AppConfig:
    audio: AudioConfig = field(default_factory=AudioConfig)
    transcription: TranscriptionConfig = field(default_factory=TranscriptionConfig)
    display: DisplayConfig = field(default_factory=DisplayConfig)
    translation: TranslationConfig = field(default_factory=TranslationConfig)


def load_config(path: str = "config.toml") -> AppConfig:
    config_path = Path(path)
    if not config_path.exists():
        config_path.write_text(DEFAULT_CONFIG, encoding="utf-8")
        print(f"Created default config at {config_path}")

    with open(config_path, "rb") as f:
        data = tomllib.load(f)

    return AppConfig(
        audio=AudioConfig(**data.get("audio", {})),
        transcription=TranscriptionConfig(**data.get("transcription", {})),
        display=DisplayConfig(**data.get("display", {})),
        translation=TranslationConfig(**data.get("translation", {})),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_config.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add config.py tests/test_config.py
git commit -m "feat: config loading with auto-generated defaults"
```

---

## Task 3: Subtitle Buffer (`buffer.py`)

**Files:**
- Create: `buffer.py`
- Create: `tests/test_buffer.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_buffer.py
import pytest
from buffer import SubtitleBuffer


def test_push_appends_line():
    buf = SubtitleBuffer(max_lines=3)
    buf.push("hello")
    assert buf.get_lines() == ["hello"]


def test_push_multiple_lines():
    buf = SubtitleBuffer(max_lines=3)
    buf.push("line one")
    buf.push("line two")
    assert buf.get_lines() == ["line one", "line two"]


def test_push_trims_to_max_lines():
    buf = SubtitleBuffer(max_lines=3)
    buf.push("a")
    buf.push("b")
    buf.push("c")
    buf.push("d")
    assert buf.get_lines() == ["b", "c", "d"]


def test_get_lines_returns_copy():
    buf = SubtitleBuffer(max_lines=3)
    buf.push("hello")
    lines = buf.get_lines()
    lines.append("injected")
    assert buf.get_lines() == ["hello"]


def test_clear_empties_buffer():
    buf = SubtitleBuffer(max_lines=3)
    buf.push("hello")
    buf.clear()
    assert buf.get_lines() == []


def test_default_max_lines_is_three():
    buf = SubtitleBuffer()
    for i in range(5):
        buf.push(f"line {i}")
    assert len(buf.get_lines()) == 3
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_buffer.py -v
```

Expected: `ModuleNotFoundError: No module named 'buffer'`

- [ ] **Step 3: Implement `buffer.py`**

```python
class SubtitleBuffer:
    def __init__(self, max_lines: int = 3):
        self._lines: list[str] = []
        self._max_lines = max_lines

    def push(self, text: str) -> None:
        self._lines.append(text)
        if len(self._lines) > self._max_lines:
            self._lines = self._lines[-self._max_lines:]

    def get_lines(self) -> list[str]:
        return list(self._lines)

    def clear(self) -> None:
        self._lines = []
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_buffer.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add buffer.py tests/test_buffer.py
git commit -m "feat: rolling subtitle line buffer"
```

---

## Task 4: Overlay HTML (`overlay.html`)

**Files:**
- Create: `overlay.html`

No unit tests — this is a static asset. Verified visually in Task 9 (smoke test).

- [ ] **Step 1: Create `overlay.html`**

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
      font-family: Arial, sans-serif;
    }

    #subtitles {
      max-width: 90%;
      text-align: center;
    }

    .line {
      display: block;
      background: rgba(0, 0, 0, 0.75);
      color: #ffffff;
      font-size: 36px;
      font-weight: bold;
      padding: 6px 18px;
      border-radius: 8px;
      margin: 4px auto;
      text-shadow: 1px 1px 3px rgba(0, 0, 0, 0.9);
      max-width: fit-content;
    }
  </style>
</head>
<body>
  <div id="subtitles"></div>
  <script>
    const container = document.getElementById('subtitles');

    function escapeHtml(text) {
      return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
    }

    function render(lines) {
      container.innerHTML = lines
        .map(line => `<span class="line">${escapeHtml(line)}</span>`)
        .join('');
    }

    function connect() {
      const ws = new WebSocket(`ws://${location.host}/ws`);

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          render(data.lines || []);
        } catch (e) {
          console.error('Bad message', e);
        }
      };

      ws.onclose = () => {
        setTimeout(connect, 1000);
      };

      ws.onerror = () => {
        ws.close();
      };
    }

    connect();
  </script>
</body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add overlay.html
git commit -m "feat: OBS browser source overlay HTML"
```

---

## Task 5: WebSocket Server (`server.py`)

**Files:**
- Create: `server.py`
- Create: `tests/test_server.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_server.py
import asyncio
import json
import queue
import pytest


@pytest.mark.asyncio
async def test_get_root_serves_overlay():
    from aiohttp.test_utils import TestClient, TestServer
    from server import create_app

    subtitle_queue = queue.Queue()
    app = await create_app(subtitle_queue)

    async with TestClient(TestServer(app)) as client:
        resp = await client.get("/")
        assert resp.status == 200
        text = await resp.text()
        assert "<div id=\"subtitles\">" in text


@pytest.mark.asyncio
async def test_websocket_receives_broadcast():
    from aiohttp.test_utils import TestClient, TestServer
    from server import create_app

    subtitle_queue = queue.Queue()
    app = await create_app(subtitle_queue)

    async with TestClient(TestServer(app)) as client:
        async with client.ws_connect("/ws") as ws:
            subtitle_queue.put({"lines": ["hello world"]})
            msg = await asyncio.wait_for(ws.receive(), timeout=2.0)
            data = json.loads(msg.data)
            assert data["lines"] == ["hello world"]


@pytest.mark.asyncio
async def test_multiple_clients_receive_broadcast():
    from aiohttp.test_utils import TestClient, TestServer
    from server import create_app

    subtitle_queue = queue.Queue()
    app = await create_app(subtitle_queue)

    async with TestClient(TestServer(app)) as client:
        async with client.ws_connect("/ws") as ws1:
            async with client.ws_connect("/ws") as ws2:
                subtitle_queue.put({"lines": ["broadcast test"]})
                msg1 = await asyncio.wait_for(ws1.receive(), timeout=2.0)
                msg2 = await asyncio.wait_for(ws2.receive(), timeout=2.0)
                assert json.loads(msg1.data)["lines"] == ["broadcast test"]
                assert json.loads(msg2.data)["lines"] == ["broadcast test"]
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_server.py -v
```

Expected: `ModuleNotFoundError: No module named 'server'`

- [ ] **Step 3: Implement `server.py`**

```python
import asyncio
import json
import queue
from pathlib import Path

from aiohttp import web, WSMsgType


async def create_app(subtitle_queue: queue.Queue) -> web.Application:
    clients: set[web.WebSocketResponse] = set()
    overlay_path = Path(__file__).parent / "overlay.html"

    async def index(request: web.Request) -> web.FileResponse:
        return web.FileResponse(overlay_path)

    async def websocket_handler(request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        clients.add(ws)
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
            clients -= dead

    app = web.Application()
    app.router.add_get("/", index)
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

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_server.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add server.py tests/test_server.py
git commit -m "feat: aiohttp HTTP and WebSocket server with subtitle broadcast"
```

---

## Task 6: Audio Capture (`audio.py`)

**Files:**
- Create: `audio.py`
- Create: `tests/test_audio.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_audio.py
import queue
import threading
import numpy as np
import pytest
from unittest.mock import patch, MagicMock


def test_microphone_capture_puts_chunk_in_queue():
    from audio import start_microphone_capture, SAMPLE_RATE, CHUNK_SAMPLES

    audio_queue = queue.Queue()
    stop_event = threading.Event()

    fake_chunk = np.zeros(CHUNK_SAMPLES, dtype=np.float32)

    def fake_stream_context(*args, **kwargs):
        class FakeStream:
            def __enter__(self):
                cb = kwargs.get("callback")
                if cb:
                    cb(fake_chunk.reshape(-1, 1), CHUNK_SAMPLES, None, None)
                return self

            def __exit__(self, *a):
                pass

        return FakeStream()

    def fake_sleep(ms):
        stop_event.set()

    with patch("audio.sd.InputStream", fake_stream_context), \
         patch("audio.sd.sleep", fake_sleep):
        start_microphone_capture(audio_queue, "default", stop_event)

    assert not audio_queue.empty()
    chunk = audio_queue.get()
    assert chunk.shape == (CHUNK_SAMPLES,)
    assert chunk.dtype == np.float32


def test_list_input_devices_returns_list():
    from audio import list_input_devices

    fake_devices = [
        {"name": "Mic 1", "max_input_channels": 2, "max_output_channels": 0},
        {"name": "Speaker", "max_input_channels": 0, "max_output_channels": 2},
        {"name": "Mic 2", "max_input_channels": 1, "max_output_channels": 0},
    ]

    with patch("audio.sd.query_devices", return_value=fake_devices):
        devices = list_input_devices()

    assert len(devices) == 2
    names = [d[1] for d in devices]
    assert "Mic 1" in names
    assert "Mic 2" in names
    assert "Speaker" not in names


def test_loopback_capture_resamples_and_queues():
    from audio import CHUNK_SAMPLES

    # Minimal smoke test: if pyaudiowpatch is present, function is importable
    try:
        from audio import start_loopback_capture
    except ImportError:
        pytest.skip("pyaudiowpatch not installed")

    # Full loopback capture test requires real WASAPI — tested manually
    assert callable(start_loopback_capture)
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_audio.py -v
```

Expected: `ModuleNotFoundError: No module named 'audio'`

- [ ] **Step 3: Implement `audio.py`**

```python
import queue
import threading
import time
from typing import Union

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
CHUNK_SECONDS = 3
CHUNK_SAMPLES = SAMPLE_RATE * CHUNK_SECONDS


def list_input_devices() -> list[tuple[int, str]]:
    devices = sd.query_devices()
    return [(i, d["name"]) for i, d in enumerate(devices) if d["max_input_channels"] > 0]


def list_output_devices() -> list[tuple[int, str]]:
    devices = sd.query_devices()
    return [(i, d["name"]) for i, d in enumerate(devices) if d["max_output_channels"] > 0]


def start_microphone_capture(
    audio_queue: queue.Queue,
    device: Union[str, int] = "default",
    stop_event: threading.Event = None,
) -> None:
    buffer: list[np.ndarray] = []

    def callback(indata: np.ndarray, frames: int, time_info, status) -> None:
        buffer.append(indata[:, 0].copy())
        total = sum(len(b) for b in buffer)
        if total >= CHUNK_SAMPLES:
            chunk = np.concatenate(buffer)[:CHUNK_SAMPLES].astype(np.float32)
            audio_queue.put(chunk)
            buffer.clear()

    device_idx = None if device == "default" else int(device)

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
        device=device_idx,
        callback=callback,
    ):
        while not (stop_event and stop_event.is_set()):
            sd.sleep(100)


def _resample(audio: np.ndarray, from_rate: int, to_rate: int) -> np.ndarray:
    if from_rate == to_rate:
        return audio
    new_length = int(len(audio) * to_rate / from_rate)
    return np.interp(
        np.linspace(0, len(audio), new_length),
        np.arange(len(audio)),
        audio,
    ).astype(np.float32)


def start_loopback_capture(
    audio_queue: queue.Queue,
    device: Union[str, int] = "default",
    stop_event: threading.Event = None,
) -> None:
    try:
        import pyaudiowpatch as pyaudio
    except ImportError:
        raise RuntimeError("pyaudiowpatch is required for loopback capture. Run: pip install pyaudiowpatch")

    pa = pyaudio.PyAudio()
    try:
        wasapi_info = pa.get_host_api_info_by_type(pyaudio.paWASAPI)

        if device == "default":
            default_out_idx = wasapi_info["defaultOutputDevice"]
            default_out = pa.get_device_info_by_index(default_out_idx)
            loopback_idx = None
            for i in range(pa.get_device_count()):
                dev = pa.get_device_info_by_index(i)
                if dev.get("isLoopbackDevice") and dev["name"].startswith(default_out["name"]):
                    loopback_idx = i
                    break
            if loopback_idx is None:
                devs = [
                    f"  [{i}] {pa.get_device_info_by_index(i)['name']}"
                    for i in range(pa.get_device_count())
                    if pa.get_device_info_by_index(i).get("isLoopbackDevice")
                ]
                raise RuntimeError(
                    "No loopback device found for default output. Available loopback devices:\n"
                    + "\n".join(devs)
                )
        else:
            loopback_idx = int(device)

        dev_info = pa.get_device_info_by_index(loopback_idx)
        src_rate = int(dev_info["defaultSampleRate"])
        channels = int(dev_info["maxInputChannels"])
        buffer: list[np.ndarray] = []

        def callback(in_data, frame_count, time_info, status):
            raw = np.frombuffer(in_data, dtype=np.float32)
            if channels > 1:
                raw = raw.reshape(-1, channels).mean(axis=1)
            resampled = _resample(raw, src_rate, SAMPLE_RATE)
            buffer.append(resampled)
            total = sum(len(b) for b in buffer)
            if total >= CHUNK_SAMPLES:
                chunk = np.concatenate(buffer)[:CHUNK_SAMPLES]
                audio_queue.put(chunk)
                buffer.clear()
            return (None, pyaudio.paContinue)

        stream = pa.open(
            format=pyaudio.paFloat32,
            channels=channels,
            rate=src_rate,
            input=True,
            input_device_index=loopback_idx,
            stream_callback=callback,
            frames_per_buffer=1024,
        )
        stream.start_stream()

        while not (stop_event and stop_event.is_set()):
            time.sleep(0.1)

        stream.stop_stream()
        stream.close()
    finally:
        pa.terminate()
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_audio.py -v
```

Expected: 3 passed (or 2 passed + 1 skipped if pyaudiowpatch not installed).

- [ ] **Step 5: Commit**

```bash
git add audio.py tests/test_audio.py
git commit -m "feat: mic and loopback audio capture"
```

---

## Task 7: Transcription (`transcriber.py`)

**Files:**
- Create: `transcriber.py`
- Create: `tests/test_transcriber.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_transcriber.py
import queue
import threading
import numpy as np
import pytest
from unittest.mock import MagicMock, patch


def _make_mock_model(segments_text: list[str]):
    fake_segment = MagicMock()
    model = MagicMock()
    segments = [MagicMock(text=f" {t} ") for t in segments_text]
    model.transcribe.return_value = (iter(segments), MagicMock())
    return model


def test_transcriber_pushes_text_to_subtitle_queue():
    from transcriber import start_transcription
    from buffer import SubtitleBuffer

    audio_queue = queue.Queue()
    subtitle_queue = queue.Queue()
    stop_event = threading.Event()
    buf = SubtitleBuffer(max_lines=3)

    audio_chunk = np.zeros(48000, dtype=np.float32)
    audio_queue.put(audio_chunk)

    mock_model = _make_mock_model(["hello world"])

    def fake_load(*args, **kwargs):
        return mock_model

    with patch("transcriber.WhisperModel", fake_load):
        t = threading.Thread(
            target=start_transcription,
            args=(audio_queue, subtitle_queue, buf, "base", "en", "cpu", stop_event),
            daemon=True,
        )
        t.start()
        result = subtitle_queue.get(timeout=3.0)
        stop_event.set()
        t.join(timeout=2)

    assert result == {"lines": ["hello world"]}
    assert buf.get_lines() == ["hello world"]


def test_transcriber_skips_empty_segments():
    from transcriber import start_transcription
    from buffer import SubtitleBuffer

    audio_queue = queue.Queue()
    subtitle_queue = queue.Queue()
    stop_event = threading.Event()
    buf = SubtitleBuffer(max_lines=3)

    audio_queue.put(np.zeros(48000, dtype=np.float32))

    mock_model = _make_mock_model(["   ", ""])

    def fake_load(*args, **kwargs):
        return mock_model

    with patch("transcriber.WhisperModel", fake_load):
        t = threading.Thread(
            target=start_transcription,
            args=(audio_queue, subtitle_queue, buf, "base", "en", "cpu", stop_event),
            daemon=True,
        )
        t.start()
        stop_event.set()
        t.join(timeout=2)

    assert subtitle_queue.empty()
    assert buf.get_lines() == []


def test_transcriber_uses_auto_language():
    from transcriber import start_transcription
    from buffer import SubtitleBuffer

    audio_queue = queue.Queue()
    subtitle_queue = queue.Queue()
    stop_event = threading.Event()
    buf = SubtitleBuffer()

    audio_queue.put(np.zeros(48000, dtype=np.float32))
    mock_model = _make_mock_model(["test"])

    def fake_load(*args, **kwargs):
        return mock_model

    with patch("transcriber.WhisperModel", fake_load):
        t = threading.Thread(
            target=start_transcription,
            args=(audio_queue, subtitle_queue, buf, "base", "auto", "cpu", stop_event),
            daemon=True,
        )
        t.start()
        subtitle_queue.get(timeout=3.0)
        stop_event.set()
        t.join(timeout=2)

    call_kwargs = mock_model.transcribe.call_args[1]
    assert call_kwargs.get("language") is None
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_transcriber.py -v
```

Expected: `ModuleNotFoundError: No module named 'transcriber'`

- [ ] **Step 3: Implement `transcriber.py`**

```python
import queue
import threading
from typing import Optional

import numpy as np
from faster_whisper import WhisperModel


def start_transcription(
    audio_queue: queue.Queue,
    subtitle_queue: queue.Queue,
    subtitle_buffer,
    model_size: str,
    language: str,
    device: str,
    stop_event: threading.Event,
) -> None:
    compute_type = "float16" if device == "cuda" else "int8"
    model = WhisperModel(model_size, device=device, compute_type=compute_type)

    lang: Optional[str] = None if language == "auto" else language

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
        if text:
            subtitle_buffer.push(text)
            subtitle_queue.put({"lines": subtitle_buffer.get_lines()})
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_transcriber.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add transcriber.py tests/test_transcriber.py
git commit -m "feat: faster-whisper transcription thread"
```

---

## Task 8: Entry Point (`main.py`)

**Files:**
- Create: `main.py`

- [ ] **Step 1: Implement `main.py`**

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
        audio_desc = f"microphone + loopback"

    print("\n[Subtitle Everything]")
    print(f"  Model:    {config.transcription.model} ({config.transcription.device})")
    print(f"  Audio:    {audio_desc}")
    print(f"  Language: {config.transcription.language}")
    print(f"  Overlay:  http://localhost:{config.display.port}")
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
    app = await create_app(subtitle_queue)
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
        args=(audio_queue, subtitle_queue, subtitle_buffer,
              config.transcription.model, config.transcription.language,
              config.transcription.device, stop_event),
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

- [ ] **Step 2: Run all tests to verify nothing broke**

```
pytest tests/ -v
```

Expected: all previously passing tests still pass.

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "feat: main entry point wiring all components together"
```

---

## Task 9: Smoke Test (Manual)

This task verifies the full end-to-end pipeline runs correctly.

- [ ] **Step 1: Run the app**

```
python main.py
```

Expected output:
```
[Subtitle Everything]
  Model:    base (cpu)
  Audio:    microphone (default)
  Language: en
  Overlay:  http://localhost:8765

Add this URL as a Browser Source in OBS.
Press Ctrl+C to stop.
```

The model downloads on first run (~150MB). Wait for the download to complete.

- [ ] **Step 2: Open the overlay in a browser**

Navigate to `http://localhost:8765` in Chrome or Edge.

Expected: blank transparent-background page (subtitles appear when speech is detected).

- [ ] **Step 3: Speak into the microphone**

Say a sentence clearly. Within ~3 seconds, subtitle text should appear at the bottom of the page.

- [ ] **Step 4: Test in OBS**

In OBS: Sources → Add → Browser Source → URL: `http://localhost:8765`, Width: 1920, Height: 1080. Verify subtitles appear overlaid on your scene.

- [ ] **Step 5: Test loopback mode**

Edit `config.toml`, set `mode = "loopback"`. Restart the app. Play audio through speakers/headphones. Verify the playing audio gets transcribed.

- [ ] **Step 6: Test `both` mode**

Set `mode = "both"`. Restart. Speak and play audio simultaneously. Both sources should produce subtitle lines.

- [ ] **Step 7: Verify Ctrl+C shuts down cleanly**

Press Ctrl+C. Expected:
```
Shutting down...
Stopped.
```
No tracebacks.

- [ ] **Step 8: Final commit**

```bash
git add .
git commit -m "feat: subtitle everything — complete working implementation"
```

---

## Notes for Future Translation Support

When adding LibreTranslate:
1. Add `translator.py` with a `translate(text, source, target, url)` function
2. Add `url`, `source_lang`, `target_lang` to `[translation]` in config
3. In `transcriber.py`, after `subtitle_buffer.push(text)`, call translation and push a second line
4. The overlay already handles multi-line — no HTML changes needed
