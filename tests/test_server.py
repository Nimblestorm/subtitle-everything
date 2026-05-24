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
