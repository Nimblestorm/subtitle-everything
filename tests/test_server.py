import asyncio
import json
import os
import queue
import tempfile

import pytest
from config import AppConfig


def _make_app(config=None):
    from server import create_app
    if config is None:
        config = AppConfig()
    return create_app(queue.Queue(), config)


@pytest.mark.asyncio
async def test_get_root_serves_overlay():
    from aiohttp.test_utils import TestClient, TestServer
    app = await _make_app()
    async with TestClient(TestServer(app)) as client:
        resp = await client.get("/")
        assert resp.status == 200
        text = await resp.text()
        assert 'id="subtitles-mic"' in text
        assert 'id="subtitles-loopback"' in text


@pytest.mark.asyncio
async def test_get_settings_serves_settings_page():
    from aiohttp.test_utils import TestClient, TestServer
    app = await _make_app()
    async with TestClient(TestServer(app)) as client:
        resp = await client.get("/settings")
        assert resp.status == 200
        assert "api/config" in await resp.text()


@pytest.mark.asyncio
async def test_get_api_config_returns_json():
    from aiohttp.test_utils import TestClient, TestServer
    config = AppConfig()
    app = await _make_app(config)
    async with TestClient(TestServer(app)) as client:
        resp = await client.get("/api/config")
        assert resp.status == 200
        data = await resp.json()
        assert data["display"]["font_family"] == "Arial"
        assert data["display"]["font_size"] == 36
        assert data["display"]["mic_color"] == "#ffffff"
        assert data["display"]["mic_position"] == "bottom"
        assert data["display"]["loopback_color"] == "#00d4ff"
        assert data["display"]["loopback_position"] == "top"
        assert data["transcription"]["mic_model"] == "base"
        assert data["transcription"]["loopback_model"] == "base"
        assert data["translation"]["target_lang"] == "es"


@pytest.mark.asyncio
async def test_post_api_config_updates_and_broadcasts():
    from aiohttp.test_utils import TestClient, TestServer
    config = AppConfig()
    with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as f:
        config_path = f.name
    try:
        from server import create_app
        app = await create_app(queue.Queue(), config, config_path)
        async with TestClient(TestServer(app)) as client:
            async with client.ws_connect("/ws") as ws:
                await asyncio.wait_for(ws.receive(), timeout=2.0)  # consume initial config
                resp = await client.post("/api/config", json={
                    "display": {"font_size": 48, "font_color": "#ff0000"}
                })
                assert resp.status == 200
                data = await resp.json()
                assert data["display"]["font_size"] == 48
                assert data["display"]["font_color"] == "#ff0000"
                assert data["requires_restart"] is False
                msg = await asyncio.wait_for(ws.receive(), timeout=2.0)
                cfg_msg = json.loads(msg.data)
                assert cfg_msg["type"] == "config"
                assert cfg_msg["display"]["font_size"] == 48
    finally:
        os.unlink(config_path)


@pytest.mark.asyncio
async def test_post_api_config_invalid_returns_400():
    from aiohttp.test_utils import TestClient, TestServer
    app = await _make_app()
    async with TestClient(TestServer(app)) as client:
        resp = await client.post("/api/config", json={"display": {"font_size": 2}})
        assert resp.status == 400
        data = await resp.json()
        assert "error" in data


@pytest.mark.asyncio
async def test_post_api_config_requires_restart_for_audio_change():
    from aiohttp.test_utils import TestClient, TestServer
    with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as f:
        config_path = f.name
    try:
        from server import create_app
        app = await create_app(queue.Queue(), AppConfig(), config_path)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post("/api/config", json={"audio": {"mode": "loopback"}})
            assert resp.status == 200
            data = await resp.json()
            assert data["requires_restart"] is True
    finally:
        os.unlink(config_path)


@pytest.mark.asyncio
async def test_websocket_receives_config_on_connect():
    from aiohttp.test_utils import TestClient, TestServer
    app = await _make_app()
    async with TestClient(TestServer(app)) as client:
        async with client.ws_connect("/ws") as ws:
            msg = await asyncio.wait_for(ws.receive(), timeout=2.0)
            data = json.loads(msg.data)
            assert data["type"] == "config"
            assert data["display"]["font_family"] == "Arial"


@pytest.mark.asyncio
async def test_websocket_config_includes_source_fields():
    from aiohttp.test_utils import TestClient, TestServer
    app = await _make_app()
    async with TestClient(TestServer(app)) as client:
        async with client.ws_connect("/ws") as ws:
            msg = await asyncio.wait_for(ws.receive(), timeout=2.0)
            data = json.loads(msg.data)
            assert data["type"] == "config"
            assert data["display"]["mic_color"] == "#ffffff"
            assert data["display"]["mic_position"] == "bottom"
            assert data["display"]["loopback_color"] == "#00d4ff"
            assert data["display"]["loopback_position"] == "top"
            assert data["display"]["audio_mode"] == "microphone"


@pytest.mark.asyncio
async def test_websocket_receives_subtitle_broadcast():
    from aiohttp.test_utils import TestClient, TestServer
    subtitle_queue = queue.Queue()
    from server import create_app
    app = await create_app(subtitle_queue, AppConfig())
    async with TestClient(TestServer(app)) as client:
        async with client.ws_connect("/ws") as ws:
            await asyncio.wait_for(ws.receive(), timeout=2.0)  # config message
            subtitle_queue.put({"type": "subtitle", "lines": ["hello"], "translated_lines": []})
            msg = await asyncio.wait_for(ws.receive(), timeout=2.0)
            data = json.loads(msg.data)
            assert data["type"] == "subtitle"
            assert data["lines"] == ["hello"]


@pytest.mark.asyncio
async def test_post_api_config_rejects_cross_origin():
    from aiohttp.test_utils import TestClient, TestServer
    app = await _make_app()
    async with TestClient(TestServer(app)) as client:
        resp = await client.post(
            "/api/config",
            json={},
            headers={"Origin": "https://evil.com"},
        )
        assert resp.status == 403


@pytest.mark.asyncio
async def test_multiple_clients_receive_broadcast():
    from aiohttp.test_utils import TestClient, TestServer
    subtitle_queue = queue.Queue()
    from server import create_app
    app = await create_app(subtitle_queue, AppConfig())
    async with TestClient(TestServer(app)) as client:
        async with client.ws_connect("/ws") as ws1:
            async with client.ws_connect("/ws") as ws2:
                await asyncio.wait_for(ws1.receive(), timeout=2.0)
                await asyncio.wait_for(ws2.receive(), timeout=2.0)
                subtitle_queue.put({"type": "subtitle", "lines": ["broadcast"], "translated_lines": []})
                msg1 = await asyncio.wait_for(ws1.receive(), timeout=2.0)
                msg2 = await asyncio.wait_for(ws2.receive(), timeout=2.0)
                assert json.loads(msg1.data)["lines"] == ["broadcast"]
                assert json.loads(msg2.data)["lines"] == ["broadcast"]
