import unittest

import harness  # noqa: F401
from cell.config import Config, _apply_toml, load
from harness import CellHomeCase


class TestZeroLimits(CellHomeCase):
    def test_apply_toml_honors_zero_daily_limits(self):
        cfg = Config()
        _apply_toml(
            cfg,
            {
                "daily_sms_limit": 0,
                "daily_call_limit": 0,
                "webhook_port": 0,
            },
        )
        self.assertEqual(cfg.daily_sms_limit, 0)
        self.assertEqual(cfg.daily_call_limit, 0)
        self.assertEqual(cfg.webhook_port, 0)

    def test_load_honors_zero_from_config_toml(self):
        (self.home / "config.toml").write_text(
            (
                'provider = "twilio"\n'
                'from_number = "+15125550100"\n'
                "daily_sms_limit = 0\n"
                "daily_call_limit = 0\n"
                "auto_confirm = false\n"
                "webhook_port = 0\n"
                'public_url = ""\n'
                'country = "US"\n'
            ),
            encoding="utf-8",
        )
        (self.home / "secrets.toml").write_text(
            'twilio_account_sid = "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"\n'
            'twilio_auth_token = "tok"\n'
            'telnyx_api_key = ""\n',
            encoding="utf-8",
        )
        cfg = load()
        self.assertEqual(cfg.daily_sms_limit, 0)
        self.assertEqual(cfg.daily_call_limit, 0)
        self.assertEqual(cfg.webhook_port, 0)

    def test_positive_limits_still_apply(self):
        cfg = Config()
        _apply_toml(cfg, {"daily_sms_limit": 7, "daily_call_limit": 3, "webhook_port": 9001})
        self.assertEqual(cfg.daily_sms_limit, 7)
        self.assertEqual(cfg.daily_call_limit, 3)
        self.assertEqual(cfg.webhook_port, 9001)


if __name__ == "__main__":
    unittest.main()
