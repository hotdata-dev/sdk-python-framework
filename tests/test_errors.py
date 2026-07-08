"""Error message construction: the API's response body must survive.

"400: Bad Request" alone is undebuggable; the body carries the server's
actual explanation (e.g. which header was missing).
"""

from __future__ import annotations

from hotdata.rest import ApiException

from hotdata_framework.databases import api_error_message
from hotdata_framework.errors import (
    HotdataTerminalError,
    HotdataTransientError,
    classify_sdk_error,
)

BODY = '{"error":{"code":"BAD_REQUEST","message":"X-Database-Id header is required"}}'


def test_classify_sdk_error_includes_response_body() -> None:
    err = classify_sdk_error(ApiException(status=400, reason="Bad Request", body=BODY))
    assert isinstance(err, HotdataTerminalError)
    assert "400: Bad Request" in str(err)
    assert "X-Database-Id header is required" in str(err)


def test_classify_sdk_error_without_body_keeps_short_form() -> None:
    err = classify_sdk_error(ApiException(status=409, reason="Conflict"))
    assert isinstance(err, HotdataTransientError)
    assert str(err) == "409: Conflict"


def test_classify_sdk_error_truncates_and_flattens_body() -> None:
    noisy = "x\n" * 1000
    err = classify_sdk_error(ApiException(status=500, reason="ISE", body=noisy))
    assert "\n" not in str(err)
    assert len(str(err)) < 600


def test_api_error_message_includes_body() -> None:
    msg = api_error_message(ApiException(status=400, reason="Bad Request", body=BODY))
    assert msg.startswith("Bad Request: ")
    assert "X-Database-Id header is required" in msg


def test_api_error_message_without_body() -> None:
    assert api_error_message(ApiException(status=404, reason="Not Found")) == "Not Found"
