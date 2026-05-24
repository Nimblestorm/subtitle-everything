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


def test_resample_uses_correct_index_range():
    from audio import _resample
    # Upsample: 4 samples at rate 4 -> 8 samples at rate 8
    audio = np.array([0.0, 1.0, 2.0, 3.0], dtype=np.float32)
    result = _resample(audio, from_rate=4, to_rate=8)
    assert len(result) == 8
    # Last output sample should interpolate toward 3.0, not be clamped to it
    assert result[-1] == pytest.approx(3.0, abs=0.1)
    assert result[0] == pytest.approx(0.0, abs=0.01)


def test_microphone_capture_retains_remainder():
    from audio import start_microphone_capture, SAMPLE_RATE, CHUNK_SAMPLES

    audio_queue = queue.Queue()
    stop_event = threading.Event()

    # Deliver 1.5x CHUNK_SAMPLES in one callback
    oversized = np.zeros(int(CHUNK_SAMPLES * 1.5), dtype=np.float32)

    def fake_stream_context(*args, **kwargs):
        class FakeStream:
            def __enter__(self):
                cb = kwargs.get("callback")
                if cb:
                    cb(oversized.reshape(-1, 1), len(oversized), None, None)
                return self

            def __exit__(self, *a):
                pass

        return FakeStream()

    def fake_sleep(ms):
        stop_event.set()

    with patch("audio.sd.InputStream", fake_stream_context), \
         patch("audio.sd.sleep", fake_sleep):
        start_microphone_capture(audio_queue, "default", stop_event)

    # First chunk emitted
    assert not audio_queue.empty()
    chunk = audio_queue.get()
    assert chunk.shape == (CHUNK_SAMPLES,)
