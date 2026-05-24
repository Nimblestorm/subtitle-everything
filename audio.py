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
