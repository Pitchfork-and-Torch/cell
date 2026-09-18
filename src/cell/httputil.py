"""Small urllib wrapper. Never logs secrets."""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class HttpError(RuntimeError):
    def __init__(self, message: str, status: int | None = None, body: str = "", code: str | int | None = None):
        super().__init__(message)
        self.status = status
        self.body = body
        self.code = code


def request(
    method: str,
    url: str,
    *,
    query: dict[str, Any] | None = None,
    form: dict[str, Any] | None = None,
    json_body: Any = None,
    basic: tuple[str, str] | None = None,
    bearer: str | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
) -> tuple[int, Any, str]:
    if query:
        q = urllib.parse.urlencode({k: v for k, v in query.items() if v is not None})
        url = url + ("&" if "?" in url else "?") + q
    data: bytes | None = None
    hdrs = {"User-Agent": "knock-cell/0.1", "Accept": "application/json"}
    if headers:
        hdrs.update(headers)
    if form is not None:
        data = urllib.parse.urlencode(form).encode("utf-8")
        hdrs["Content-Type"] = "application/x-www-form-urlencoded"
    elif json_body is not None:
        data = json.dumps(json_body).encode("utf-8")
        hdrs["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method.upper(), headers=hdrs)
    if basic:
        import base64

        token = base64.b64encode(f"{basic[0]}:{basic[1]}".encode("utf-8")).decode("ascii")
        req.add_header("Authorization", f"Basic {token}")
    if bearer:
        req.add_header("Authorization", f"Bearer {bearer}")
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            status = resp.getcode() or 200
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        parsed = _maybe_json(raw)
        code = _extract_code(parsed)
        msg = _error_message(parsed, raw, e.code)
        raise HttpError(msg, status=e.code, body=raw, code=code) from None
    except urllib.error.URLError as e:
        raise HttpError(f"network error: {e.reason}") from None
    return status, _maybe_json(raw), raw


def _maybe_json(raw: str) -> Any:
    raw = (raw or "").strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw}


def _extract_code(parsed: Any) -> str | int | None:
    from cell.errors import extract_code

    return extract_code(parsed)


def _error_message(parsed: Any, raw: str, status: int) -> str:
    from cell.errors import annotate, extract_code

    code = extract_code(parsed)
    if isinstance(parsed, dict):
        for key in ("message", "error", "detail"):
            val = parsed.get(key)
            if isinstance(val, str) and val.strip():
                if code is not None:
                    return annotate(f"HTTP {status} ({code}): {val}", code)
                return f"HTTP {status}: {val}"
        errors = parsed.get("errors")
        if isinstance(errors, list) and errors:
            first = errors[0]
            if isinstance(first, dict):
                detail = first.get("detail") or first.get("title") or first
                msg = f"HTTP {status}: {detail}"
                return annotate(msg, code)
    snippet = (raw or "").strip().replace("\n", " ")[:240]
    return annotate(f"HTTP {status}: {snippet or 'request failed'}", code)
