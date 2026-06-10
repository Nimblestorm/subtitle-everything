import queue
import threading
from concurrent.futures import ThreadPoolExecutor
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
    source: str = "mic",
) -> None:
    compute_type = "float16" if config.transcription.device == "cuda" else "int8"
    model_name = config.transcription.mic_model if source == "mic" else config.transcription.loopback_model
    model = WhisperModel(
        model_name,
        device=config.transcription.device,
        compute_type=compute_type,
    )
    while not stop_event.is_set():
        try:
            audio_chunk: np.ndarray = audio_queue.get(timeout=0.5)
        except queue.Empty:
            continue

        # snapshot mutable config fields used in this iteration
        max_chars = config.display.max_chars_per_line
        lang_setting = config.transcription.language
        translation_cfg = config.translation

        segments, _ = model.transcribe(
            audio_chunk,
            language=None if lang_setting == "auto" else lang_setting,
            beam_size=1,
            vad_filter=True,
        )
        text = " ".join(seg.text.strip() for seg in segments).strip()
        if not text:
            continue

        for line in split_to_lines(text, max_chars):
            subtitle_buffer.push(line)

        original_lines = subtitle_buffer.get_lines()
        translated_lines: list[str] = []

        if translation_cfg.enabled:
            with ThreadPoolExecutor(max_workers=min(len(original_lines), 4)) as pool:
                translated = list(pool.map(lambda line: translate(line, translation_cfg), original_lines))
            if translation_cfg.dual_language:
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
