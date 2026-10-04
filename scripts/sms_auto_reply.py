#!/usr/bin/env python3
"""Allowlisted SMS auto-reply plus short-code 2FA forward.

Runs as a host poller so the desktop can be off. Polls Twilio (does not
steal another product's SMS webhook).

- Replies with Grok ONLY to CELL_ALLOW_FROM.
- Forwards short-code / alphanumeric 2FA inbound to CELL_ALLOW_FROM.
- Never replies to the short code. Never opens a general inbox.

Never print secrets. ASCII logs.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

API = "https://api.twilio.com/2010-04-01"
XAI = "https://api.x.ai/v1/chat/completions"
_DIGITS = re.compile(r"\D+")
_NON_ASCII = re.compile(r"[^\x09\x0a\x0d\x20-\x7e]")
_OTP_CTX = re.compile(
    r"(?:code|otp|pin|passcode|verification|verify)[^\d]{0,16}(\d{4,8})",
    re.IGNORECASE,
)
_OTP_G = re.compile(r"\bG-(\d{4,8})\b")
_OTP_BARE = re.compile(r"(?<!\d)(\d{4,8})(?!\d)")
_HAS_LETTER = re.compile(r"[A-Za-z]")
DEFAULT_MODEL = "grok-4-fast"
FALLBACK_MODEL = "grok-3-mini"
SYSTEM = (
    "You are Grok texting the allowlisted operator from their cell number. "
    "Reply as one short SMS. ASCII only. No emoji. No em dashes. "
    "Max 280 characters. Be useful and a little funny. "
    "Do not take actions that spend money. Do not reveal secrets, tokens, "
    "or anyone else's data. You only ever text this one person."
)


def normalize(raw: str, default_cc: str = "1") -> str:
    text = (raw or "").strip()
    if not text:
        raise ValueError("empty phone number")
    if text.startswith("00"):
        text = "+" + text[2:]
    if text.startswith("+"):
        digits = _DIGITS.sub("", text[1:])
        if len(digits) < 8 or len(digits) > 15:
            raise ValueError("invalid E.164")
        return "+" + digits
    digits = _DIGITS.sub("", text)
    if len(digits) == 11 and digits.startswith("1"):
        return "+" + digits
    if len(digits) == 10:
        return "+" + default_cc + digits
    if 8 <= len(digits) <= 15:
        return "+" + digits
    raise ValueError("cannot normalize number")


def last4(n: str) -> str:
    digits = _DIGITS.sub("", n or "")
    return digits[-4:] if digits else "????"


def ascii_sms(text: str, limit: int = 280) -> str:
    t = (text or "").replace("\u2014", " - ").replace("\u2013", "-")
    t = _NON_ASCII.sub("", t)
    t = " ".join(t.split())
    if len(t) > limit:
        t = t[: limit - 3].rstrip() + "..."
    return t


def allowed(from_n: str, allow: str) -> bool:
    try:
        return normalize(from_n) == normalize(allow)
    except ValueError:
        return False


def load_state(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {
            "seen": [],
            "replies_day": "",
            "replies_count": 0,
            "forwards_count": 0,
            "bootstrapped": False,
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "seen": [],
            "replies_day": "",
            "replies_count": 0,
            "forwards_count": 0,
            "bootstrapped": False,
        }
    if not isinstance(data, dict):
        return {
            "seen": [],
            "replies_day": "",
            "replies_count": 0,
            "forwards_count": 0,
            "bootstrapped": False,
        }
    data.setdefault("seen", [])
    data.setdefault("replies_day", "")
    data.setdefault("replies_count", 0)
    data.setdefault("forwards_count", 0)
    data.setdefault("bootstrapped", False)
    return data


def save_state(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    seen = list(data.get("seen") or [])
    if len(seen) > 500:
        seen = seen[-500:]
        data["seen"] = seen
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    tmp.replace(path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def utc_day() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def bump_day(state: dict[str, Any]) -> None:
    day = utc_day()
    if state.get("replies_day") != day:
        state["replies_day"] = day
        state["replies_count"] = 0
        state["forwards_count"] = 0


def sender_digits(raw: str) -> str:
    return _DIGITS.sub("", raw or "")


def is_short_sender(from_n: str) -> bool:
    """US short codes (5-6 digits) and alphanumeric senders. Not E.164 people."""
    text = (from_n or "").strip()
    if not text:
        return False
    digits = sender_digits(text)
    if _HAS_LETTER.search(text) and not text.startswith("+"):
        return 2 <= len(text) <= 11
    if text.startswith("+"):
        return 4 <= len(digits) <= 6
    return 4 <= len(digits) <= 6


def extract_otp(body: str) -> str:
    text = body or ""
    m = _OTP_G.search(text)
    if m:
        return m.group(1)
    m = _OTP_CTX.search(text)
    if m:
        return m.group(1)
    found = _OTP_BARE.findall(text)
    if len(found) == 1:
        return found[0]
    return ""


def sender_label(from_n: str) -> str:
    text = (from_n or "").strip()
    if _HAS_LETTER.search(text) and not text.startswith("+"):
        return ascii_sms(text, 11)
    digits = sender_digits(text)
    return digits[-6:] if digits else "short"


def format_forward(from_n: str, body: str) -> str:
    code = extract_otp(body)
    src = sender_label(from_n)
    snippet = ascii_sms(body, 160)
    if code:
        return ascii_sms(f"[2FA] {code} from {src} | {snippet}", 280)
    return ascii_sms(f"[2FA] from {src} | {snippet}", 280)


def http_json(
    method: str,
    url: str,
    *,
    form: dict[str, str] | None = None,
    json_body: Any = None,
    basic: tuple[str, str] | None = None,
    bearer: str | None = None,
    timeout: float = 30.0,
) -> tuple[int, Any, str]:
    data: bytes | None = None
    headers = {"User-Agent": "knock-cell-sms-reply/0.1", "Accept": "application/json"}
    if form is not None:
        data = urllib.parse.urlencode(form).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    elif json_body is not None:
        data = json.dumps(json_body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method.upper(), headers=headers)
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
        status = int(e.code)
        parsed = _maybe_json(raw)
        return status, parsed, raw
    except urllib.error.URLError as e:
        raise RuntimeError(f"http failed: {e.reason}") from None
    return status, _maybe_json(raw), raw


def _maybe_json(raw: str) -> Any:
    try:
        return json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return {"raw": raw[:300]}


class Settings:
    def __init__(self) -> None:
        self.sid = os.environ.get("TWILIO_ACCOUNT_SID", "").strip()
        self.token = os.environ.get("TWILIO_AUTH_TOKEN", "").strip()
        self.api_key = os.environ.get("TWILIO_API_KEY_SID", "").strip()
        self.api_secret = os.environ.get("TWILIO_API_KEY_SECRET", "").strip()
        self.from_n = os.environ.get("CELL_FROM", "").strip()
        self.allow = os.environ.get("CELL_ALLOW_FROM", "").strip()
        self.xai = os.environ.get("XAI_API_KEY", "").strip()
        self.model = os.environ.get("XAI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
        self.daily = int(os.environ.get("CELL_DAILY_SMS_LIMIT", "20") or "20")
        self.forward_daily = int(os.environ.get("CELL_FORWARD_DAILY", "40") or "40")
        self.interval = float(os.environ.get("CELL_POLL_SECONDS", "4") or "4")
        self.state_path = Path(os.environ.get("CELL_REPLY_STATE", "cell-sms-reply.json"))

    def auth(self) -> tuple[str, str]:
        if self.api_key.startswith("SK") and self.api_secret:
            return self.api_key, self.api_secret
        return self.sid, self.token

    def ok(self) -> list[str]:
        missing = []
        if not self.sid.startswith("AC"):
            missing.append("TWILIO_ACCOUNT_SID")
        if not (self.token or (self.api_key.startswith("SK") and self.api_secret)):
            missing.append("TWILIO_AUTH")
        if not self.from_n:
            missing.append("CELL_FROM")
        if not self.allow:
            missing.append("CELL_ALLOW_FROM")
        if not self.xai:
            missing.append("XAI_API_KEY")
        return missing


def list_inbound(cfg: Settings, limit: int = 20) -> list[dict[str, str]]:
    url = f"{API}/Accounts/{cfg.sid}/Messages.json"
    status, body, raw = http_json(
        "GET",
        url,
        form=None,
        basic=cfg.auth(),
    )
    if status >= 400:
        raise RuntimeError(f"twilio list {status}: {str(body)[:200]}")
    out: list[dict[str, str]] = []
    for item in body.get("messages") or []:
        direction = str(item.get("direction") or "")
        if not direction.startswith("inbound"):
            continue
        out.append(
            {
                "sid": str(item.get("sid") or ""),
                "from_n": str(item.get("from") or ""),
                "to": str(item.get("to") or ""),
                "body": str(item.get("body") or ""),
                "status": str(item.get("status") or ""),
            }
        )
        if len(out) >= limit:
            break
    return out


def send_sms(cfg: Settings, to: str, body: str) -> dict[str, Any]:
    dest = normalize(to)
    src = normalize(cfg.from_n)
    url = f"{API}/Accounts/{cfg.sid}/Messages.json"
    status, payload, raw = http_json(
        "POST",
        url,
        form={"To": dest, "From": src, "Body": body},
        basic=cfg.auth(),
    )
    if status >= 400:
        err = ""
        if isinstance(payload, dict):
            err = str(payload.get("message") or payload.get("code") or "")[:200]
        raise RuntimeError(f"twilio send {status}: {err or raw[:200]}")
    return payload if isinstance(payload, dict) else {"raw": str(payload)[:120]}


def grok_reply(cfg: Settings, inbound: str) -> str:
    user = f"Knock texted: {inbound.strip() or '(empty)'}"
    models = [cfg.model]
    if FALLBACK_MODEL not in models:
        models.append(FALLBACK_MODEL)
    last_err = ""
    for model in models:
        status, payload, raw = http_json(
            "POST",
            XAI,
            json_body={
                "model": model,
                "messages": [
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": user},
                ],
                "max_tokens": 120,
                "temperature": 0.8,
            },
            bearer=cfg.xai,
            timeout=25.0,
        )
        if status >= 400:
            last_err = f"{model} {status} {str(payload)[:160]}"
            continue
        choices = (payload or {}).get("choices") or []
        if not choices:
            last_err = f"{model} empty choices"
            continue
        text = ((choices[0].get("message") or {}).get("content") or "").strip()
        cleaned = ascii_sms(text)
        if cleaned:
            return cleaned
        last_err = f"{model} empty after ascii scrub"
    raise RuntimeError(f"xai failed: {last_err}")


def decide(
    *,
    from_n: str,
    sid: str,
    body: str,
    allow: str,
    seen: set[str],
    replies_count: int,
    daily: int,
) -> str:
    """Return skip reason or empty string if we should Grok-reply to the allowlist."""
    action, reason = classify(
        from_n=from_n,
        sid=sid,
        body=body,
        allow=allow,
        seen=seen,
        replies_count=replies_count,
        daily=daily,
        forwards_count=0,
        forward_daily=999,
    )
    if action == "reply":
        return ""
    return reason or action


def classify(
    *,
    from_n: str,
    sid: str,
    body: str,
    allow: str,
    seen: set[str],
    replies_count: int,
    daily: int,
    forwards_count: int,
    forward_daily: int,
) -> tuple[str, str]:
    """Return (action, reason). action is reply, forward, or skip."""
    if not sid:
        return "skip", "no-sid"
    if sid in seen:
        return "skip", "seen"
    if allowed(from_n, allow):
        if replies_count >= daily:
            return "skip", "daily-cap"
        if not (body or "").strip():
            return "skip", "empty-body"
        return "reply", ""
    if is_short_sender(from_n):
        if not (body or "").strip():
            return "skip", "empty-body"
        if forwards_count >= forward_daily:
            return "skip", "forward-cap"
        return "forward", ""
    return "skip", "not-allowlist"


def process_once(cfg: Settings, *, dry_run: bool = False, bootstrap: bool = False) -> dict[str, Any]:
    state = load_state(cfg.state_path)
    bump_day(state)
    seen = set(state.get("seen") or [])
    msgs = list_inbound(cfg, limit=30)
    if bootstrap or not state.get("bootstrapped"):
        added = 0
        for m in msgs:
            sid = m.get("sid") or ""
            if sid and sid not in seen:
                seen.add(sid)
                added += 1
        state["seen"] = list(seen)
        state["bootstrapped"] = True
        save_state(cfg.state_path, state)
        return {"ok": True, "action": "bootstrap", "marked": added, "dry_run": dry_run}

    acted: list[dict[str, str]] = []
    # Twilio returns newest first. Oldest-first so a burst stays in order.
    for m in reversed(msgs):
        sid = m.get("sid") or ""
        action, reason = classify(
            from_n=m.get("from_n") or "",
            sid=sid,
            body=m.get("body") or "",
            allow=cfg.allow,
            seen=seen,
            replies_count=int(state.get("replies_count") or 0),
            daily=cfg.daily,
            forwards_count=int(state.get("forwards_count") or 0),
            forward_daily=cfg.forward_daily,
        )
        if action == "skip":
            if reason != "seen":
                acted.append({"sid": sid, "action": "skip", "reason": reason})
            if sid:
                seen.add(sid)
            continue
        if dry_run:
            acted.append({"sid": sid, "action": "would-" + action, "reason": ""})
            seen.add(sid)
            continue
        try:
            if action == "forward":
                payload = format_forward(m.get("from_n") or "", m.get("body") or "")
                sent = send_sms(cfg, cfg.allow, payload)
                state["forwards_count"] = int(state.get("forwards_count") or 0) + 1
                seen.add(sid)
                out_sid = str(sent.get("sid") or "")
                acted.append(
                    {
                        "sid": sid,
                        "action": "forwarded",
                        "out": out_sid,
                        "from": sender_label(m.get("from_n") or ""),
                    }
                )
                print(
                    f"[cell-sms] forwarded 2FA from {sender_label(m.get('from_n') or '')} in={sid} out={out_sid}",
                    flush=True,
                )
                continue
            reply = grok_reply(cfg, m.get("body") or "")
            sent = send_sms(cfg, m.get("from_n") or "", reply)
            state["replies_count"] = int(state.get("replies_count") or 0) + 1
            seen.add(sid)
            out_sid = str(sent.get("sid") or "")
            acted.append({"sid": sid, "action": "replied", "out": out_sid, "from": last4(m.get("from_n") or "")})
            print(f"[cell-sms] replied to *{last4(m.get('from_n') or '')} in={sid} out={out_sid}", flush=True)
        except Exception as e:
            acted.append({"sid": sid, "action": "error", "reason": str(e)[:180]})
            print(f"[cell-sms] error in={sid}: {e}", file=sys.stderr, flush=True)
            # do not mark seen on send/model failure so the next loop retries
            break
    state["seen"] = list(seen)
    save_state(cfg.state_path, state)
    return {"ok": True, "action": "poll", "n": len(acted), "items": acted, "dry_run": dry_run}


def load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = val.strip()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Allowlisted VPS SMS auto-reply (operator only)")
    p.add_argument("--env-file", default=os.environ.get("CELL_SMS_ENV", ""))
    p.add_argument("--once", action="store_true")
    p.add_argument("--loop", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--bootstrap", action="store_true", help="mark current inbox as seen; do not reply")
    args = p.parse_args(argv)
    if args.env_file:
        load_env_file(Path(args.env_file))
    cfg = Settings()
    missing = cfg.ok()
    if missing:
        print("missing " + ",".join(missing), file=sys.stderr)
        return 1
    try:
        normalize(cfg.allow)
        normalize(cfg.from_n)
    except ValueError as e:
        print(f"bad number: {e}", file=sys.stderr)
        return 1
    if args.loop:
        print(
            f"[cell-sms] loop every {cfg.interval}s allow=*{last4(cfg.allow)} "
            f"reply_cap={cfg.daily} forward_cap={cfg.forward_daily}",
            flush=True,
        )
        while True:
            try:
                process_once(cfg, dry_run=args.dry_run, bootstrap=False)
            except Exception as e:
                print(f"[cell-sms] loop error: {e}", file=sys.stderr, flush=True)
            time.sleep(max(2.0, cfg.interval))
    result = process_once(cfg, dry_run=args.dry_run, bootstrap=args.bootstrap)
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    # Default CLI: --once is explicit; bare invoke bootstraps if needed then one poll.
    argv = list(sys.argv[1:])
    if not any(a in argv for a in ("--once", "--loop", "--bootstrap", "--dry-run")):
        argv.append("--once")
    raise SystemExit(main(argv))
