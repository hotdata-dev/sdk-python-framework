"""Hotdata runtime primitives for notebook and app integrations."""

from importlib.metadata import PackageNotFoundError, version

from hotdata_runtime.client import (
    HotdataClient,
    ResultSummary,
    RunHistoryItem,
    from_env,
)
from hotdata_runtime.databases import (
    DEFAULT_SCHEMA,
    LoadManagedTableResult,
    ManagedDatabase,
    ManagedTable,
    MANAGED_SOURCE_TYPE,
    build_managed_config,
    create_connection_request,
    is_parquet_path,
)
from hotdata_runtime.env import (
    default_api_key,
    default_host,
    default_session_id,
    explicit_workspace_id,
    list_workspaces,
    normalize_host,
    pick_workspace,
    resolve_workspace_selection,
    WorkspaceSelection,
)
from hotdata_runtime.health import workspace_health_lines
from hotdata_runtime.result import QueryResult

try:
    __version__ = version("hotdata-runtime")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"

__all__ = [
    "__version__",
    "DEFAULT_SCHEMA",
    "HotdataClient",
    "LoadManagedTableResult",
    "MANAGED_SOURCE_TYPE",
    "ManagedDatabase",
    "ManagedTable",
    "QueryResult",
    "build_managed_config",
    "create_connection_request",
    "is_parquet_path",
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
    "ResultSummary",
    "RunHistoryItem",
    "WorkspaceSelection",
]
