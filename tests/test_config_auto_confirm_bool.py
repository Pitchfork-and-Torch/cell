import os
import unittest

import harness  # noqa: F401
from cell.config import Config, _apply_environ, _apply_toml, _as_bool, load
from harness import CellHomeCase


class TestAutoConfirmBool(CellHomeCase):
    def test_string_false_stays_off(self):
        cfg = Config()
        _apply_toml(cfg, {"auto_confirm": "false"})
        self.assertFalse(cfg.auto_confirm)
        cfg = Config()
        _apply_toml(cfg, {"auto_confirm": "0"})
        self.assertFalse(cfg.auto_confirm)
        cfg = Config()
        _apply_toml(cfg, {"auto_confirm": "no"})
        self.assertFalse(cfg.auto_confirm)

    def test_string_true_turns_on(self):
        cfg = Config()
        _apply_toml(cfg, {"auto_confirm": "true"})
        self.assertTrue(cfg.auto_confirm)
        cfg = Config()
        _apply_toml(cfg, {"auto_confirm": "1"})
        self.assertTrue(cfg.auto_confirm)

    def test_native_bool_and_int(self):
        self.assertFalse(_as_bool(False))
        self.assertTrue(_as_bool(True))
        self.assertFalse(_as_bool(0))
        self.assertTrue(_as_bool(1))

    def test_env_can_disable(self):
        self.write_twilio_config(auto_confirm=True)
        os.environ["CELL_AUTO_CONFIRM"] = "false"
        cfg = load()
        self.assertFalse(cfg.auto_confirm)

    def test_env_zero_disables(self):
        cfg = Config(auto_confirm=True)
        os.environ["CELL_AUTO_CONFIRM"] = "0"
        _apply_environ(cfg)
        self.assertFalse(cfg.auto_confirm)

    def test_env_still_enables(self):
        self.write_twilio_config()
        os.environ["CELL_AUTO_CONFIRM"] = "yes"
        cfg = load()
        self.assertTrue(cfg.auto_confirm)

    def test_toml_false_literal_still_off(self):
        (self.home / "config.toml").write_text(
            (
                'provider = "twilio"\n'
                'from_number = "+15125550100"\n'
                "daily_sms_limit = 20\n"
                "daily_call_limit = 5\n"
                "auto_confirm = false\n"
                "webhook_port = 8788\n"
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
        self.assertFalse(cfg.auto_confirm)


if __name__ == "__main__":
    unittest.main()
