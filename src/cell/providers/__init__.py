from __future__ import annotations

from cell.config import Config
from cell.models import ProviderError
from cell.providers.base import Provider
from cell.providers.modem import ModemProvider
from cell.providers.telnyx import TelnyxProvider
from cell.providers.twilio import TwilioProvider


def get_provider(cfg: Config) -> Provider:
    name = (cfg.provider or "twilio").lower()
    if name == "twilio":
        return TwilioProvider(cfg)
    if name == "telnyx":
        return TelnyxProvider(cfg)
    if name in ("modem", "mmcli", "usb"):
        return ModemProvider(cfg)
    raise ProviderError(f"unknown provider: {name}")


__all__ = ["Provider", "get_provider", "TwilioProvider", "TelnyxProvider", "ModemProvider"]
