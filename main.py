import asyncio
import queue
import threading

from aiohttp import web

from audio import start_microphone_capture, start_loopback_capture
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
