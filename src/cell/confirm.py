"""Cost gates for send/call/buy."""

from __future__ import annotations

import sys

from cell.models import NeedConfirm


def gsm7_ok(text: str) -> bool:
    # Practical GSM-7: BMP latin + common punctuation. Not a full GSM table.
    for ch in text:
        o = ord(ch)
        if o > 126 and ch not in "\n\r\t":
            return False
    return True


def segments(text: str) -> int:
    if not text:
        return 1
    if gsm7_ok(text):
        if len(text) <= 160:
            return 1
        return (len(text) + 152) // 153
    if len(text) <= 70:
        return 1
    return (len(text) + 66) // 67


def sms_cost_note(text: str) -> str:
    n = segments(text)
    return (
        f"{n} SMS segment(s). Twilio US long-code list is about $0.0083/segment "
        f"plus carrier fees (~$0.0035-$0.005). Rough ceiling ~${0.014 * n:.3f}."
    )


def call_cost_note() -> str:
    return "Outbound US voice is typically about $0.014/min plus the called-party rate. Trial accounts can only call verified numbers."


def buy_cost_note() -> str:
    return "Twilio US local numbers are about $1.15/month. Toll-free about $2.15/month. US A2P 10DLC or toll-free verification is required for production SMS."


def require_yes(*, yes: bool, auto: bool, what: str, note: str, tty_prompt: bool = True) -> None:
    if yes or auto:
        return
    if tty_prompt and sys.stdin.isatty() and sys.stdout.isatty():
        print(f"{what}")
        print(note)
        ans = input("Type YES to continue: ").strip()
        if ans == "YES":
            return
        raise NeedConfirm("cancelled")
    raise NeedConfirm(f"{what} Needs --yes. {note}")
