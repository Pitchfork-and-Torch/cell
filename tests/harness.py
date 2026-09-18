"""Isolated CELL_HOME + carrier HTTP tripwire for unit tests."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from cell.providers.fake import FakeProvider

_ENV_KEYS = (
    "CELL_HOME",
    "CELL_ENV_FILE",
    "CELL_PROVIDER",
    "CELL_FROM",
    "CELL_AUTO_CONFIRM",
    "CELL_FAKE",
    "CELL_PUBLIC_URL",
    "CELL_WEBHOOK_PORT",
    "TWILIO_ACCOUNT_SID",
    "TWILIO_AUTH_TOKEN",
    "TWILIO_PHONE_NUMBER",
    "TELNYX_API_KEY",
)

# Reserved test numbers (NANP 555). Not a live handset.
FROM_N = "+15125550100"
TO_N = "+15125550199"
SID = "ACaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
TOKEN = "unit-test-only-token-zz"


class CellHomeCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory(prefix="cell-test-")
        self.home = Path(self._tmpdir.name)
        self._saved: dict[str, str | None] = {}
        for key in _ENV_KEYS:
            self._saved[key] = os.environ.pop(key, None)
        os.environ["CELL_HOME"] = str(self.home)
        FakeProvider.reset()
        # Patch urlopen so every provider import style is blocked (no live carrier).
        self._http = mock.patch("urllib.request.urlopen", side_effect=self._blocked_http)
        self._http.start()
        self.addCleanup(self._http.stop)

    def tearDown(self) -> None:
        FakeProvider.reset()
        for key, val in self._saved.items():
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val
        self._tmpdir.cleanup()

    @staticmethod
    def _blocked_http(*_args, **_kwargs):
        raise AssertionError("cell test blocked carrier HTTP")

    def write_twilio_config(
        self,
        *,
        from_number: str = FROM_N,
        auto_confirm: bool = False,
        sms_limit: int = 20,
        call_limit: int = 5,
        sid: str = SID,
        token: str = TOKEN,
    ) -> None:
        auto = "true" if auto_confirm else "false"
        (self.home / "config.toml").write_text(
            (
                'provider = "twilio"\n'
                f'from_number = "{from_number}"\n'
                f"daily_sms_limit = {int(sms_limit)}\n"
                f"daily_call_limit = {int(call_limit)}\n"
                f"auto_confirm = {auto}\n"
                "webhook_port = 8788\n"
                'public_url = ""\n'
                'country = "US"\n'
            ),
            encoding="utf-8",
        )
        (self.home / "secrets.toml").write_text(
            (
                f'twilio_account_sid = "{sid}"\n'
                f'twilio_auth_token = "{token}"\n'
                'telnyx_api_key = ""\n'
            ),
            encoding="utf-8",
        )

    def enable_fake(self, *, from_number: str = FROM_N, sms_limit: int = 20) -> None:
        os.environ["CELL_PROVIDER"] = "fake"
        os.environ["CELL_FAKE"] = "1"
        os.environ["CELL_FROM"] = from_number
        (self.home / "config.toml").write_text(
            (
                'provider = "fake"\n'
                f'from_number = "{from_number}"\n'
                f"daily_sms_limit = {int(sms_limit)}\n"
                "daily_call_limit = 5\n"
                "auto_confirm = false\n"
                "webhook_port = 8788\n"
                'public_url = ""\n'
                'country = "US"\n'
            ),
            encoding="utf-8",
        )
        (self.home / "secrets.toml").write_text(
            'twilio_account_sid = ""\ntwilio_auth_token = ""\ntelnyx_api_key = ""\n',
            encoding="utf-8",
        )
