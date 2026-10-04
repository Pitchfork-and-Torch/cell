"""Map CPaaS error codes to short recovery hints. Never log secrets."""

from __future__ import annotations

from typing import Any

# Twilio Messaging / Voice / REST. Values are operator-facing, ASCII only.
TWILIO_HINTS: dict[int, str] = {
    20003: "Auth failed. Check TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN (cell init / CELL_ENV_FILE).",
    20008: "Twilio rejected the request signature or parameters.",
    20404: "Twilio resource not found (wrong SID, number, or account).",
    21211: "Invalid To number, or a Twilio trial can only SMS verified destinations.",
    21212: "Invalid From number. Set from_number / CELL_FROM to a number this account owns.",
    21214: "To number cannot be reached.",
    21408: "Permission to send to this region is denied on this account.",
    21606: "From number is not a valid SMS-capable number on this account.",
    21608: "Twilio trial: the To number is not verified. Verify it or upgrade the account.",
    21610: "Recipient unsubscribed (STOP). Do not send again until they START.",
    21612: "Twilio cannot route to this To number.",
    21614: "To is not a mobile / not SMS-capable.",
    21704: "The From number is not owned by this account.",
    30001: "Queue overflow. Wait and retry; lower send rate.",
    30002: "Account suspended. Check the Twilio console.",
    30003: "Unreachable destination handset.",
    30004: "Message blocked by carrier or recipient.",
    30005: "Unknown destination. Check the To number.",
    30006: "Landline or unreachable for SMS.",
    30007: "Carrier filtered the content. Change the body; this is not a CLI bug.",
    30008: "Unknown upstream error. Retry once, then check Twilio debugger.",
    30032: "Toll-free verification required, not a CLI bug.",
    30034: "US A2P 10DLC registration required, not a CLI bug.",
    30035: "10DLC campaign missing or not approved.",
    30036: "10DLC brand missing or not approved.",
    30037: "From number is not linked to an approved 10DLC campaign.",
    30038: "10DLC campaign is not allowed to send this traffic.",
}

TELNYX_HINTS: dict[str, str] = {
    "10009": "Telnyx auth failed. Check TELNYX_API_KEY.",
    "10011": "Telnyx rejected the payload. Check From/To and messaging profile.",
}


def extract_code(parsed: Any) -> int | str | None:
    if not isinstance(parsed, dict):
        return None
    c = parsed.get("code")
    if isinstance(c, bool):
        return None
    if isinstance(c, (int, str)) and str(c).strip():
        return c
    errors = parsed.get("errors")
    if isinstance(errors, list) and errors:
        first = errors[0]
        if isinstance(first, dict):
            c = first.get("code")
            if isinstance(c, bool):
                return None
            if isinstance(c, (int, str)) and str(c).strip():
                return c
    return None


def hint_for(code: int | str | None) -> str | None:
    if code is None or isinstance(code, bool):
        return None
    if isinstance(code, int):
        return TWILIO_HINTS.get(code) or TELNYX_HINTS.get(str(code))
    text = str(code).strip()
    if not text:
        return None
    if text in TELNYX_HINTS:
        return TELNYX_HINTS[text]
    try:
        return TWILIO_HINTS.get(int(text))
    except (TypeError, ValueError):
        return None


def annotate(message: str, code: int | str | None = None) -> str:
    msg = message or ""
    h = hint_for(code)
    if h and h not in msg:
        return f"{msg} Hint: {h}"
    return msg
