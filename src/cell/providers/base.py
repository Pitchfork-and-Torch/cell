from __future__ import annotations

from abc import ABC, abstractmethod

from cell.config import Config
from cell.models import CallResult, Message, PhoneNumber


class Provider(ABC):
    name = "base"

    def __init__(self, cfg: Config):
        self.cfg = cfg

    @abstractmethod
    def status(self) -> dict:
        raise NotImplementedError

    @abstractmethod
    def list_owned_numbers(self) -> list[PhoneNumber]:
        raise NotImplementedError

    def search_numbers(
        self,
        *,
        country: str = "US",
        area_code: str | None = None,
        sms: bool = True,
        voice: bool = True,
        limit: int = 10,
    ) -> list[PhoneNumber]:
        raise NotImplementedError(f"{self.name} does not implement number search")

    def buy_number(self, e164: str) -> PhoneNumber:
        raise NotImplementedError(f"{self.name} does not implement number buy")

    @abstractmethod
    def send_sms(self, to: str, body: str, from_n: str | None = None) -> Message:
        raise NotImplementedError

    def list_messages(self, *, limit: int = 20, with_n: str | None = None) -> list[Message]:
        raise NotImplementedError(f"{self.name} does not implement message list (use local webhook store)")

    def place_call(self, to: str, *, say: str | None = None, twiml_url: str | None = None) -> CallResult:
        raise NotImplementedError(f"{self.name} does not implement voice yet")

    def set_sms_webhook(self, url: str, number: str | None = None) -> dict:
        raise NotImplementedError(f"{self.name} does not implement webhook pin")
