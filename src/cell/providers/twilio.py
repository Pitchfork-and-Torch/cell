"""Twilio Programmable SMS + Voice + Incoming Numbers."""

from __future__ import annotations

import base64
import hashlib
import hmac
from typing import Any

from cell.config import Config
from cell.e164 import normalize
from cell.httputil import HttpError, request
from cell.models import CallResult, Message, PhoneNumber, ProviderError
from cell.providers.base import Provider

API = "https://api.twilio.com/2010-04-01"


class TwilioProvider(Provider):
    name = "twilio"

    def __init__(self, cfg: Config):
        super().__init__(cfg)
        self.sid = (cfg.twilio_account_sid or "").strip()
        self.token = (cfg.twilio_auth_token or "").strip()
        if not self.sid or not self.token:
            raise ProviderError(
                "Twilio credentials missing. Run: cell init   or set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN"
            )
        if not self.sid.startswith("AC"):
            raise ProviderError("TWILIO_ACCOUNT_SID should start with AC")

    def _auth(self) -> tuple[str, str]:
        return self.sid, self.token

    def _url(self, suffix: str) -> str:
        return f"{API}/Accounts/{self.sid}/{suffix}"

    def _req(self, method: str, suffix: str, **kwargs: Any) -> Any:
        try:
            _status, body, _raw = request(method, self._url(suffix), basic=self._auth(), **kwargs)
        except HttpError as e:
            raise ProviderError(str(e), status=e.status) from None
        return body

    def status(self) -> dict:
        try:
            _status, acct, _raw = request(
                "GET",
                f"{API}/Accounts/{self.sid}.json",
                basic=self._auth(),
            )
        except HttpError as e:
            raise ProviderError(str(e), status=e.status) from None
        bal: dict = {}
        try:
            _status, bal, _raw = request(
                "GET",
                f"{API}/Accounts/{self.sid}/Balance.json",
                basic=self._auth(),
            )
        except HttpError:
            bal = {}
        nums = self.list_owned_numbers()
        default = self.cfg.from_number or (nums[0].e164 if nums else "")
        return {
            "provider": "twilio",
            "account": acct.get("friendly_name") or acct.get("sid"),
            "account_status": acct.get("status"),
            "account_type": acct.get("type"),
            "balance": bal.get("balance"),
            "currency": bal.get("currency"),
            "from_number": default or None,
            "numbers": [n.to_dict() for n in nums],
            "trial": (acct.get("type") or "").lower() == "trial",
        }

    def list_owned_numbers(self) -> list[PhoneNumber]:
        body = self._req("GET", "IncomingPhoneNumbers.json", query={"PageSize": 50})
        out: list[PhoneNumber] = []
        for item in body.get("incoming_phone_numbers") or []:
            caps = item.get("capabilities") or {}
            out.append(
                PhoneNumber(
                    e164=item.get("phone_number") or "",
                    sms=_truthy(caps.get("sms")),
                    voice=_truthy(caps.get("voice")),
                    mms=_truthy(caps.get("mms")),
                    sid=item.get("sid") or "",
                    friendly=item.get("friendly_name") or "",
                    extra={"sms_url": item.get("sms_url") or ""},
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
        country = (country or "US").upper()
        query: dict[str, Any] = {"PageSize": min(limit, 20)}
        if sms:
            query["SmsEnabled"] = "true"
        if voice:
            query["VoiceEnabled"] = "true"
        if area_code:
            query["AreaCode"] = area_code
        body = self._req("GET", f"AvailablePhoneNumbers/{country}/Local.json", query=query)
        out: list[PhoneNumber] = []
        for item in (body.get("available_phone_numbers") or [])[:limit]:
            caps = item.get("capabilities") or {}
            out.append(
                PhoneNumber(
                    e164=item.get("phone_number") or "",
                    sms=_truthy(caps.get("sms")),
                    voice=_truthy(caps.get("voice")),
                    mms=_truthy(caps.get("MMS") or caps.get("mms")),
                    friendly=item.get("friendly_name") or item.get("locality") or "",
                    extra={
                        "region": item.get("region") or "",
                        "locality": item.get("locality") or "",
                        "iso_country": item.get("iso_country") or country,
                    },
                )
            )
        return out

    def buy_number(self, e164: str) -> PhoneNumber:
        n = normalize(e164)
        body = self._req("POST", "IncomingPhoneNumbers.json", form={"PhoneNumber": n})
        caps = body.get("capabilities") or {}
        return PhoneNumber(
            e164=body.get("phone_number") or n,
            sms=_truthy(caps.get("sms")),
            voice=_truthy(caps.get("voice")),
            mms=_truthy(caps.get("mms")),
            sid=body.get("sid") or "",
            friendly=body.get("friendly_name") or "",
        )

    def send_sms(self, to: str, body: str, from_n: str | None = None) -> Message:
        src = normalize(from_n or self.cfg.from_number)
        dest = normalize(to)
        if not body.strip():
            raise ProviderError("empty SMS body")
        payload = self._req(
            "POST",
            "Messages.json",
            form={"To": dest, "From": src, "Body": body},
        )
        return _msg_from_twilio(payload)

    def list_messages(self, *, limit: int = 20, with_n: str | None = None) -> list[Message]:
        query: dict[str, Any] = {"PageSize": min(max(limit, 1), 100)}
        if with_n:
            query["From"] = normalize(with_n)
        body = self._req("GET", "Messages.json", query=query)
        items = [_msg_from_twilio(x) for x in body.get("messages") or []]
        if with_n and len(items) < limit:
            # also messages we sent to that number
            extra = self._req(
                "GET",
                "Messages.json",
                query={"PageSize": min(max(limit, 1), 100), "To": normalize(with_n)},
            )
            seen = {m.sid for m in items}
            for x in extra.get("messages") or []:
                m = _msg_from_twilio(x)
                if m.sid not in seen:
                    items.append(m)
        items.sort(key=lambda m: m.created, reverse=True)
        return items[:limit]

    def place_call(self, to: str, *, say: str | None = None, twiml_url: str | None = None) -> CallResult:
        dest = normalize(to)
        src = normalize(self.cfg.from_number)
        form: dict[str, Any] = {"To": dest, "From": src}
        if twiml_url:
            form["Url"] = twiml_url
        else:
            text = say or "This is Grok calling from the cell tool. Goodbye."
            # Keep TwiML ASCII-safe.
            safe = (
                text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
            )
            form["Twiml"] = f"<Response><Say>{safe}</Say></Response>"
        body = self._req("POST", "Calls.json", form=form)
        return CallResult(
            sid=body.get("sid") or "",
            status=body.get("status") or "",
            from_n=body.get("from") or src,
            to=body.get("to") or dest,
            extra={"direction": body.get("direction") or "outbound-api"},
        )

    def set_sms_webhook(self, url: str, number: str | None = None) -> dict:
        target = normalize(number or self.cfg.from_number)
        owned = self.list_owned_numbers()
        match = next((n for n in owned if n.e164 == target), None)
        if not match or not match.sid:
            raise ProviderError(f"number not on this Twilio account: {target}")
        body = self._req(
            "POST",
            f"IncomingPhoneNumbers/{match.sid}.json",
            form={"SmsUrl": url, "SmsMethod": "POST"},
        )
        return {
            "number": body.get("phone_number") or target,
            "sms_url": body.get("sms_url") or url,
            "sid": body.get("sid") or match.sid,
            "warning": "This replaces the previous SMS webhook on this number. Do not point a HavenID number here unless you intend to take inbound away from HavenID.",
        }

    def validate_webhook(self, url: str, params: dict[str, str], signature: str) -> bool:
        return twilio_signature_ok(self.token, url, params, signature)


def _msg_from_twilio(item: dict) -> Message:
    direction = item.get("direction") or ""
    if direction.startswith("inbound"):
        direction = "inbound"
    elif direction.startswith("outbound"):
        direction = "outbound"
    err = item.get("error_message") or ""
    if item.get("error_code") and not err:
        err = str(item.get("error_code"))
    return Message(
        sid=item.get("sid") or "",
        direction=direction,
        from_n=item.get("from") or "",
        to=item.get("to") or "",
        body=item.get("body") or "",
        status=item.get("status") or "",
        created=item.get("date_created") or item.get("date_sent") or "",
        error=err,
        price=str(item.get("price") or ""),
        segments=str(item.get("num_segments") or ""),
    )


def twilio_signature_ok(auth_token: str, url: str, params: dict[str, str], header: str) -> bool:
    if not auth_token or not header:
        return False
    pieces = [url]
    for key in sorted(params):
        pieces.append(key)
        pieces.append(params[key])
    digest = hmac.new(auth_token.encode("utf-8"), "".join(pieces).encode("utf-8"), hashlib.sha1).digest()
    expected = base64.b64encode(digest).decode("ascii")
    return hmac.compare_digest(expected, header)


def _truthy(val: Any) -> bool:
    if isinstance(val, bool):
        return val
    if val is None:
        return False
    return str(val).lower() in ("true", "1", "yes")
