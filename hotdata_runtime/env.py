from __future__ import annotations

import os
from urllib.parse import urlparse

from hotdata import ApiClient, Configuration
from hotdata.api.workspaces_api import WorkspacesApi


def normalize_host(url: str) -> str:
    u = url.rstrip("/")
    if u.endswith("/v1"):
        u = u[:-3]
    parsed = urlparse(u)
    if not parsed.scheme or not parsed.netloc:
        return u
    return f"{parsed.scheme}://{parsed.netloc}"


def default_api_key() -> str:
    return os.environ.get("HOTDATA_API_KEY", "") or os.environ.get(
        "HOTDATA_TOKEN", ""
    )


def explicit_workspace_id() -> str | None:
    return os.environ.get("HOTDATA_WORKSPACE") or os.environ.get(
        "HOTDATA_WORKSPACE_ID"
    )


def default_host() -> str:
    raw = os.environ.get("HOTDATA_API_URL", "https://api.hotdata.dev")
    return normalize_host(raw)


def default_session_id() -> str | None:
    return os.environ.get("HOTDATA_SANDBOX")


def list_workspaces(api_key: str, host: str, session_id: str | None):
    cfg = Configuration(
        host=host,
        api_key=api_key,
        workspace_id=None,
        session_id=session_id,
    )
    with ApiClient(cfg) as api:
        listing = WorkspacesApi(api).list_workspaces()
    return listing.workspaces


def pick_workspace(api_key: str, host: str, session_id: str | None) -> str:
    explicit = explicit_workspace_id()
    if explicit:
        return explicit
    workspaces = list_workspaces(api_key, host, session_id)
    if not workspaces:
        raise RuntimeError("No Hotdata workspaces found for this API key.")
    active = [w for w in workspaces if w.active]
    chosen = active[0] if active else workspaces[0]
    return chosen.public_id
