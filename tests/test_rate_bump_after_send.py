"""Daily SMS/call quota must not burn when the provider call fails."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cell.config import Config
from cell.models import Message, ProviderError
from cell import actions
from cell.store import connect, usage_today


def _cfg(home: Path) -> Config:
    return Config(
        home=home,
        provider="twilio",
        from_number="+15551112222",
        twilio_account_sid="ACtest",
        twilio_auth_token="token",
        daily_sms_limit=5,
        daily_call_limit=5,
        auto_confirm=True,
    )


class TestRateBumpAfterSend(unittest.TestCase):
    def test_failed_send_does_not_burn_sms_quota(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            cfg = _cfg(home)
            with patch("cell.actions.get_provider") as gp:
                prov = gp.return_value
                prov.send_sms.side_effect = ProviderError("twilio down", status=503)
                with self.assertRaises(ProviderError):
                    actions.send_sms("+15553334444", "hi", yes=True, cfg=cfg)
            con = connect(cfg.db_path)
            self.assertEqual(usage_today(con, "sms"), 0)
            con.close()

    def test_successful_send_bumps_sms_quota(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            cfg = _cfg(home)
            msg = Message(
                sid="SMtest",
                direction="outbound",
                from_n="+15551112222",
                to="+15553334444",
                body="hi",
                status="queued",
                created="2026-09-18T00:00:00+00:00",
            )
            with patch("cell.actions.get_provider") as gp:
                gp.return_value.send_sms.return_value = msg
                out = actions.send_sms("+15553334444", "hi", yes=True, cfg=cfg)
            self.assertTrue(out["ok"])
            con = connect(cfg.db_path)
            self.assertEqual(usage_today(con, "sms"), 1)
            con.close()


if __name__ == "__main__":
    unittest.main()
