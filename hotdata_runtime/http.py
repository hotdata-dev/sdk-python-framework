"""HTTP client defaults for Hotdata SDK :class:`~hotdata.Configuration`."""

from __future__ import annotations

from urllib3.util.retry import Retry


def default_http_retries() -> Retry:
    """Retry transient connection failures (e.g. stale pooled sockets)."""
    return Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=0.2,
        status_forcelist=(502, 503, 504),
        allowed_methods=frozenset(
            ["GET", "HEAD", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]
        ),
    )
