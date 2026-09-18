import os
import unittest

import harness  # noqa: F401
from cell.config import load
from harness import TOKEN, CellHomeCase


class TestConfig(CellHomeCase):
    def test_env_wins_from_number(self):
        self.write_twilio_config(from_number="+15125550100")
        os.environ["CELL_FROM"] = "+15125550111"
        cfg = load()
        self.assertEqual(cfg.from_number, "+15125550111")
        self.assertEqual(cfg.masked()["twilio_auth_token"], "set")
        self.assertNotIn(TOKEN, str(cfg.masked()))

    def test_create_false_missing_home(self):
        missing = self.home / "nope"
        os.environ["CELL_HOME"] = str(missing)
        cfg = load(create=False)
        self.assertFalse(cfg.config_path.is_file())
        self.assertEqual(cfg.provider, "twilio")

    def test_sid_mask(self):
        self.write_twilio_config()
        cfg = load()
        masked = cfg.masked()["twilio_account_sid"]
        self.assertIsNotNone(masked)
        self.assertIn("...", masked)
        self.assertNotEqual(masked, cfg.twilio_account_sid)

    def test_auto_confirm_env(self):
        self.write_twilio_config()
        os.environ["CELL_AUTO_CONFIRM"] = "1"
        cfg = load()
        self.assertTrue(cfg.auto_confirm)


if __name__ == "__main__":
    unittest.main()
