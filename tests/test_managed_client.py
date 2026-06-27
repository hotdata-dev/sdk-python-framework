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

        def get_result(self, result_id: str) -> Any:
            status = next(statuses)
            calls.append(f"get_result:{status}")
            return SimpleNamespace(status=status, result_id=result_id, error_message=None)

    class FakeArrowResultsApi:
        def __init__(self, api: object) -> None:
            pass

        def get_result_arrow(self, result_id: str) -> pa.Table:
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
    client._runtime = SimpleNamespace(  # type: ignore[assignment]
        api=object(),
        resolve_managed_database=lambda name: SimpleNamespace(id="db1", default_connection_id="c"),
        list_managed_tables=lambda database, schema=None: [
            SimpleNamespace(table="orders", synced=True)
        ],
    )

    table = client.fetch_table(database="mydb", schema="public", table="orders")

    assert table is not None
    assert table.num_rows == 2
    # The result was polled to readiness, and Arrow was fetched only afterwards.
    assert "get_result:processing" in calls
    assert "get_result:ready" in calls
    assert calls.index("arrow") > calls.index("get_result:ready")
