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


    def test_init_fills_empty_from_number(self):
        from cell.config import write_init

        self.write_twilio_config(from_number="")
        # Empty from_number in file; env/arg should fill it without rewriting other keys.
        write_init(from_number="+15125550999")
        cfg_text = (self.home / "config.toml").read_text(encoding="utf-8")
        self.assertIn("from_number = \"+15125550999\"", cfg_text)
        self.assertIn("daily_sms_limit", cfg_text)

    def test_init_explicit_from_number_replaces(self):
        from cell.config import write_init

        self.write_twilio_config(from_number="+15125550100")
        write_init(from_number="+15125550999")
        cfg_text = (self.home / "config.toml").read_text(encoding="utf-8")
        self.assertIn("from_number = \"+15125550999\"", cfg_text)
        self.assertNotIn("from_number = \"+15125550100\"", cfg_text)


if __name__ == "__main__":
    unittest.main()
