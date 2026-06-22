from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from hotdata_runtime.client import HotdataClient
from hotdata_runtime.env import normalize_host, pick_workspace, resolve_workspace_selection


def _clear_workspace_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HOTDATA_WORKSPACE", raising=False)


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
        resolved = resolve_workspace_selection("k", "https://api.hotdata.dev", None)
    listing.assert_not_called()
    assert resolved.workspace_id == "ws_explicit"
    assert resolved.source == "explicit_env"
    assert resolved.workspaces == []


def test_pick_workspace_chooses_first_active(monkeypatch: pytest.MonkeyPatch):
    _clear_workspace_env(monkeypatch)

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
    _clear_workspace_env(monkeypatch)

    items = [
        SimpleNamespace(public_id="ws_1", active=False),
        SimpleNamespace(public_id="ws_2", active=False),
    ]
    listing = SimpleNamespace(workspaces=items)

    with patch("hotdata_runtime.env.WorkspacesApi") as Api:
        Api.return_value.list_workspaces.return_value = listing
        assert pick_workspace("k", "https://api.hotdata.dev", None) == "ws_1"


def test_resolve_workspace_selection_source_first(monkeypatch: pytest.MonkeyPatch):
    _clear_workspace_env(monkeypatch)
    items = [
        SimpleNamespace(public_id="ws_1", active=False),
        SimpleNamespace(public_id="ws_2", active=False),
    ]
    listing = SimpleNamespace(workspaces=items)
    with patch("hotdata_runtime.env.WorkspacesApi") as Api:
        Api.return_value.list_workspaces.return_value = listing
        resolved = resolve_workspace_selection("k", "https://api.hotdata.dev", None)
    assert resolved.workspace_id == "ws_1"
    assert resolved.source == "first"
    assert resolved.workspaces == items


def test_resolve_workspace_selection_returns_workspaces_and_source(
    monkeypatch: pytest.MonkeyPatch,
):
    _clear_workspace_env(monkeypatch)

    items = [
        SimpleNamespace(public_id="ws_1", active=False),
        SimpleNamespace(public_id="ws_2", active=True),
    ]
    listing = SimpleNamespace(workspaces=items)

    with patch("hotdata_runtime.env.WorkspacesApi") as Api:
        Api.return_value.list_workspaces.return_value = listing
        resolved = resolve_workspace_selection("k", "https://api.hotdata.dev", None)
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

    with (
        patch.object(client, "_results_api", return_value=FakeResultsApi()),
        pytest.raises(RuntimeError, match="cancelled"),
    ):
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

    with (
        patch.object(client, "connections", return_value=FakeConnectionsApi()),
        pytest.raises(RuntimeError, match="Duplicate connection names"),
    ):
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
    with (
        patch.object(client, "_information_schema", return_value=fake_api),
        patch.object(client, "connection_id_by_name") as id_map,
    ):
        cols = client.columns_for_qualified(
            "warehouse.public.orders",
            connection_id="conn_explicit",
        )
    id_map.assert_not_called()
    assert cols == [col]
    assert fake_api.kwargs["connection_id"] == "conn_explicit"


def test_list_recent_results_returns_normalized_summaries():
    client = HotdataClient("k", "ws", host="https://api.hotdata.dev")
    listing = SimpleNamespace(
        results=[
            SimpleNamespace(id="res_1", status="ready", created_at="2026-01-01T00:00:00Z"),
            SimpleNamespace(id="res_2", status="failed", created_at=None),
        ]
    )

    class FakeResultsApi:
        def list_results(self, *, limit: int, offset: int):
            return listing

    with patch.object(client, "results", return_value=FakeResultsApi()):
        out = client.list_recent_results(limit=10, offset=2)
    assert [r.result_id for r in out] == ["res_1", "res_2"]
    assert out[0].status == "ready"
    assert out[0].to_dict()["created_at"] == "2026-01-01T00:00:00Z"


def test_execute_sql_sends_no_database_id_by_default():
    from hotdata.models.query_response import QueryResponse as _QR

    client = HotdataClient("k", "ws", host="https://api.hotdata.dev")

    class FakeQueryApi:
        def __init__(self):
            self.calls: list[dict] = []

        def query(self, request, **kwargs):
            self.calls.append(kwargs)
            return _QR(
                columns=["n"],
                rows=[[1]],
                row_count=1,
                preview_row_count=1,
                truncated=False,
                nullable=[False],
                result_id="res_1",
                query_run_id="qrun_1",
                execution_time_ms=1,
            )

    fake_q = FakeQueryApi()
    with patch.object(client, "_query_api", return_value=fake_q):
        client.execute_sql("SELECT 1")

    assert fake_q.calls == [{}]


def test_execute_sql_resolves_database_and_sends_x_database_id():
    from types import SimpleNamespace

    from hotdata.models.query_response import QueryResponse as _QR

    client = HotdataClient("k", "ws", host="https://api.hotdata.dev")

    class FakeQueryApi:
        def __init__(self):
            self.calls: list[dict] = []

        def query(self, request, **kwargs):
            self.calls.append(kwargs)
            return _QR(
                columns=["n"],
                rows=[[1]],
                row_count=1,
                preview_row_count=1,
                truncated=False,
                nullable=[False],
                result_id="res_1",
                query_run_id="qrun_1",
                execution_time_ms=1,
            )

    fake_q = FakeQueryApi()
    fake_db = SimpleNamespace(id="db_abc")

    with (
        patch.object(client, "_query_api", return_value=fake_q),
        patch.object(client, "resolve_managed_database", return_value=fake_db) as resolve,
    ):
        client.execute_sql('SELECT * FROM "default"."public"."orders"', database="my_db")

    resolve.assert_called_once_with("my_db")
    assert fake_q.calls == [{"x_database_id": "db_abc"}]


def test_list_run_history_returns_normalized_items():
    client = HotdataClient("k", "ws", host="https://api.hotdata.dev")
    listing = SimpleNamespace(
        query_runs=[
            SimpleNamespace(
                id="run_1",
                status="succeeded",
                created_at="2026-01-01T00:00:00Z",
                execution_time_ms=7,
                result_id="res_1",
            ),
        ]
    )

    class FakeRunsApi:
        def __init__(self):
            self.kwargs = None

        def list_query_runs(self, *, limit: int):
            self.kwargs = {"limit": limit}
            return listing

    fake_runs = FakeRunsApi()
    with patch.object(client, "query_runs", return_value=fake_runs):
        out = client.list_run_history(limit=5)
    assert [r.query_run_id for r in out] == ["run_1"]
    assert out[0].execution_time_ms == 7
    assert out[0].to_dict()["result_id"] == "res_1"
    assert fake_runs.kwargs == {"limit": 5}
