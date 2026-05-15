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
