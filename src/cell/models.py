from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class PhoneNumber:
    e164: str
    sms: bool = False
    voice: bool = False
    mms: bool = False
    sid: str = ""
    friendly: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d


@dataclass
class Message:
    sid: str
    direction: str
    from_n: str
    to: str
    body: str
    status: str
    created: str = ""
    error: str = ""
    price: str = ""
    segments: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CallResult:
    sid: str
    status: str
    from_n: str
    to: str
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ProviderError(RuntimeError):
    def __init__(self, message: str, code: str | int | None = None, status: int | None = None):
        super().__init__(message)
        self.code = code
        self.status = status

    def to_dict(self) -> dict[str, Any]:
        return {"error": str(self), "code": self.code, "status": self.status}


class NeedConfirm(RuntimeError):
    """Raised when an expensive action needs --yes."""
