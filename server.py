import asyncio
import json
import queue
from pathlib import Path

from aiohttp import web


async def create_app(subtitle_queue: queue.Queue) -> web.Application:
    clients: set[web.WebSocketResponse] = set()
    overlay_path = Path(__file__).parent / "overlay.html"

    if not overlay_path.is_file():
        raise RuntimeError(f"overlay.html not found at {overlay_path}")

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
            clients.difference_update(dead)

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
