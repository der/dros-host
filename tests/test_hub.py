import tempfile
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from dros import Bus
from dros._transport import ServerTransport


@pytest.fixture
def bus_with_hub() -> Generator[Bus, Any, Any]:
    transport = ServerTransport(
        host="127.0.0.1", port=0, ping_timeout=1, ping_interval=1
    )
    bus = Bus(transport=transport, max_workers=4)
    bus.start()
    yield bus
    bus.stop()


class TestHub:
    def test_remote_publish_to_local(self, bus_with_hub: Bus) -> None:
        bus = bus_with_hub
        received: list[dict[str, Any]] = []
        event = threading.Event()

        def callback(m: dict[str, Any]) -> None:
            received.append(m)
            event.set()

        bus.subscribe("test", callback, mode="event")

        import socketio

        sio_client = socketio.Client()
        got = threading.Event()

        @sio_client.on("connect")
        def on_connect() -> None:
            got.set()

        port = bus._transport.port
        sio_client.connect(
            f"http://127.0.0.1:{port}",
            transports=["websocket"],
            wait_timeout=5,
        )
        assert got.wait(timeout=3)

        sio_client.emit("publish", {"topic": "test", "message": {"hello": "world"}})
        assert event.wait(timeout=2)
        assert received == [{"hello": "world"}]
        sio_client.disconnect()

    def test_remote_subscribe_receives_publish(self, bus_with_hub: Bus) -> None:
        bus = bus_with_hub
        import socketio

        sio_client = socketio.Client()
        received: list[dict[str, Any]] = []
        got = threading.Event()

        @sio_client.on("connect")
        def on_connect() -> None:
            got.set()

        @sio_client.on("publish")
        def on_publish(data: dict[str, Any]) -> None:
            received.append(data["message"])

        port = bus._transport.port
        sio_client.connect(
            f"http://127.0.0.1:{port}",
            transports=["websocket"],
            wait_timeout=5,
        )
        assert got.wait(timeout=3)

        sio_client.emit("subscribe", "sensors")
        time.sleep(0.1)

        bus.publish("sensors", {"temp": 25.5})
        time.sleep(0.2)
        assert received == [{"temp": 25.5}]
        sio_client.disconnect()

    def test_remote_disconnect_cleans_up(self, bus_with_hub: Bus) -> None:
        bus = bus_with_hub
        import socketio

        sio_client = socketio.Client()
        got = threading.Event()

        @sio_client.on("connect")
        def on_connect() -> None:
            got.set()

        port = bus._transport.port
        sio_client.connect(
            f"http://127.0.0.1:{port}",
            transports=["websocket"],
            wait_timeout=5,
        )
        assert got.wait(timeout=3)

        sio_client.emit("subscribe", "sensors")
        time.sleep(0.1)

        transport = bus._transport
        assert isinstance(transport, ServerTransport)
        assert "sensors" in transport._remote_subs

        sio_client.disconnect()
        time.sleep(0.1)

        assert "sensors" not in transport._remote_subs

    def test_bus_without_hub(self) -> None:
        bus = Bus()
        received: list[dict[str, Any]] = []
        event = threading.Event()

        def callback(m: dict[str, Any]) -> None:
            received.append(m)
            event.set()

        bus.subscribe("test", callback, mode="event")
        bus.start()
        bus.publish("test", {"x": 1})
        assert event.wait(timeout=2)
        assert received == [{"x": 1}]
        bus.stop()

    def test_static_file_serving(self) -> None:
        dashboard_html = "<html><body>Dashboard</body></html>"
        with tempfile.TemporaryDirectory() as tmpdir:
            dash_path = Path(tmpdir) / "dashboard.html"
            dash_path.write_text(dashboard_html)

            transport = ServerTransport(
                host="127.0.0.1",
                port=0,
                ping_timeout=1,
                ping_interval=1,
                static_dir=tmpdir,
            )
            bus = Bus(transport=transport, max_workers=2)
            bus.start()
            try:
                url = f"http://127.0.0.1:{transport.port}/dashboard"
                with urllib.request.urlopen(url, timeout=3) as resp:  # noqa: S310
                    assert resp.status == 200
                    assert resp.headers.get("Content-Type") == "text/html"
                    body = resp.read().decode("utf-8")
                    assert body == dashboard_html
            finally:
                bus.stop()

    def test_static_dir_not_configured_returns_404(self) -> None:
        transport = ServerTransport(
            host="127.0.0.1",
            port=0,
            ping_timeout=1,
            ping_interval=1,
        )
        bus = Bus(transport=transport, max_workers=2)
        bus.start()
        try:
            url = f"http://127.0.0.1:{transport.port}/dashboard"
            with pytest.raises(urllib.error.HTTPError) as exc_info:
                urllib.request.urlopen(url, timeout=3)  # noqa: S310
            assert exc_info.value.code == 404
        finally:
            bus.stop()
