"""Hotdata client and shared models for notebook integrations."""

from hotdata_core_notebook.client import HotdataClient, from_env
from hotdata_core_notebook.health import workspace_health_lines
from hotdata_core_notebook.env import (
    default_api_key,
    default_host,
    default_session_id,
    explicit_workspace_id,
    list_workspaces,
    normalize_host,
    pick_workspace,
)
from hotdata_core_notebook.result import QueryResult

__all__ = [
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
