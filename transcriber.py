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
