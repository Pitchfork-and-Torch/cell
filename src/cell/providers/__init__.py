from __future__ import annotations

import os

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
    if name == "fake":
        flag = (os.environ.get("CELL_FAKE") or "").strip().lower()
        if flag not in ("1", "true", "yes"):
            raise ProviderError("fake provider is test-only. Set CELL_FAKE=1 to enable.")
        from cell.providers.fake import FakeProvider

        return FakeProvider(cfg)
    raise ProviderError(f"unknown provider: {name}")


__all__ = ["Provider", "get_provider", "TwilioProvider", "TelnyxProvider", "ModemProvider"]
