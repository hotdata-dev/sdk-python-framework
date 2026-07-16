from __future__ import annotations

from hotdata.rest import ApiException


class HotdataError(RuntimeError):
    pass


class HotdataTransientError(HotdataError):
    pass


class HotdataTerminalError(HotdataError):
    pass


def classify_sdk_error(error: Exception) -> HotdataError:
    if isinstance(error, TimeoutError):
        return HotdataTransientError(str(error))
    if isinstance(error, ConnectionError):
        return HotdataTransientError(str(error))
    if isinstance(error, ApiException):
        status_code = int(error.status or 0)
        message = f"{status_code}: {error.reason or 'unknown error'}"
        # The response body is where the API explains itself (e.g. which
        # header is missing) — without it "400: Bad Request" is undebuggable.
        body = getattr(error, "body", None)
        if body:
            message = f"{message} — {' '.join(str(body).split())[:500]}"
        if status_code in (408, 409, 425, 429):
            return HotdataTransientError(message)
        if status_code == 501:
            # Not Implemented is a permanent capability gap (e.g. the storage
            # backend cannot issue presigned URLs) — retrying cannot succeed.
            return HotdataTerminalError(message)
        if 500 <= status_code <= 599:
            return HotdataTransientError(message)
        return HotdataTerminalError(message)
    return HotdataTerminalError(str(error))
