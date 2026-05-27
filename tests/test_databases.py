from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import mock_open, patch

import pytest

from hotdata.exceptions import ApiException
from hotdata_runtime.client import HotdataClient
from hotdata_runtime.databases import (
    is_parquet_path,
    managed_database_from_detail,
)


def _client() -> HotdataClient:
    return HotdataClient("k", "ws", host="https://api.hotdata.dev")


def _detail(id="db_1", description="sales", default_connection_id="conn_1"):
    return SimpleNamespace(
        id=id,
        name=description,
        default_connection_id=default_connection_id,
    )


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/data/orders.parquet", True),
        ("/data/ORDERS.PARQUET", True),
        ("/data/orders.csv", False),
    ],
)
def test_is_parquet_path(path: str, expected: bool):
    assert is_parquet_path(path) is expected


def test_managed_database_from_detail():
    db = managed_database_from_detail(_detail())
    assert db.id == "db_1"
    assert db.description == "sales"
    assert db.default_connection_id == "conn_1"


def test_list_managed_databases_returns_all():
    client = _client()
    summary = SimpleNamespace(id="db_1")
    detail = _detail()
    listing = SimpleNamespace(databases=[summary])
    with patch.object(client, "_databases_api") as dbs:
        dbs.return_value.list_databases.return_value = listing
        dbs.return_value.get_database.return_value = detail
        result = client.list_managed_databases()
    assert len(result) == 1
    assert result[0].id == "db_1"
    assert result[0].description == "sales"


def test_list_managed_databases_skips_failed_gets():
    client = _client()
    summaries = [SimpleNamespace(id="db_1"), SimpleNamespace(id="db_2")]
    detail = _detail(id="db_2", description="warehouse", default_connection_id="conn_2")
    listing = SimpleNamespace(databases=summaries)
    with patch.object(client, "_databases_api") as dbs:
        dbs.return_value.list_databases.return_value = listing
        dbs.return_value.get_database.side_effect = [
            ApiException(status=404, reason="not found"),
            detail,
        ]
        result = client.list_managed_databases()
    assert len(result) == 1
    assert result[0].id == "db_2"


def test_resolve_managed_database_by_id():
    client = _client()
    detail = _detail()
    with patch.object(client, "_databases_api") as dbs:
        dbs.return_value.get_database.return_value = detail
        db = client.resolve_managed_database("db_1")
    assert db.id == "db_1"
    assert db.default_connection_id == "conn_1"


def test_resolve_managed_database_by_description():
    client = _client()
    summary = SimpleNamespace(id="db_1", name="sales")
    listing = SimpleNamespace(databases=[summary])
    detail = _detail()
    with patch.object(client, "_databases_api") as dbs:
        dbs.return_value.get_database.side_effect = [
            ApiException(status=404, reason="not found"),
            detail,
        ]
        dbs.return_value.list_databases.return_value = listing
        db = client.resolve_managed_database("sales")
    assert db.id == "db_1"


def test_resolve_managed_database_not_found():
    client = _client()
    listing = SimpleNamespace(databases=[])
    with patch.object(client, "_databases_api") as dbs:
        dbs.return_value.get_database.side_effect = ApiException(status=404, reason="not found")
        dbs.return_value.list_databases.return_value = listing
        with pytest.raises(KeyError, match="no-such"):
            client.resolve_managed_database("no-such")


def test_create_managed_database_returns_summary():
    client = _client()
    created = _detail(id="db_new", description="mydb", default_connection_id="conn_new")
    with patch.object(client, "_databases_api") as dbs:
        dbs.return_value.create_database.return_value = created
        db = client.create_managed_database("mydb", tables=["orders"])
    assert db.id == "db_new"
    assert db.description == "mydb"
    req = dbs.return_value.create_database.call_args.args[0]
    assert req.schemas[0].tables[0].name == "orders"


def test_create_managed_database_wraps_api_errors():
    client = _client()
    with patch.object(client, "_databases_api") as dbs:
        dbs.return_value.create_database.side_effect = ApiException(
            status=400,
            reason="bad request",
        )
        with pytest.raises(RuntimeError, match="bad request"):
            client.create_managed_database("mydb")


def test_create_managed_database_with_expires_at():
    client = _client()
    created = _detail()
    with patch.object(client, "_databases_api") as dbs:
        dbs.return_value.create_database.return_value = created
        client.create_managed_database("mydb", expires_at="7d")
    req = dbs.return_value.create_database.call_args.args[0]
    assert req.expires_at == "7d"


def test_delete_managed_database_calls_sdk():
    client = _client()
    db = managed_database_from_detail(_detail())
    with patch.object(client, "resolve_managed_database", return_value=db), \
         patch.object(client, "_databases_api") as dbs:
        client.delete_managed_database("db_1")
    dbs.return_value.delete_database.assert_called_once_with("db_1")


def test_list_managed_tables_builds_full_names():
    client = _client()
    db = managed_database_from_detail(_detail())
    table = SimpleNamespace(
        connection="conn_1",
        var_schema="public",
        table="orders",
        synced=True,
        last_sync="2026-05-19T00:00:00Z",
    )
    with patch.object(client, "resolve_managed_database", return_value=db), \
         patch.object(client, "iter_tables", return_value=[table]):
        rows = client.list_managed_tables("db_1")
    assert len(rows) == 1
    assert rows[0].full_name == "db_1.public.orders"
    assert rows[0].synced is True


def test_upload_parquet_rejects_non_parquet():
    client = _client()
    with pytest.raises(ValueError, match="parquet"):
        client.upload_parquet("/tmp/data.csv")


def test_upload_parquet_returns_upload_id():
    client = _client()
    uploaded = SimpleNamespace(id="upl_123")
    with patch("builtins.open", mock_open(read_data=b"PAR1")), patch.object(
        client, "uploads"
    ) as uploads:
        uploads.return_value.upload_file.return_value = uploaded
        upload_id = client.upload_parquet("/tmp/data.parquet")
    assert upload_id == "upl_123"


def test_load_managed_table_with_upload_id():
    client = _client()
    db = managed_database_from_detail(_detail())
    loaded = SimpleNamespace(
        connection_id="conn_1",
        schema_name="public",
        table_name="orders",
        row_count=42,
    )
    with patch.object(client, "resolve_managed_database", return_value=db), \
         patch.object(client, "connections") as connections:
        connections.return_value.load_managed_table.return_value = loaded
        result = client.load_managed_table(
            "db_1",
            "orders",
            upload_id="upl_123",
        )
    assert result.row_count == 42
    assert result.full_name == "db_1.public.orders"
    connections.return_value.load_managed_table.assert_called_once_with(
        "conn_1", "public", "orders", _Any()
    )


def test_load_managed_table_requires_exactly_one_source():
    client = _client()
    with pytest.raises(ValueError, match="Exactly one"):
        client.load_managed_table("db_1", "orders")
    with pytest.raises(ValueError, match="Exactly one"):
        client.load_managed_table(
            "db_1",
            "orders",
            upload_id="upl_1",
            file="/tmp/x.parquet",
        )


def test_delete_managed_table_uses_default_connection_id():
    client = _client()
    db = managed_database_from_detail(_detail())
    with patch.object(client, "resolve_managed_database", return_value=db), \
         patch.object(client, "connections") as connections:
        client.delete_managed_table("db_1", "orders")
    connections.return_value.delete_managed_table.assert_called_once_with(
        "conn_1",
        "public",
        "orders",
    )


class _Any:
    """Matches any value in assert_called_once_with."""
    def __eq__(self, other: object) -> bool:
        return True
