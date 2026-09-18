import unittest

import harness  # noqa: F401
from cell import actions
from cell.config import load
from harness import CellHomeCase


class TestDoctor(CellHomeCase):
    def test_offline_healthy_twilio_config(self):
        self.write_twilio_config()
        d = actions.doctor(live=False)
        self.assertTrue(d["ok"])
        self.assertTrue(d["offline"])
        names = {c["name"]: c for c in d["checks"]}
        self.assertTrue(names["config_file"]["ok"])
        self.assertTrue(names["secrets_file"]["ok"])
        self.assertTrue(names["sqlite"]["ok"])
        self.assertTrue(names["twilio_sid"]["ok"])
        self.assertTrue(names["twilio_token"]["ok"])
        self.assertTrue(names["from_number"]["ok"])
        self.assertTrue(names["auto_confirm"]["ok"])
        self.assertEqual(names["provider_api"]["detail"], "skipped (offline)")
        self.assertNotIn("owned_numbers", names)

    def test_sid_must_start_with_ac(self):
        self.write_twilio_config(sid="XXnotanaccountsid0000000000000000")
        d = actions.doctor(live=False)
        self.assertFalse(d["ok"])
        names = {c["name"]: c for c in d["checks"]}
        self.assertFalse(names["twilio_sid"]["ok"])
        self.assertIn("should start with AC", names["twilio_sid"]["detail"])

    def test_auto_confirm_fails_doctor(self):
        self.write_twilio_config(auto_confirm=True)
        d = actions.doctor(live=False)
        self.assertFalse(d["ok"])
        names = {c["name"]: c for c in d["checks"]}
        self.assertFalse(names["auto_confirm"]["ok"])

    def test_invalid_from_number(self):
        self.write_twilio_config(from_number="123")
        d = actions.doctor(live=False)
        self.assertFalse(d["ok"])
        names = {c["name"]: c for c in d["checks"]}
        self.assertFalse(names["from_number"]["ok"])

    def test_fake_provider_fails_doctor(self):
        self.enable_fake()
        d = actions.doctor(live=False)
        self.assertFalse(d["ok"])
        names = {c["name"]: c for c in d["checks"]}
        self.assertFalse(names["fake_provider"]["ok"])

    def test_does_not_print_token(self):
        self.write_twilio_config()
        d = actions.doctor(live=False)
        blob = str(d)
        self.assertNotIn("unit-test-only-token-zz", blob)
        masked = load().masked()
        self.assertEqual(masked["twilio_auth_token"], "set")
        self.assertNotEqual(masked["twilio_account_sid"], load().twilio_account_sid)


if __name__ == "__main__":
    unittest.main()
