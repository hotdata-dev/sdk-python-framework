from __future__ import annotations

import time
from typing import Any, Iterator

from hotdata import ApiClient, Configuration
from hotdata.api.connections_api import ConnectionsApi
from hotdata.api.information_schema_api import InformationSchemaApi
from hotdata.api.query_api import QueryApi
from hotdata.api.query_runs_api import QueryRunsApi
from hotdata.api.results_api import ResultsApi
from hotdata.exceptions import ApiException
from hotdata.models.async_query_response import AsyncQueryResponse
from hotdata.models.query_request import QueryRequest
from hotdata.models.query_response import QueryResponse
from hotdata.models.table_info import TableInfo

from hotdata_runtime.env import (
    default_api_key,
    default_host,
    default_session_id,
    normalize_host,
    pick_workspace,
)
from hotdata_runtime.result import QueryResult

_TERMINAL = frozenset({"succeeded", "failed", "cancelled"})


class HotdataClient:
    """Thin wrapper around the Hotdata Python SDK with query polling helpers."""

    def __init__(
        self,
        api_key: str,
        workspace_id: str,
        *,
        host: str | None = None,
        session_id: str | None = None,
    ) -> None:
        self._host = normalize_host(host) if host else default_host()
        self._api_key = api_key
        self._workspace_id = workspace_id
        self._session_id = session_id
        self._config = Configuration(
            host=self._host,
            api_key=api_key,
            workspace_id=workspace_id,
            session_id=session_id,
        )
        self._api = ApiClient(self._config)

    @classmethod
    def from_env(cls) -> HotdataClient:
        api_key = default_api_key()
        if not api_key:
            raise RuntimeError(
                "HOTDATA_API_KEY or HOTDATA_TOKEN must be set."
            )
        host = default_host()
        session = default_session_id()
        workspace_id = pick_workspace(api_key, host, session)
        return cls(api_key, workspace_id, host=host, session_id=session)

    @property
    def workspace_id(self) -> str:
        return self._workspace_id

    @property
    def host(self) -> str:
        return self._host

    @property
    def session_id(self) -> str | None:
        return self._session_id

    @property
    def api(self) -> ApiClient:
        return self._api

    def close(self) -> None:
        self._api.close()

    def __enter__(self) -> HotdataClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def connections(self) -> ConnectionsApi:
        return ConnectionsApi(self._api)

    def _information_schema(self) -> InformationSchemaApi:
        return InformationSchemaApi(self._api)

    def _query_api(self) -> QueryApi:
        return QueryApi(self._api)

    def _query_runs_api(self) -> QueryRunsApi:
        return QueryRunsApi(self._api)

    def _results_api(self) -> ResultsApi:
        return ResultsApi(self._api)

    def query_runs(self) -> QueryRunsApi:
        return self._query_runs_api()

    def results(self) -> ResultsApi:
        return self._results_api()

    def iter_tables(
        self,
        *,
        connection_id: str | None = None,
        include_columns: bool = False,
        page_size: int = 200,
    ) -> Iterator[TableInfo]:
        cursor: str | None = None
        while True:
            resp = self._information_schema().information_schema(
                connection_id=connection_id,
                include_columns=include_columns,
                limit=page_size,
                cursor=cursor,
            )
            yield from resp.tables
            if not resp.has_more or not resp.next_cursor:
                break
            cursor = resp.next_cursor

    def qualified_table_name(self, t: TableInfo) -> str:
        return f"{t.connection}.{t.var_schema}.{t.table}"

    def list_qualified_table_names(
        self, *, limit: int = 5000, connection_id: str | None = None
    ) -> list[str]:
        out: list[str] = []
        for t in self.iter_tables(connection_id=connection_id):
            out.append(self.qualified_table_name(t))
            if len(out) >= limit:
                break
        return sorted(out)

    def connection_id_by_name(self) -> dict[str, str]:
        listing = self.connections().list_connections()
        return {c.name: c.id for c in listing.connections}

    def columns_for_qualified(self, qualified: str) -> list[TableInfo]:
        parts = qualified.split(".")
        if len(parts) < 3:
            raise ValueError(
                f"Expected connection.schema.table, got {qualified!r}"
            )
        conn_name, schema_name, table_name = (
            parts[0],
            parts[1],
            ".".join(parts[2:]),
        )
        id_map = self.connection_id_by_name()
        conn_id = id_map.get(conn_name)
        if not conn_id:
            raise KeyError(f"Unknown connection {conn_name!r}")
        resp = self._information_schema().information_schema(
            connection_id=conn_id,
            var_schema=schema_name,
            table=table_name,
            include_columns=True,
            limit=10,
        )
        if not resp.tables:
            return []
        first = resp.tables[0]
        return first.columns or []

    def _poll_query_run(
        self,
        query_run_id: str,
        *,
        timeout_s: float = 300.0,
        interval_s: float = 0.5,
    ):
        runs = self._query_runs_api()
        deadline = time.monotonic() + timeout_s
        last = None
        while time.monotonic() < deadline:
            last = runs.get_query_run(query_run_id)
            if last.status in _TERMINAL:
                return last
            time.sleep(interval_s)
        raise TimeoutError(
            f"Query run {query_run_id} did not finish within {timeout_s}s "
            f"(last status: {getattr(last, 'status', None)})"
        )

    def _wait_result_ready(
        self,
        result_id: str,
        *,
        timeout_s: float = 300.0,
        interval_s: float = 0.5,
    ):
        results = self._results_api()
        deadline = time.monotonic() + timeout_s
        last = None
        while time.monotonic() < deadline:
            last = results.get_result(result_id)
            if last.status == "ready":
                return last
            if last.status == "failed":
                raise RuntimeError(
                    last.error_message or "Result persistence failed"
                )
            time.sleep(interval_s)
        raise TimeoutError(
            f"Result {result_id} not ready within {timeout_s}s "
            f"(last status: {getattr(last, 'status', None)})"
        )

    def execute_sql(self, sql: str) -> QueryResult:
        q = self._query_api()
        try:
            raw = q.query(QueryRequest(sql=sql))
        except ApiException as e:
            raise RuntimeError(e.reason or str(e)) from e

        if isinstance(raw, AsyncQueryResponse):
            run = self._poll_query_run(raw.query_run_id)
            if run.status != "succeeded":
                raise RuntimeError(
                    run.error_message or f"Query failed ({run.status})"
                )
            if run.result_id:
                persisted = self._wait_result_ready(run.result_id)
                return QueryResult.from_get_result(persisted)
            raise RuntimeError("Query succeeded but no result_id was returned.")

        if isinstance(raw, QueryResponse):
            return QueryResult.from_query_response(raw)

        raise RuntimeError(f"Unexpected query response type: {type(raw)!r}")

    def get_result(self, result_id: str) -> QueryResult:
        r = self._results_api().get_result(result_id)
        if r.status != "ready":
            r = self._wait_result_ready(result_id)
        return QueryResult.from_get_result(r)


def from_env() -> HotdataClient:
    return HotdataClient.from_env()
