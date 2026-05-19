from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import mock_open, patch

import pytest

from hotdata.exceptions import ApiException
from hotdata_runtime.client import HotdataClient
from hotdata_runtime.databases import (
    build_managed_config,
    create_connection_request,
    is_parquet_path,
)


def _client() -> HotdataClient:
    return HotdataClient("k", "ws", host="https://api.hotdata.dev")


def test_build_managed_config_empty_without_tables():
    assert build_managed_config("public", []) == {}


def test_build_managed_config_declares_tables():
    cfg = build_managed_config("public", ["orders", "customers"])
    assert cfg == {
        "schemas": [
            {
                "name": "public",
                "tables": [{"name": "orders"}, {"name": "customers"}],
            }
        ]
    }


def test_create_connection_request_uses_managed_source_type():
    req = create_connection_request("sales", schema="public", tables=["orders"])
    assert req.name == "sales"
    assert req.source_type == "managed"
    assert req.skip_discovery is True
    assert req.config["schemas"][0]["tables"][0]["name"] == "orders"


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


def test_list_managed_databases_filters_managed_only():
    client = _client()
    listing = SimpleNamespace(
        connections=[
            SimpleNamespace(id="c1", name="sales", source_type="managed"),
            SimpleNamespace(id="c2", name="warehouse", source_type="postgres"),
        ]
    )
    with patch.object(client, "connections") as connections:
        connections.return_value.list_connections.return_value = listing
        dbs = client.list_managed_databases()
    assert [db.name for db in dbs] == ["sales"]


def test_resolve_managed_database_by_name_and_id():
    client = _client()
    listing = SimpleNamespace(
        connections=[
            SimpleNamespace(id="conn_abc", name="sales", source_type="managed"),
        ]
    )
    with patch.object(client, "connections") as connections:
        connections.return_value.list_connections.return_value = listing
        by_name = client.resolve_managed_database("sales")
        by_id = client.resolve_managed_database("conn_abc")
    assert by_name.id == "conn_abc"
    assert by_id.name == "sales"


def test_resolve_managed_database_rejects_non_managed():
    client = _client()
    listing = SimpleNamespace(
        connections=[
            SimpleNamespace(id="c1", name="warehouse", source_type="postgres"),
        ]
    )
    with patch.object(client, "connections") as connections:
        connections.return_value.list_connections.return_value = listing
        with pytest.raises(ValueError, match="not a managed database"):
            client.resolve_managed_database("warehouse")


def test_create_managed_database_returns_summary():
    client = _client()
    created = SimpleNamespace(id="conn_new", name="mydb", source_type="managed")
    with patch.object(client, "connections") as connections:
        connections.return_value.create_connection.return_value = created
        db = client.create_managed_database("mydb", tables=["orders"])
    assert db.id == "conn_new"
    assert db.name == "mydb"
    req = connections.return_value.create_connection.call_args.args[0]
    assert req.config["schemas"][0]["tables"][0]["name"] == "orders"


def test_create_managed_database_wraps_api_errors():
    client = _client()
    with patch.object(client, "connections") as connections:
        connections.return_value.create_connection.side_effect = ApiException(
            status=400,
            reason="bad request",
        )
        with pytest.raises(RuntimeError, match="bad request"):
            client.create_managed_database("mydb")


def test_list_managed_tables_builds_full_names():
    client = _client()
    listing = SimpleNamespace(
        connections=[
            SimpleNamespace(id="conn1", name="sales", source_type="managed"),
        ]
    )
    table = SimpleNamespace(
        connection="sales",
        var_schema="public",
        table="orders",
        synced=True,
        last_sync="2026-05-19T00:00:00Z",
    )
    with patch.object(client, "connections") as connections, patch.object(
        client, "iter_tables", return_value=[table]
    ):
        connections.return_value.list_connections.return_value = listing
        rows = client.list_managed_tables("sales")
    assert len(rows) == 1
    assert rows[0].full_name == "sales.public.orders"
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
    db = SimpleNamespace(id="conn1", name="sales", source_type="managed")
    loaded = SimpleNamespace(
        connection_id="conn1",
        schema_name="public",
        table_name="orders",
        row_count=42,
    )
    with patch.object(client, "resolve_managed_database", return_value=db), patch.object(
        client, "connections"
    ) as connections:
        connections.return_value.load_managed_table.return_value = loaded
        result = client.load_managed_table(
            "sales",
            "orders",
            upload_id="upl_123",
        )
    assert result.row_count == 42
    assert result.full_name == "sales.public.orders"


def test_load_managed_table_requires_exactly_one_source():
    client = _client()
    with pytest.raises(ValueError, match="Exactly one"):
        client.load_managed_table("sales", "orders")
    with pytest.raises(ValueError, match="Exactly one"):
        client.load_managed_table(
            "sales",
            "orders",
            upload_id="upl_1",
            file="/tmp/x.parquet",
        )


def test_delete_managed_table_calls_sdk():
    client = _client()
    db = SimpleNamespace(id="conn1", name="sales", source_type="managed")
    with patch.object(client, "resolve_managed_database", return_value=db), patch.object(
        client, "connections"
    ) as connections:
        client.delete_managed_table("sales", "orders")
    connections.return_value.delete_managed_table.assert_called_once_with(
        "conn1",
        "public",
        "orders",
    )
