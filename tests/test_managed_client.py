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
    client._runtime = _fake_runtime()

    table = client.fetch_table(database="mydb", schema="public", table="orders")

    assert table is not None
    assert table.num_rows == 2
    # The result was polled to readiness, and Arrow was fetched only afterwards.
    assert "get_result:processing" in calls
    assert "get_result:ready" in calls
    assert calls.index("arrow") > calls.index("get_result:ready")


class _FakeApiClient:
    """Just enough of the generated ApiClient's default-header surface."""

    def __init__(self) -> None:
        self.default_headers: dict[str, str] = {}

    def set_default_header(self, name: str, value: str) -> None:
        self.default_headers[name] = value


def _fake_runtime(api: object | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        api=api if api is not None else _FakeApiClient(),
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
    the header is missing. ``fetch_table`` must carry the database id on the
    result poll and the Arrow fetch, not only on the query submit.

    Regression: reruns/append loads against an existing synced table failed
    with an opaque ``400: Bad Request`` (dlthubworker#70) because both reads
    omitted the header.
    """
    seen_headers: list[dict[str, Any] | None] = []
    arrow_headers: list[str | None] = []
    fake_api = _FakeApiClient()

    class FakeQueryApi:
        def __init__(self, api: object) -> None:
            pass

        def query(self, request: object, *, x_database_id: str) -> QueryResponse:
            assert x_database_id == "db1"
            return _query_response("rslt1")

    class FakeResultsApi:
        def __init__(self, api: object) -> None:
            pass

        def get_result(self, result_id: str, *, _headers: dict[str, Any] | None = None) -> Any:
            seen_headers.append(_headers)
            return SimpleNamespace(status="ready", result_id=result_id, error_message=None)

    class FakeArrowResultsApi:
        def __init__(self, api: _FakeApiClient) -> None:
            self._api = api

        def get_result_arrow(self, result_id: str) -> pa.Table:
            # The scoped default header must be present DURING the fetch.
            arrow_headers.append(self._api.default_headers.get("X-Database-Id"))
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
    client._runtime = _fake_runtime(fake_api)

    table = client.fetch_table(database="mydb", schema="public", table="orders")

    assert table is not None
    assert seen_headers == [{"X-Database-Id": "db1"}]
    assert arrow_headers == ["db1"]
    # The scoped header is removed once the fetch completes.
    assert "X-Database-Id" not in fake_api.default_headers
