"""Managed database helpers (Hotdata-owned catalogs with parquet table loads)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from hotdata.exceptions import ApiException

DEFAULT_SCHEMA = "public"


@dataclass(frozen=True)
class ManagedDatabase:
    id: str
    description: str | None
    default_connection_id: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ManagedTable:
    full_name: str
    schema: str
    table: str
    synced: bool
    last_sync: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LoadManagedTableResult:
    connection_id: str
    schema_name: str
    table_name: str
    row_count: int
    full_name: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def is_parquet_path(path: str) -> bool:
    return Path(path).suffix.lower() == ".parquet"


def managed_database_from_detail(detail: Any) -> ManagedDatabase:
    return ManagedDatabase(
        id=str(detail.id),
        description=detail.name,
        default_connection_id=str(detail.default_connection_id),
    )


def api_error_message(exc: ApiException) -> str:
    reason = exc.reason or str(exc)
    # Keep the response body: it carries the API's actual explanation.
    body = getattr(exc, "body", None)
    if body:
        return f"{reason}: {' '.join(str(body).split())[:500]}"
    return reason
