"""Future USB cellular modem backend (ModemManager / AT commands). Not implemented."""

from __future__ import annotations

from cell.models import Message, PhoneNumber, ProviderError
from cell.providers.base import Provider


class ModemProvider(Provider):
    name = "modem"

    def _dead(self, action: str) -> None:
        raise ProviderError(
            f"USB modem backend is a reserved extension point ({action}). "
            "On Linux the planned path is ModemManager `mmcli` (SMS via --messaging-create-sms / --messaging-send). "
            "On Windows the planned path is a COM-port AT command session (AT+CMGF=1, AT+CMGS). "
            "No dongle is required for the default Twilio/Telnyx backends."
        )

    def status(self) -> dict:
        self._dead("status")
        return {}

    def list_owned_numbers(self) -> list[PhoneNumber]:
        self._dead("list numbers")
        return []

    def send_sms(self, to: str, body: str, from_n: str | None = None) -> Message:
        self._dead("send SMS")
        return Message(sid="", direction="outbound", from_n="", to=to, body=body, status="unsent")
