from __future__ import annotations

import io
from types import SimpleNamespace
from unittest.mock import MagicMock, mock_open, patch

import pytest
from hotdata.exceptions import ApiException
from hotdata.models.database_default_table_decl import DatabaseDefaultTableDecl

from hotdata_framework.client import HotdataClient
from hotdata_framework.databases import (
    is_parquet_path,
    managed_database_from_detail,
)


def _decl_key_supported() -> bool:
    # `key` ships with the regenerated client; the key tests activate once it does.
    try:
        return DatabaseDefaultTableDecl(name="t", key=["k"]).key == ["k"]
    except Exception:
        return False


requires_key_field = pytest.mark.skipif(
    not _decl_key_supported(),
    reason="hotdata client without `key` on managed-table decls",
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
    with (
        patch.object(client, "resolve_managed_database", return_value=db),
        patch.object(client, "_databases_api") as dbs,
    ):
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
    with (
        patch.object(client, "resolve_managed_database", return_value=db),
        patch.object(client, "iter_tables", return_value=[table]),
    ):
        rows = client.list_managed_tables("db_1")
    assert len(rows) == 1
    assert rows[0].full_name == "db_1.public.orders"
    assert rows[0].synced is True


def test_upload_parquet_rejects_non_parquet():
    client = _client()
    with pytest.raises(ValueError, match="parquet"):
        client.upload_parquet("/tmp/data.csv")


def _mock_open_bytes(data: bytes) -> MagicMock:
    """Return an open() mock whose file handle supports read(n) via BytesIO."""
    bio = io.BytesIO(data)
    m = MagicMock()
    m.__enter__ = lambda s: bio
    m.__exit__ = MagicMock(return_value=False)
    return MagicMock(return_value=m)


def _session(mode: str, **kw) -> SimpleNamespace:
    defaults = dict(
        upload_id="upl_sess",
        finalize_token="tok",
        headers={},
        part_size=None,
        part_urls=None,
        url=None,
    )
    return SimpleNamespace(mode=mode, **{**defaults, **kw})


def _http_resp(status: int = 200, etag: str = '"abc"') -> SimpleNamespace:
    return SimpleNamespace(status=status, headers={"ETag": etag})


def test_upload_parquet_multipart():
    client = _client()
    data = b"PAR1" + b"\x00" * 6  # 10 bytes -> 2 parts of 5
    session = _session("multipart", part_size=5, part_urls=["https://s/1", "https://s/2"])
    finalized = SimpleNamespace(upload_id="upl_final")

    with (
        patch("builtins.open", _mock_open_bytes(data)),
        patch("os.path.getsize", return_value=len(data)),
        patch.object(client, "uploads") as uploads,
        patch("hotdata_framework.client.urllib3.PoolManager") as MockPool,
    ):
        pool = MockPool.return_value
        pool.request.return_value = _http_resp()
        pool.clear.return_value = None
        uploads.return_value.create_upload_session_handler.return_value = session
        uploads.return_value.finalize_upload_handler.return_value = finalized

        upload_id = client.upload_parquet("/tmp/data.parquet")

    assert upload_id == "upl_final"
    assert pool.request.call_count == 2
    finalize_call = uploads.return_value.finalize_upload_handler.call_args
    assert finalize_call.kwargs["upload_id"] == "upl_sess"
    assert finalize_call.kwargs["x_upload_finalize_token"] == "tok"
    parts = finalize_call.kwargs["finalize_upload_request"].parts
    assert len(parts) == 2
    assert parts[0].part_number == 1
    assert parts[1].part_number == 2


def test_upload_parquet_single_put():
    client = _client()
    data = b"PAR1tiny"
    session = _session("single", url="https://s/put")
    finalized = SimpleNamespace(upload_id="upl_single")

    with (
        patch("builtins.open", mock_open(read_data=data)),
        patch("os.path.getsize", return_value=len(data)),
        patch.object(client, "uploads") as uploads,
        patch("hotdata_framework.client.urllib3.PoolManager") as MockPool,
    ):
        pool = MockPool.return_value
        pool.request.return_value = _http_resp()
        pool.clear.return_value = None
        uploads.return_value.create_upload_session_handler.return_value = session
        uploads.return_value.finalize_upload_handler.return_value = finalized

        upload_id = client.upload_parquet("/tmp/data.parquet")

    assert upload_id == "upl_single"
    pool.request.assert_called_once()
    call_args = pool.request.call_args
    assert call_args.args[0] == "PUT"
    assert call_args.args[1] == "https://s/put"


def test_upload_parquet_raises_on_501():
    client = _client()

    with (
        patch("builtins.open", mock_open(read_data=b"PAR1")),
        patch("os.path.getsize", return_value=4),
        patch.object(client, "uploads") as uploads,
    ):
        err = ApiException(status=501)
        uploads.return_value.create_upload_session_handler.side_effect = err

        with pytest.raises(RuntimeError, match="presigned uploads"):
            client.upload_parquet("/tmp/data.parquet")

    uploads.return_value.upload_file.assert_not_called()


def test_upload_parquet_multipart_reads_are_part_size_bounded():
    """The OOM fix: multipart mode must never read more than part_size at once."""
    client = _client()
    part_size = 5
    data = b"PAR1" + b"\x00" * 9  # 13 bytes -> parts of 5, 5, 3
    read_sizes: list[int] = []

    class _TrackingFile(io.BytesIO):
        def read(self, n=-1):
            read_sizes.append(n)
            return super().read(n)

    bio = _TrackingFile(data)
    handle = MagicMock()
    handle.__enter__ = lambda s: bio
    handle.__exit__ = MagicMock(return_value=False)
    session = _session(
        "multipart", part_size=part_size, part_urls=["https://s/1", "https://s/2", "https://s/3"]
    )
    finalized = SimpleNamespace(upload_id="upl_final")

    with (
        patch("builtins.open", MagicMock(return_value=handle)),
        patch("os.path.getsize", return_value=len(data)),
        patch.object(client, "uploads") as uploads,
        patch("hotdata_framework.client.urllib3.PoolManager") as MockPool,
    ):
        pool = MockPool.return_value
        pool.request.return_value = _http_resp()
        pool.clear.return_value = None
        uploads.return_value.create_upload_session_handler.return_value = session
        uploads.return_value.finalize_upload_handler.return_value = finalized

        client.upload_parquet("/tmp/data.parquet")

    assert read_sizes, "expected chunked reads"
    assert all(n == part_size for n in read_sizes)


def test_load_managed_table_with_upload_id():
    client = _client()
    db = managed_database_from_detail(_detail())
    loaded = SimpleNamespace(
        connection_id="conn_1",
        schema_name="public",
        table_name="orders",
        row_count=42,
    )
    with (
        patch.object(client, "resolve_managed_database", return_value=db),
        patch.object(client, "connections") as connections,
    ):
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


def _load_and_capture_request(client, **kwargs):
    db = managed_database_from_detail(_detail())
    loaded = SimpleNamespace(
        connection_id="conn_1", schema_name="public", table_name="orders", row_count=1
    )
    with (
        patch.object(client, "resolve_managed_database", return_value=db),
        patch.object(client, "connections") as connections,
    ):
        connections.return_value.load_managed_table.return_value = loaded
        client.load_managed_table("db_1", "orders", upload_id="upl_1", **kwargs)
    return connections.return_value.load_managed_table.call_args.args[3]


def test_load_managed_table_defaults_to_replace():
    assert _load_and_capture_request(_client()).mode == "replace"


@pytest.mark.parametrize("mode", ["append", "delete", "update", "upsert"])
def test_load_managed_table_forwards_mode(mode: str):
    assert _load_and_capture_request(_client(), mode=mode).mode == mode


@requires_key_field
def test_create_managed_database_declares_keys():
    client = _client()
    with patch.object(client, "_databases_api") as dbs:
        dbs.return_value.create_database.return_value = _detail(id="db_new")
        client.create_managed_database(
            "mydb", tables=["orders", "events"], keys={"orders": ["id"]}
        )
    req = dbs.return_value.create_database.call_args.args[0]
    declared = {t.name: list(t.key) for t in req.schemas[0].tables}
    assert declared == {"orders": ["id"], "events": []}


@requires_key_field
def test_add_managed_table_declares_key():
    client = _client()
    db = managed_database_from_detail(_detail())
    with (
        patch.object(client, "resolve_managed_database", return_value=db),
        patch.object(client, "_databases_api") as dbs,
    ):
        client.add_managed_table("db_1", "line_items", key=["order_id", "sku"])
    req = dbs.return_value.add_database_table.call_args.args[2]
    assert req.name == "line_items"
    assert list(req.key) == ["order_id", "sku"]


@requires_key_field
def test_add_managed_table_keyless_by_default():
    client = _client()
    db = managed_database_from_detail(_detail())
    with (
        patch.object(client, "resolve_managed_database", return_value=db),
        patch.object(client, "_databases_api") as dbs,
    ):
        client.add_managed_table("db_1", "orders")
    req = dbs.return_value.add_database_table.call_args.args[2]
    assert list(req.key) == []


def test_delete_managed_table_uses_default_connection_id():
    client = _client()
    db = managed_database_from_detail(_detail())
    with (
        patch.object(client, "resolve_managed_database", return_value=db),
        patch.object(client, "connections") as connections,
    ):
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
