from __future__ import annotations

from unittest.mock import patch

from hotdata.exceptions import ApiException

from hotdata_runtime.client import HotdataClient
from hotdata_runtime.health import workspace_health_lines


def test_workspace_health_ok():
    client = HotdataClient("k", "ws", host="https://api.hotdata.dev")
    listing = type("L", (), {"connections": [object()]})()

    class FakeConnectionsApi:
        def list_connections(self):
            return listing

    with patch.object(client, "connections", return_value=FakeConnectionsApi()):
        ok, parts = workspace_health_lines(client)
    assert ok is True
    assert any("reachable" in p for p in parts)


def test_workspace_health_api_error():
    client = HotdataClient("k", "ws", host="https://api.hotdata.dev")

    class Boom:
        def list_connections(self):
            raise ApiException(status=500, reason="nope")

    with patch.object(client, "connections", return_value=Boom()):
        ok, parts = workspace_health_lines(client)
    assert ok is False
    assert parts == ["nope"]
