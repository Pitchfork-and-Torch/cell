"""E.164 helpers. US 10-digit numbers become +1..."""

from __future__ import annotations

import re

_DIGITS = re.compile(r"\D+")
# Contact apps and PBX paste often append extensions. Digits-only scrubbing
# used to glue them onto the subscriber number (5125551212x99 -> +512555121299).
_EXT = re.compile(
    r"(?:[\s.;,]*(?:ext(?:ension)?|x|\#)\s*\.?\s*\d+\s*)$",
    re.IGNORECASE,
)
_EXT_URI = re.compile(r";ext=\d+\s*$", re.IGNORECASE)


class PhoneError(ValueError):
    pass


def _strip_extension(text: str) -> str:
    text = _EXT_URI.sub("", text)
    text = _EXT.sub("", text)
    return text.strip()


def normalize(raw: str, default_cc: str = "1") -> str:
    text = (raw or "").strip()
    if not text:
        raise PhoneError("empty phone number")
    text = _strip_extension(text)
    if not text:
        raise PhoneError("empty phone number")
    if text.startswith("00"):
        text = "+" + text[2:]
    # US/Canada international dialing prefix (011 + country code...).
    # Without this, "011441234567890" becomes +011441234567890.
    elif text.startswith("011"):
        text = "+" + text[3:]
    if text.startswith("+"):
        digits = _DIGITS.sub("", text[1:])
        if len(digits) < 8 or len(digits) > 15:
            raise PhoneError(f"invalid E.164: {raw}")
        return "+" + digits
    digits = _DIGITS.sub("", text)
    if len(digits) == 11 and digits.startswith("1"):
        return "+" + digits
    if len(digits) == 10:
        return "+" + default_cc + digits
    if 8 <= len(digits) <= 15:
        return "+" + digits
    raise PhoneError(f"cannot normalize number: {raw}")


def is_e164(raw: str) -> bool:
    try:
        n = normalize(raw)
    except PhoneError:
        return False
    return n.startswith("+") and n[1:].isdigit()
