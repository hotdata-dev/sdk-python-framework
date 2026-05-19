"""Managed database helpers (Hotdata-owned catalogs with parquet table loads)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from hotdata.exceptions import ApiException
from hotdata.models.create_connection_request import CreateConnectionRequest
from hotdata.models.load_managed_table_request import LoadManagedTableRequest

MANAGED_SOURCE_TYPE = "managed"
DEFAULT_SCHEMA = "public"


@dataclass(frozen=True)
class ManagedDatabase:
    id: str
    name: str
    source_type: str

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
    lowered = path.lower()
    if lowered.endswith(".parquet"):
        return True
    return Path(path).suffix.lower() == ".parquet"


def build_managed_config(schema: str, tables: list[str]) -> dict[str, Any]:
    if not tables:
        return {}
    return {
        "schemas": [
            {
                "name": schema,
                "tables": [{"name": table} for table in tables],
            }
        ]
    }


def create_connection_request(
    name: str,
    *,
    schema: str = DEFAULT_SCHEMA,
    tables: list[str] | None = None,
) -> CreateConnectionRequest:
    table_list = tables or []
    return CreateConnectionRequest(
        name=name,
        source_type=MANAGED_SOURCE_TYPE,
        config=build_managed_config(schema, table_list),
        skip_discovery=True,
    )


def _managed_database(conn: Any) -> ManagedDatabase:
    return ManagedDatabase(
        id=str(conn.id),
        name=str(conn.name),
        source_type=str(conn.source_type),
    )


def _api_error(exc: ApiException) -> str:
    return exc.reason or str(exc)
