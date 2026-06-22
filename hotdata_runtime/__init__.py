"""Hotdata runtime primitives for notebook, app, and adapter integrations."""

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
    is_parquet_path,
)
from hotdata_runtime.env import (
    WorkspaceSelection,
    default_api_key,
    default_host,
    default_session_id,
    explicit_workspace_id,
    list_workspaces,
    normalize_host,
    pick_workspace,
    resolve_workspace_selection,
)
from hotdata_runtime.errors import (
    HotdataError,
    HotdataTerminalError,
    HotdataTransientError,
    classify_sdk_error,
)
from hotdata_runtime.health import workspace_health_lines
from hotdata_runtime.managed_client import ManagedDatabaseClient
from hotdata_runtime.result import QueryResult

try:
    __version__ = version("hotdata-runtime")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"

__all__ = [
    "DEFAULT_SCHEMA",
    "HotdataClient",
    "HotdataError",
    "HotdataTerminalError",
    "HotdataTransientError",
    "LoadManagedTableResult",
    "ManagedDatabase",
    "ManagedDatabaseClient",
    "ManagedTable",
    "QueryResult",
    "ResultSummary",
    "RunHistoryItem",
    "WorkspaceSelection",
    "__version__",
    "classify_sdk_error",
    "default_api_key",
    "default_host",
    "default_session_id",
    "explicit_workspace_id",
    "from_env",
    "is_parquet_path",
    "list_workspaces",
    "normalize_host",
    "pick_workspace",
    "resolve_workspace_selection",
    "workspace_health_lines",
]
