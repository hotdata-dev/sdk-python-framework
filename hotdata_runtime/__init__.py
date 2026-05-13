"""Hotdata runtime primitives for notebook and app integrations."""

from importlib.metadata import PackageNotFoundError, version

from hotdata_runtime.client import HotdataClient, from_env
from hotdata_runtime.env import (
    default_api_key,
    default_host,
    default_session_id,
    explicit_workspace_id,
    list_workspaces,
    normalize_host,
    pick_workspace,
)
from hotdata_runtime.health import workspace_health_lines
from hotdata_runtime.result import QueryResult

try:
    __version__ = version("hotdata-runtime")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"

__all__ = [
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
]
