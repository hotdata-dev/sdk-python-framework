from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from hotdata_runtime.env import normalize_host, pick_workspace, resolve_workspace_selection
from hotdata_runtime.client import HotdataClient


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://api.hotdata.dev", "https://api.hotdata.dev"),
        ("https://api.hotdata.dev/", "https://api.hotdata.dev"),
        ("https://api.hotdata.dev/v1", "https://api.hotdata.dev"),
        ("https://api.hotdata.dev/v1/", "https://api.hotdata.dev"),
        ("http://localhost:8000/v1", "http://localhost:8000"),
        ("http://localhost:8000", "http://localhost:8000"),
    ],
)
def test_normalize_host(raw: str, expected: str):
    assert normalize_host(raw) == expected


def test_pick_workspace_prefers_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HOTDATA_WORKSPACE", "ws_explicit")
    assert pick_workspace("k", "https://api.hotdata.dev", None) == "ws_explicit"


def test_resolve_workspace_selection_prefers_env_without_listing(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("HOTDATA_WORKSPACE", "ws_explicit")
    with patch("hotdata_runtime.env.list_workspaces") as listing:
        resolved = resolve_workspace_selection(
            "k", "https://api.hotdata.dev", None
        )
    listing.assert_not_called()
    assert resolved.workspace_id == "ws_explicit"
    assert resolved.source == "explicit_env"
    assert resolved.workspaces == []


def test_pick_workspace_prefers_workspace_id_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("HOTDATA_WORKSPACE", raising=False)
    monkeypatch.setenv("HOTDATA_WORKSPACE_ID", "ws_from_id")
    assert pick_workspace("k", "https://api.hotdata.dev", None) == "ws_from_id"


def test_pick_workspace_chooses_first_active(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("HOTDATA_WORKSPACE", raising=False)
    monkeypatch.delenv("HOTDATA_WORKSPACE_ID", raising=False)

    items = [
        SimpleNamespace(public_id="ws_1", active=False),
        SimpleNamespace(public_id="ws_2", active=True),
        SimpleNamespace(public_id="ws_3", active=True),
    ]
    listing = SimpleNamespace(workspaces=items)

    with patch("hotdata_runtime.env.WorkspacesApi") as Api:
        Api.return_value.list_workspaces.return_value = listing
        assert pick_workspace("k", "https://api.hotdata.dev", None) == "ws_2"


def test_pick_workspace_falls_back_to_first(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("HOTDATA_WORKSPACE", raising=False)
    monkeypatch.delenv("HOTDATA_WORKSPACE_ID", raising=False)

    items = [
        SimpleNamespace(public_id="ws_1", active=False),
        SimpleNamespace(public_id="ws_2", active=False),
    ]
    listing = SimpleNamespace(workspaces=items)

    with patch("hotdata_runtime.env.WorkspacesApi") as Api:
        Api.return_value.list_workspaces.return_value = listing
        assert pick_workspace("k", "https://api.hotdata.dev", None) == "ws_1"


def test_resolve_workspace_selection_source_first(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("HOTDATA_WORKSPACE", raising=False)
    monkeypatch.delenv("HOTDATA_WORKSPACE_ID", raising=False)
    items = [
        SimpleNamespace(public_id="ws_1", active=False),
        SimpleNamespace(public_id="ws_2", active=False),
    ]
    listing = SimpleNamespace(workspaces=items)
    with patch("hotdata_runtime.env.WorkspacesApi") as Api:
        Api.return_value.list_workspaces.return_value = listing
        resolved = resolve_workspace_selection(
            "k", "https://api.hotdata.dev", None
        )
    assert resolved.workspace_id == "ws_1"
    assert resolved.source == "first"
    assert resolved.workspaces == items


def test_resolve_workspace_selection_returns_workspaces_and_source(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv("HOTDATA_WORKSPACE", raising=False)
    monkeypatch.delenv("HOTDATA_WORKSPACE_ID", raising=False)

    items = [
        SimpleNamespace(public_id="ws_1", active=False),
        SimpleNamespace(public_id="ws_2", active=True),
    ]
    listing = SimpleNamespace(workspaces=items)

    with patch("hotdata_runtime.env.WorkspacesApi") as Api:
        Api.return_value.list_workspaces.return_value = listing
        resolved = resolve_workspace_selection(
            "k", "https://api.hotdata.dev", None
        )
    assert resolved.workspace_id == "ws_2"
    assert resolved.source == "active"
    assert resolved.workspaces == items


def test_list_qualified_table_names_passes_connection_id():
    client = HotdataClient("k", "ws", host="https://api.hotdata.dev")
    with patch.object(client, "iter_tables", return_value=iter([])) as it:
        client.list_qualified_table_names(limit=5, connection_id="conn_a")
    it.assert_called_once()
    assert it.call_args.kwargs["connection_id"] == "conn_a"


def test_wait_result_ready_raises_on_cancelled():
    client = HotdataClient("k", "ws", host="https://api.hotdata.dev")

    class FakeResultsApi:
        def get_result(self, result_id: str):
            return SimpleNamespace(status="cancelled", error_message=None)

    with patch.object(client, "_results_api", return_value=FakeResultsApi()):
        with pytest.raises(RuntimeError, match="cancelled"):
            client._wait_result_ready("res_1", timeout_s=0.1, interval_s=0)


def test_connection_id_by_name_raises_on_duplicate_names():
    client = HotdataClient("k", "ws", host="https://api.hotdata.dev")
    listing = SimpleNamespace(
        connections=[
            SimpleNamespace(name="warehouse", id="conn_1"),
            SimpleNamespace(name="warehouse", id="conn_2"),
        ]
    )

    class FakeConnectionsApi:
        def list_connections(self):
            return listing

    with patch.object(client, "connections", return_value=FakeConnectionsApi()):
        with pytest.raises(RuntimeError, match="Duplicate connection names"):
            client.connection_id_by_name()


def test_columns_for_qualified_prefers_explicit_connection_id():
    client = HotdataClient("k", "ws", host="https://api.hotdata.dev")
    col = SimpleNamespace(name="a", data_type="INTEGER", nullable=True)
    table = SimpleNamespace(columns=[col])
    response = SimpleNamespace(tables=[table])

    class FakeInformationSchemaApi:
        def __init__(self):
            self.kwargs = None

        def information_schema(self, **kwargs):
            self.kwargs = kwargs
            return response

    fake_api = FakeInformationSchemaApi()
    with patch.object(client, "_information_schema", return_value=fake_api), patch.object(
        client, "connection_id_by_name"
    ) as id_map:
        cols = client.columns_for_qualified(
            "warehouse.public.orders",
            connection_id="conn_explicit",
        )
    id_map.assert_not_called()
    assert cols == [col]
    assert fake_api.kwargs["connection_id"] == "conn_explicit"
