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
