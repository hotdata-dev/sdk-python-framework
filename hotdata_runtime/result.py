from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from hotdata.models.get_result_response import GetResultResponse
from hotdata.models.query_response import QueryResponse


@dataclass
class QueryResult:
    """Tabular result from a Hotdata query or stored result id."""

    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    result_id: str | None
    query_run_id: str | None
    execution_time_ms: int | None
    warning: str | None = None
    error_message: str | None = None

    def to_records(
        self,
        *,
        max_rows: int | None = None,
    ) -> list[dict[str, Any]]:
        rows = self.rows if max_rows is None else self.rows[:max_rows]
        return [dict(zip(self.columns, row)) for row in rows]

    def metadata_dict(self) -> dict[str, Any]:
        return {
            "row_count": self.row_count,
            "column_count": len(self.columns),
            "result_id": self.result_id,
            "query_run_id": self.query_run_id,
            "execution_time_ms": self.execution_time_ms,
            "warning": self.warning,
            "error_message": self.error_message,
        }

    def to_pandas(self):  # type: ignore[no-untyped-def]
        import pandas as pd

        if not self.columns:
            return pd.DataFrame()
        return pd.DataFrame(self.rows, columns=self.columns)

    @classmethod
    def from_query_response(cls, r: QueryResponse) -> QueryResult:
        return cls(
            columns=list(r.columns),
            rows=[list(row) for row in r.rows],
            row_count=r.row_count,
            result_id=r.result_id,
            query_run_id=r.query_run_id,
            execution_time_ms=r.execution_time_ms,
            warning=r.warning,
            error_message=None,
        )

    @classmethod
    def from_get_result(cls, r: GetResultResponse) -> QueryResult:
        cols = list(r.columns or [])
        row_data = [list(row) for row in (r.rows or [])]
        return cls(
            columns=cols,
            rows=row_data,
            row_count=r.row_count or 0,
            result_id=r.result_id,
            query_run_id=None,
            execution_time_ms=None,
            warning=None,
            error_message=r.error_message,
        )
