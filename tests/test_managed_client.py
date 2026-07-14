"""Regression tests for ManagedDatabaseClient result handling."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pyarrow as pa
import pytest
from hotdata.models.query_response import QueryResponse

import hotdata_framework.managed_client as mc


def _query_response(result_id: str) -> QueryResponse:
    return QueryResponse(
        columns=[],
        rows=[],
        row_count=0,
        preview_row_count=0,
        truncated=False,
        nullable=[],
        result_id=result_id,
        query_run_id="qr",
        execution_time_ms=1,
    )


def test_fetch_table_waits_for_ready_before_arrow(monkeypatch: pytest.MonkeyPatch) -> None:
    """A synchronous ``QueryResponse`` persists its full result out-of-band, and
    that result can still be ``processing`` when the inline preview returns.

    ``fetch_table`` must poll the result to ``ready`` before fetching it as
    Arrow. The earlier bug returned the ``result_id`` immediately on the sync
    path, so Arrow was fetched against a ``processing`` result and failed.
    """
    calls: list[str] = []

    class FakeQueryApi:
        def __init__(self, api: object) -> None:
            pass

        def query(self, request: object, *, x_database_id: str) -> QueryResponse:
            calls.append("query")
            return _query_response("rslt1")

    statuses = iter(["processing", "processing", "ready"])

    class FakeResultsApi:
        def __init__(self, api: object) -> None:
            pass

        def get_result(self, result_id: str, **kwargs: Any) -> Any:
            status = next(statuses)
            calls.append(f"get_result:{status}")
            return SimpleNamespace(status=status, result_id=result_id, error_message=None)

    class FakeArrowResultsApi:
        def __init__(self, api: object) -> None:
            pass

        def get_result_arrow(self, result_id: str, **kwargs: Any) -> pa.Table:
            calls.append("arrow")
            return pa.table({"id": [1, 2]})

    monkeypatch.setattr(mc, "QueryApi", FakeQueryApi)
    monkeypatch.setattr(mc, "ResultsApi", FakeResultsApi)
    monkeypatch.setattr(mc, "ArrowResultsApi", FakeArrowResultsApi)
    monkeypatch.setattr(mc.time, "sleep", lambda _seconds: None)

    client = mc.ManagedDatabaseClient(
        api_key="k",
        workspace_id="w",
        api_base_url="https://example.test",
        max_retries=1,
        retry_backoff_seconds=0.0,
    )
    client._runtime = _fake_runtime()

    table = client.fetch_table(database="mydb", schema="public", table="orders")

    assert table is not None
    assert table.num_rows == 2
    # The result was polled to readiness, and Arrow was fetched only afterwards.
    assert "get_result:processing" in calls
    assert "get_result:ready" in calls
    assert calls.index("arrow") > calls.index("get_result:ready")


def _fake_runtime() -> SimpleNamespace:
    return SimpleNamespace(
        api=object(),
        resolve_managed_database=lambda name: SimpleNamespace(id="db1", default_connection_id="c"),
        list_managed_tables=lambda database, schema=None: [
            SimpleNamespace(table="orders", synced=True)
        ],
    )


def test_fetch_table_carries_database_scope_on_result_reads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Results (and runs) of a database-scoped query are database-scoped:
    the results endpoints 400 with "X-Database-Id header is required" when
    the scope is missing. ``fetch_table`` must carry the database id on the
    result poll and the Arrow fetch, not only on the query submit — the
    hotdata 0.6.0 SDK exposes ``x_database_id`` on all three.

    Regression: reruns/append loads against an existing synced table failed
    with an opaque ``400: Bad Request`` because both reads omitted the scope.
    """
    result_scopes: list[str | None] = []
    arrow_scopes: list[str | None] = []

    class FakeQueryApi:
        def __init__(self, api: object) -> None:
            pass

        def query(self, request: object, *, x_database_id: str) -> QueryResponse:
            assert x_database_id == "db1"
            return _query_response("rslt1")

    class FakeResultsApi:
        def __init__(self, api: object) -> None:
            pass

        def get_result(self, result_id: str, *, x_database_id: str | None = None) -> Any:
            result_scopes.append(x_database_id)
            return SimpleNamespace(status="ready", result_id=result_id, error_message=None)

    class FakeArrowResultsApi:
        def __init__(self, api: object) -> None:
            pass

        # x_database_id is REQUIRED in the 0.6.0 SDK — mirroring that here
        # makes this test fail if a caller ever drops the scope again.
        def get_result_arrow(self, result_id: str, *, x_database_id: str) -> pa.Table:
            arrow_scopes.append(x_database_id)
            return pa.table({"id": [1]})

    monkeypatch.setattr(mc, "QueryApi", FakeQueryApi)
    monkeypatch.setattr(mc, "ResultsApi", FakeResultsApi)
    monkeypatch.setattr(mc, "ArrowResultsApi", FakeArrowResultsApi)

    client = mc.ManagedDatabaseClient(
        api_key="k",
        workspace_id="w",
        api_base_url="https://example.test",
        max_retries=1,
        retry_backoff_seconds=0.0,
    )
    client._runtime = _fake_runtime()

    table = client.fetch_table(database="mydb", schema="public", table="orders")

    assert table is not None
    assert result_scopes == ["db1"]
    assert arrow_scopes == ["db1"]


def _load_recording_runtime(calls: list[str]) -> SimpleNamespace:
    """A runtime whose ``load_managed_table`` records each mode and always fails
    with a transient error, so retry behaviour is observable via ``calls``."""

    def load_managed_table(
        database: str, table: str, *, schema: str, upload_id: str, mode: str
    ) -> SimpleNamespace:
        calls.append(mode)
        raise TimeoutError("commit succeeded but response was lost")

    runtime = _fake_runtime()
    runtime.load_managed_table = load_managed_table
    return runtime


def _managed_client(max_retries: int) -> Any:
    return mc.ManagedDatabaseClient(
        api_key="k",
        workspace_id="w",
        api_base_url="https://example.test",
        max_retries=max_retries,
        retry_backoff_seconds=0.0,
    )


def test_append_load_runs_at_most_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """``append`` is not idempotent: retrying after a commit whose response was
    lost would duplicate rows. A transient failure must surface immediately
    without re-appending, even with retries budgeted."""
    monkeypatch.setattr(mc.time, "sleep", lambda _seconds: None)
    calls: list[str] = []
    client = _managed_client(max_retries=8)
    client._runtime = _load_recording_runtime(calls)

    with pytest.raises(mc.HotdataTransientError):
        client.load_managed_table("db", "orders", schema="public", upload_id="u1", mode="append")

    assert calls == ["append"]  # tried once, never retried


def test_idempotent_load_retries_on_transient(monkeypatch: pytest.MonkeyPatch) -> None:
    """Idempotent modes still exhaust the retry budget on transient errors."""
    monkeypatch.setattr(mc.time, "sleep", lambda _seconds: None)
    calls: list[str] = []
    client = _managed_client(max_retries=3)
    client._runtime = _load_recording_runtime(calls)

    with pytest.raises(mc.HotdataTransientError):
        client.load_managed_table("db", "orders", schema="public", upload_id="u1", mode="replace")

    assert calls == ["replace", "replace", "replace"]  # retried up to max_retries
