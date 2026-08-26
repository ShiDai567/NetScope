"""WS consumer 集成测试（Channels ApplicationCommunicator）。"""

import json

import pytest
from channels.testing import WebsocketCommunicator

from core.redis_store import RedisStore, set_store

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def fake_store():
    import fakeredis

    client = fakeredis.FakeStrictRedis(decode_responses=True)
    store = RedisStore(client=client)
    set_store(store)
    yield store
    set_store(None)


async def test_ws_handshake_and_snapshot(fake_store):
    from config.asgi import application

    communicator = WebsocketCommunicator(application, "/ws/network/")
    connected, _ = await communicator.connect()
    assert connected

    hello = json.loads(await communicator.receive_from())
    assert hello["type"] == "hello"
    assert set(hello["data"]) >= {"server_time", "seq", "mode", "uptime"}

    snapshot = json.loads(await communicator.receive_from())
    assert snapshot["type"] == "snapshot"
    assert set(snapshot["data"]) >= {
        "total",
        "active",
        "closed",
        "failed",
        "lost",
        "directions",
        "protocols",
        "apps",
        "bandwidth",
        "loss_rate",
        "avg_latency_ms",
        "system",
        "mode",
        "uptime",
    }
    await communicator.disconnect()


async def test_ws_ping_pong(fake_store):
    from config.asgi import application

    communicator = WebsocketCommunicator(application, "/ws/network/")
    connected, _ = await communicator.connect()
    assert connected
    await communicator.receive_from()  # hello
    await communicator.receive_from()  # snapshot

    await communicator.send_to(text_data=json.dumps({"type": "ping"}))
    pong = json.loads(await communicator.receive_from())
    assert pong["type"] == "pong"
    await communicator.disconnect()


async def test_ws_unknown_type_ignored(fake_store):
    from config.asgi import application

    communicator = WebsocketCommunicator(application, "/ws/network/")
    connected, _ = await communicator.connect()
    assert connected
    await communicator.receive_from()
    await communicator.receive_from()

    await communicator.send_to(text_data=json.dumps({"type": "whatever"}))
    # 未知类型静默忽略：发送 ping 验证连接仍存活
    await communicator.send_to(text_data=json.dumps({"type": "ping"}))
    pong = json.loads(await communicator.receive_from(timeout=5))
    assert pong["type"] == "pong"
    await communicator.disconnect()
