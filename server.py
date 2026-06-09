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
