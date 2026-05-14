from __future__ import annotations

from dataclasses import fields
from unittest.mock import patch

import hotdata_runtime as hr
from hotdata_runtime.client import HotdataClient
from hotdata_runtime.result import QueryResult


def test_public_exports_contract():
    assert hr.__all__ == [
        "__version__",
        "HotdataClient",
        "QueryResult",
        "workspace_health_lines",
        "default_api_key",
        "default_host",
        "default_session_id",
        "explicit_workspace_id",
        "from_env",
        "list_workspaces",
        "normalize_host",
        "pick_workspace",
        "resolve_workspace_selection",
        "WorkspaceSelection",
    ]


def test_module_from_env_delegates_to_client_classmethod():
    sentinel = HotdataClient("k", "ws", host="https://api.hotdata.dev")
    with patch.object(HotdataClient, "from_env", return_value=sentinel) as m:
        got = hr.from_env()
    m.assert_called_once_with()
    assert got is sentinel


def test_query_result_contract_fields():
    assert [f.name for f in fields(QueryResult)] == [
        "columns",
        "rows",
        "row_count",
        "result_id",
        "query_run_id",
        "execution_time_ms",
        "warning",
        "error_message",
    ]
