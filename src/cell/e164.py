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

# ITU E.161 / NANP vanity keypad (1-800-FLOWERS -> 1-800-3569377).
_VANITY = str.maketrans(
    {
        "A": "2", "B": "2", "C": "2",
        "D": "3", "E": "3", "F": "3",
        "G": "4", "H": "4", "I": "4",
        "J": "5", "K": "5", "L": "5",
        "M": "6", "N": "6", "O": "6",
        "P": "7", "Q": "7", "R": "7", "S": "7",
        "T": "8", "U": "8", "V": "8",
        "W": "9", "X": "9", "Y": "9", "Z": "9",
        "a": "2", "b": "2", "c": "2",
        "d": "3", "e": "3", "f": "3",
        "g": "4", "h": "4", "i": "4",
        "j": "5", "k": "5", "l": "5",
        "m": "6", "n": "6", "o": "6",
        "p": "7", "q": "7", "r": "7", "s": "7",
        "t": "8", "u": "8", "v": "8",
        "w": "9", "x": "9", "y": "9", "z": "9",
    }
)


class PhoneError(ValueError):
    pass


def _strip_extension(text: str) -> str:
    text = _EXT_URI.sub("", text)
    text = _EXT.sub("", text)
    return text.strip()


def _strip_uri_scheme(text: str) -> str:
    """Drop tel:/sip:/sips: so vanity mapping cannot turn 'tel' into 835.

    Contact apps and PBX paste often use RFC 3966 / SIP URIs. Without this,
    translate(_VANITY) maps T->8, E->3, L->5 and 'tel:+15551234567' becomes
    the wrong E.164 +83515551234567.
    """
    lower = text.lower()
    for prefix in ("tel:", "sips:", "sip:"):
        if lower.startswith(prefix):
            text = text[len(prefix) :]
            break
    # Drop URI parameters / headers and user@host wrappers.
    if "@" in text:
        text = text.split("@", 1)[0]
    if ";" in text:
        text = text.split(";", 1)[0]
    if "?" in text:
        text = text.split("?", 1)[0]
    return text.strip()


def normalize(raw: str, default_cc: str = "1") -> str:
    text = (raw or "").strip()
    if not text:
        raise PhoneError("empty phone number")
    text = _strip_uri_scheme(text)
    if not text:
        raise PhoneError("empty phone number")
    text = _strip_extension(text)
    if not text:
        raise PhoneError("empty phone number")
    # Map vanity letters before digit scrubbing so FLOWERS is not dropped.
    # Require at least one digit so pure garbage ("not-a-number") still errors.
    if any(ch.isalpha() for ch in text) and any(ch.isdigit() for ch in text):
        text = text.translate(_VANITY)
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
