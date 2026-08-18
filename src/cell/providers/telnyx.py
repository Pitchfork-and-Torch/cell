"""Telnyx Messaging API. Cheaper than Twilio; 10DLC still required in the US."""

from __future__ import annotations

from typing import Any

from cell.config import Config
from cell.e164 import normalize
from cell.httputil import HttpError, request
from cell.models import Message, PhoneNumber, ProviderError
from cell.providers.base import Provider

API = "https://api.telnyx.com/v2"


class TelnyxProvider(Provider):
    name = "telnyx"

    def __init__(self, cfg: Config):
        super().__init__(cfg)
        self.key = (cfg.telnyx_api_key or "").strip()
        if not self.key:
            raise ProviderError("Telnyx API key missing. Set TELNYX_API_KEY or run cell init.")

    def _req(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            _status, body, _raw = request(method, API + path, bearer=self.key, **kwargs)
        except HttpError as e:
            raise ProviderError(str(e), status=e.status) from None
        return body

    def status(self) -> dict:
        nums = self.list_owned_numbers()
        default = self.cfg.from_number or (nums[0].e164 if nums else "")
        return {
            "provider": "telnyx",
            "from_number": default or None,
            "numbers": [n.to_dict() for n in nums],
            "balance": None,
            "note": "Telnyx Mission Control holds balance. US SMS still needs 10DLC or toll-free verification.",
        }

    def list_owned_numbers(self) -> list[PhoneNumber]:
        body = self._req("GET", "/phone_numbers", query={"page[size]": 50})
        out: list[PhoneNumber] = []
        for item in body.get("data") or []:
            phone = item.get("phone_number") or ""
            feats = item.get("features") or {}
            if isinstance(feats, list):
                names = {str(x).lower() for x in feats}
                sms = "sms" in names
                voice = "voice" in names or "calling" in names
                mms = "mms" in names
            else:
                sms = True
                voice = True
                mms = False
            out.append(
                PhoneNumber(
                    e164=phone,
                    sms=sms,
                    voice=voice,
                    mms=mms,
                    sid=str(item.get("id") or ""),
                    friendly=item.get("connection_name") or "",
                )
            )
        return out

    def search_numbers(
        self,
        *,
        country: str = "US",
        area_code: str | None = None,
        sms: bool = True,
        voice: bool = True,
        limit: int = 10,
    ) -> list[PhoneNumber]:
        query: dict[str, Any] = {
            "filter[country_code]": (country or "US").upper(),
            "filter[limit]": min(limit, 20),
        }
        if area_code:
            query["filter[national_destination_code]"] = area_code
        if sms:
            query["filter[features][]"] = "sms"
        body = self._req("GET", "/available_phone_numbers", query=query)
        out: list[PhoneNumber] = []
        for item in (body.get("data") or [])[:limit]:
            out.append(
                PhoneNumber(
                    e164=item.get("phone_number") or "",
                    sms=True,
                    voice=True,
                    extra={
                        "region": (item.get("region_information") or [{}])[0].get("region_name")
                        if isinstance(item.get("region_information"), list)
                        else "",
                    },
                )
            )
        return out

    def buy_number(self, e164: str) -> PhoneNumber:
        n = normalize(e164)
        body = self._req("POST", "/number_orders", json_body={"phone_numbers": [{"phone_number": n}]})
        data = body.get("data") or {}
        return PhoneNumber(
            e164=n,
            sms=True,
            voice=True,
            sid=str(data.get("id") or ""),
            extra={"status": data.get("status") or "ordered"},
        )

    def send_sms(self, to: str, body: str, from_n: str | None = None) -> Message:
        src = normalize(from_n or self.cfg.from_number)
        dest = normalize(to)
        if not body.strip():
            raise ProviderError("empty SMS body")
        payload = self._req(
            "POST",
            "/messages",
            json_body={"from": src, "to": dest, "text": body},
        )
        data = payload.get("data") or payload
        to_list = data.get("to") or []
        status = ""
        if to_list and isinstance(to_list[0], dict):
            status = to_list[0].get("status") or ""
        return Message(
            sid=str(data.get("id") or ""),
            direction="outbound",
            from_n=src,
            to=dest,
            body=body,
            status=status or "queued",
        )

    def list_messages(self, *, limit: int = 20, with_n: str | None = None) -> list[Message]:
        # Telnyx message list is profile-oriented. Prefer local store + inbound webhook.
        raise ProviderError(
            "Telnyx has no simple account-wide inbox list like Twilio. "
            "Run cell webhook and pin the messaging profile inbound URL, then use cell inbox (local) or cell watch."
        )

    def set_sms_webhook(self, url: str, number: str | None = None) -> dict:
        return {
            "number": number or self.cfg.from_number,
            "sms_url": url,
            "note": "Set this URL on the Telnyx Messaging Profile inbound webhook in Mission Control (or PATCH the profile).",
        }
