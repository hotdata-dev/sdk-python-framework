"""The default request timeout must reach every call through the client.

The generated client sends ``_request_timeout=None`` (urllib3 no-timeout)
unless a caller passes one per call — and the helper methods expose no such
knob — so a stalled server blocks the calling thread indefinitely.
``apply_default_request_timeout`` wraps the REST seam once at construction.
"""

from __future__ import annotations

from hotdata_framework.client import HotdataClient, apply_default_request_timeout
from hotdata_framework.managed_client import ManagedDatabaseClient


class _FakeRest:
    def __init__(self) -> None:
        self.seen: list[object] = []

    def request(self, method, url, headers=None, body=None, post_params=None, _request_timeout=None):
        self.seen.append(_request_timeout)
        return "resp"


class _FakeApi:
    def __init__(self) -> None:
        self.rest_client = _FakeRest()


def test_default_applied_when_no_per_call_timeout() -> None:
    api = _FakeApi()
    rest = api.rest_client
    apply_default_request_timeout(api, (10.0, 60.0))

    assert api.rest_client.request("GET", "http://x") == "resp"
    assert rest.seen == [(10.0, 60.0)]


def test_explicit_per_call_timeout_wins() -> None:
    api = _FakeApi()
    rest = api.rest_client
    apply_default_request_timeout(api, 60.0)

    api.rest_client.request("GET", "http://x", _request_timeout=5.0)
    assert rest.seen == [5.0]


def test_hotdata_client_wraps_its_rest_seam() -> None:
    client = HotdataClient("k", "w", host="https://example.test", request_timeout=7.0)
    # The wrapper is installed in place of the generated bound method.
    assert client.api.rest_client.request.__name__ == "request"
    assert client.api.rest_client.request.__wrapped__ is not None


def test_hotdata_client_without_timeout_is_untouched() -> None:
    client = HotdataClient("k", "w", host="https://example.test")
    assert not hasattr(client.api.rest_client.request, "__wrapped__")


def test_managed_client_threads_timeout_through() -> None:
    client = ManagedDatabaseClient(
        api_key="k",
        workspace_id="w",
        api_base_url="https://example.test",
        max_retries=1,
        retry_backoff_seconds=0.0,
        request_timeout=(5.0, 30.0),
    )
    assert client._runtime.api.rest_client.request.__wrapped__ is not None
    client.close()
