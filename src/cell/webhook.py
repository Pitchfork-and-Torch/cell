"""Local inbound webhook. Polling still works if HavenID owns the number webhook."""

from __future__ import annotations

import base64
import json
import re
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from cell.config import Config, load
from cell.ed25519 import verify as ed25519_verify
from cell.models import Message
from cell.providers.twilio import twilio_signature_ok
from cell.store import connect, upsert_message


def serve(cfg: Config | None = None, host: str = "127.0.0.1", port: int | None = None) -> None:
    cfg = cfg or load()
    port = port or cfg.webhook_port
    httpd = ThreadingHTTPServer((host, port), _handler_for(cfg))
    print(f"cell webhook on http://{host}:{port}")
    print(f"  GET  /health")
    print(f"  POST /sms     Twilio form or Telnyx JSON")
    print(f"  POST /voice   returns simple TwiML <Say>")
    if cfg.public_url:
        print(f"  public {cfg.public_url.rstrip('/')}/sms")
    print("Pin this URL on a number you own. Do not steal a HavenID webhook unless intended.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nwebhook stopped")
        httpd.server_close()


def _handler_for(cfg: Config):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args) -> None:
            sys_stderr_write = super().log_message
            sys_stderr_write(fmt, *args)

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path in ("/", "/health"):
                self._json(200, {"ok": True, "service": "cell-webhook"})
                return
            self._json(404, {"ok": False, "error": "not found"})

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            length = int(self.headers.get("Content-Length") or "0")
            raw = self.rfile.read(length) if length else b""
            if path == "/sms":
                self._sms(raw)
                return
            if path == "/voice":
                self._voice()
                return
            self._json(404, {"ok": False, "error": "not found"})

        def _sms(self, raw: bytes) -> None:
            ctype = (self.headers.get("Content-Type") or "").lower()
            status, error, msg = ingest_sms(cfg, self.headers, raw, ctype, self.path)
            if status != 200:
                self._json(status, {"ok": False, "error": error})
                return
            if msg and msg.sid:
                print(f"IN {msg.from_n} -> {msg.to}: {msg.body}")
            # Empty TwiML: do not auto-reply (cost + loop risk).
            body = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'
            self._raw(200, body.encode("utf-8"), "text/xml")

        def _voice(self) -> None:
            twiml = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                "<Response><Say>This number is monitored by Grok cell. Goodbye.</Say></Response>"
            )
            self._raw(200, twiml.encode("utf-8"), "text/xml")

        def _json(self, code: int, payload: dict) -> None:
            data = json.dumps(payload).encode("utf-8")
            self._raw(code, data, "application/json")

        def _raw(self, code: int, data: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return Handler


def _hdr(headers: object, name: str) -> str:
    getter = getattr(headers, "get", None)
    if getter is None:
        return ""
    direct = getter(name)
    if direct:
        return str(direct)
    want = name.lower()
    items = getattr(headers, "items", None)
    if items is None:
        return ""
    for key, value in items():
        if str(key).lower() == want and value:
            return str(value)
    return ""


def _b64(text: str) -> bytes | None:
    raw = "".join((text or "").split())
    if not raw or not re.fullmatch(r"[A-Za-z0-9+/=]+", raw):
        return None
    raw += "=" * ((-len(raw)) % 4)
    try:
        return base64.b64decode(raw, validate=True)
    except Exception:
        return None


def _twilio_ok(cfg: Config, headers: object, path: str, form: dict[str, str]) -> bool:
    token = (cfg.twilio_auth_token or "").strip()
    if not token:
        return False
    sig = _hdr(headers, "X-Twilio-Signature")
    public = (cfg.public_url or "").rstrip("/")
    if public:
        url = public + "/sms"
    else:
        host = _hdr(headers, "X-Forwarded-Host") or _hdr(headers, "Host") or "127.0.0.1"
        proto = _hdr(headers, "X-Forwarded-Proto") or "http"
        url = f"{proto}://{host}{path.split('?')[0]}"
    return twilio_signature_ok(token, url, form, sig)


# Telnyx signs timestamp|body. Reject captures older or newer than this window.
TELNYX_MAX_SKEW_S = 300


def _telnyx_check(
    cfg: Config,
    headers: object,
    raw: bytes,
    now: float | None = None,
) -> str | None:
    """Return None when the Ed25519 webhook signature is fresh.

    The bearer API key is not the webhook public key. A KEY... token in
    telnyx_api_key does not authorize inbound JSON.
    """
    key = (cfg.telnyx_public_key or "").strip()
    if not key:
        return "telnyx not configured"
    signature = _b64(_hdr(headers, "telnyx-signature-ed25519"))
    timestamp = _hdr(headers, "telnyx-timestamp").strip()
    public = _b64(key)
    if (
        signature is None
        or public is None
        or not timestamp.isdigit()
        or len(timestamp) > 12
    ):
        return "bad telnyx signature"
    stamp = int(timestamp)
    current = int(time.time() if now is None else now)
    if abs(current - stamp) > TELNYX_MAX_SKEW_S:
        return "stale telnyx timestamp"
    message = timestamp.encode("ascii") + b"|" + raw
    if not ed25519_verify(public, signature, message):
        return "bad telnyx signature"
    return None


def ingest_sms(
    cfg: Config,
    headers: object,
    raw: bytes,
    content_type: str,
    path: str,
    now: float | None = None,
) -> tuple[int, str, Message | None]:
    """Authorize, then store. Unsigned or unverified bodies are not stored."""
    ctype = (content_type or "").lower()
    if "json" in ctype:
        reason = _telnyx_check(cfg, headers, raw, now=now)
        if reason:
            return 403, reason, None
        msg = _from_telnyx_json(raw)
    else:
        form = {k: (v[0] if v else "") for k, v in parse_qs(raw.decode("utf-8", "replace")).items()}
        if not _twilio_ok(cfg, headers, path, form):
            return 403, "bad twilio signature", None
        msg = _from_twilio_form(form)
    if msg and msg.sid:
        con = connect(cfg.db_path)
        try:
            upsert_message(con, msg, source="webhook")
        finally:
            con.close()
    return 200, "", msg


def _from_twilio_form(form: dict[str, str]) -> Message | None:
    sid = form.get("MessageSid") or form.get("SmsSid") or ""
    if not sid:
        return None
    return Message(
        sid=sid,
        direction="inbound",
        from_n=form.get("From") or "",
        to=form.get("To") or "",
        body=form.get("Body") or "",
        status=form.get("SmsStatus") or "received",
    )


def _from_telnyx_json(raw: bytes) -> Message | None:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        return None
    data = payload.get("data") or payload
    payload_obj = data.get("payload") if isinstance(data, dict) else None
    if isinstance(payload_obj, dict):
        data = payload_obj
    if not isinstance(data, dict):
        return None
    sid = str(data.get("id") or data.get("message_id") or "")
    from_n = ""
    from_obj = data.get("from") or {}
    if isinstance(from_obj, dict):
        from_n = from_obj.get("phone_number") or ""
    elif isinstance(from_obj, str):
        from_n = from_obj
    to_n = ""
    to_obj = data.get("to")
    if isinstance(to_obj, list) and to_obj:
        first = to_obj[0]
        to_n = first.get("phone_number") if isinstance(first, dict) else str(first)
    elif isinstance(to_obj, dict):
        to_n = to_obj.get("phone_number") or ""
    elif isinstance(to_obj, str):
        to_n = to_obj
    body = data.get("text") or data.get("body") or ""
    if not sid:
        return None
    return Message(
        sid=sid,
        direction="inbound",
        from_n=from_n,
        to=to_n,
        body=body,
        status="received",
    )
