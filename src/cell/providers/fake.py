"""In-memory provider for tests. Enable with CELL_PROVIDER=fake and CELL_FAKE=1.

Never talks to a carrier. Not for production.
"""

from __future__ import annotations

import uuid

from cell.e164 import normalize
from cell.models import CallResult, Message, PhoneNumber, ProviderError
from cell.providers.base import Provider


class FakeProvider(Provider):
    name = "fake"
    mailbox: list[Message] = []
    calls: list[CallResult] = []
    bought: list[PhoneNumber] = []
    webhook: dict[str, str] = {}

    @classmethod
    def reset(cls) -> None:
        cls.mailbox.clear()
        cls.calls.clear()
        cls.bought.clear()
        cls.webhook.clear()

    def status(self) -> dict:
        nums = self.list_owned_numbers()
        default = self.cfg.from_number or (nums[0].e164 if nums else "")
        return {
            "provider": "fake",
            "account": "fake",
            "account_status": "active",
            "account_type": "Full",
            "balance": "0",
            "currency": "USD",
            "from_number": default or None,
            "numbers": [n.to_dict() for n in nums],
            "trial": False,
        }

    def list_owned_numbers(self) -> list[PhoneNumber]:
        owned = list(type(self).bought)
        src = (self.cfg.from_number or "").strip()
        if src:
            n = normalize(src)
            if not any(x.e164 == n for x in owned):
                owned.insert(
                    0,
                    PhoneNumber(e164=n, sms=True, voice=True, sid="PNfake", friendly="fake"),
                )
        return owned

    def search_numbers(
        self,
        *,
        country: str = "US",
        area_code: str | None = None,
        sms: bool = True,
        voice: bool = True,
        limit: int = 10,
    ) -> list[PhoneNumber]:
        area = "".join(ch for ch in (area_code or "555") if ch.isdigit())[:3] or "555"
        return [
            PhoneNumber(
                e164=f"+1{area}5550100",
                sms=True,
                voice=True,
                extra={"locality": "Fake", "region": "TX", "iso_country": (country or "US").upper()},
            )
        ][: max(1, min(int(limit), 20))]

    def buy_number(self, e164: str) -> PhoneNumber:
        n = PhoneNumber(e164=normalize(e164), sms=True, voice=True, sid="PNbought", friendly="fake-bought")
        type(self).bought.append(n)
        return n

    def send_sms(self, to: str, body: str, from_n: str | None = None) -> Message:
        src = normalize(from_n or self.cfg.from_number)
        dest = normalize(to)
        if not (body or "").strip():
            raise ProviderError("empty SMS body")
        msg = Message(
            sid="SM" + uuid.uuid4().hex[:16],
            direction="outbound",
            from_n=src,
            to=dest,
            body=body,
            status="queued",
            created="2026-01-01T00:00:00Z",
        )
        type(self).mailbox.insert(0, msg)
        return msg

    def list_messages(self, *, limit: int = 20, with_n: str | None = None) -> list[Message]:
        items = list(type(self).mailbox)
        if with_n:
            peer = normalize(with_n)
            items = [m for m in items if m.from_n == peer or m.to == peer]
        return items[: max(1, min(int(limit), 100))]

    def place_call(self, to: str, *, say: str | None = None, twiml_url: str | None = None) -> CallResult:
        dest = normalize(to)
        src = normalize(self.cfg.from_number)
        result = CallResult(
            sid="CA" + uuid.uuid4().hex[:16],
            status="queued",
            from_n=src,
            to=dest,
            extra={"say": say or "", "url": twiml_url or "", "direction": "outbound-api"},
        )
        type(self).calls.append(result)
        return result

    def set_sms_webhook(self, url: str, number: str | None = None) -> dict:
        target = normalize(number or self.cfg.from_number)
        type(self).webhook = {"number": target, "sms_url": url}
        return {
            "number": target,
            "sms_url": url,
            "sid": "PNfake",
            "warning": "fake provider: webhook not pinned on a carrier.",
        }
