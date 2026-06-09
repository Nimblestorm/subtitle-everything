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
