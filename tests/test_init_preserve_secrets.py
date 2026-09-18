"""write_init must not wipe existing secrets when re-run empty."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path


class TestInitPreserveSecrets(unittest.TestCase):
    def test_reinit_keeps_secrets(self) -> None:
        home = Path(tempfile.mkdtemp(prefix="cell-init-"))
        os.environ["CELL_HOME"] = str(home)
        for k in (
            "TWILIO_ACCOUNT_SID",
            "TWILIO_AUTH_TOKEN",
            "TELNYX_API_KEY",
            "CELL_FROM",
            "TWILIO_PHONE_NUMBER",
            "CELL_ENV_FILE",
        ):
            os.environ.pop(k, None)

        from cell.config import load, write_init

        write_init(
            twilio_account_sid="ACaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            twilio_auth_token="secret-token-1",
            from_number="+15551234567",
        )
        write_init()
        cfg = load()
        self.assertEqual(cfg.twilio_account_sid, "ACaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        self.assertEqual(cfg.twilio_auth_token, "secret-token-1")


if __name__ == "__main__":
    unittest.main()
