import unittest
from unittest import mock

import harness  # noqa: F401
from cell import actions
from cell.config import load
from cell.models import NeedConfirm, ProviderError
from cell.providers import get_provider
from cell.providers.fake import FakeProvider
from cell.store import connect, usage_today
from harness import FROM_N, TO_N, CellHomeCase


class TestSendRead(CellHomeCase):
    def test_dry_run_does_not_bump_usage_or_mailbox(self):
        self.write_twilio_config()
        cfg = load()
        out = actions.send_sms(TO_N, "hello", dry_run=True, cfg=cfg)
        self.assertTrue(out["dry_run"])
        self.assertEqual(out["from_n"], FROM_N)
        self.assertEqual(out["to"], TO_N)
        self.assertEqual(out["segments"], 1)
        self.assertEqual(out["usage_today"]["sms"], 0)
        self.assertEqual(FakeProvider.mailbox, [])
        con = connect(cfg.db_path)
        self.assertEqual(usage_today(con, "sms"), 0)
        con.close()

    def test_fake_send_then_inbox_local(self):
        self.enable_fake()
        cfg = load()
        sent = actions.send_sms(TO_N, "alpha", yes=True, cfg=cfg)
        self.assertTrue(sent["message"]["sid"].startswith("SM"))
        box = actions.inbox(local=True, cfg=cfg)
        self.assertEqual(box["source"], "local")
        self.assertEqual(len(box["messages"]), 1)
        self.assertEqual(box["messages"][0]["body"], "alpha")
        thread = actions.thread(TO_N, local=True, cfg=cfg)
        self.assertEqual(len(thread["messages"]), 1)

    def test_rate_limit_bumps_only_after_success(self):
        self.enable_fake(sms_limit=1)
        cfg = load()
        actions.send_sms(TO_N, "one", yes=True, cfg=cfg)
        with self.assertRaises(ProviderError) as cm:
            actions.send_sms(TO_N, "two", yes=True, cfg=cfg)
        self.assertIn("daily sms limit", str(cm.exception))
        preview = actions.send_sms(TO_N, "two", dry_run=True, cfg=cfg)
        self.assertTrue(preview["would_block_rate"])
        self.assertFalse(preview["would_succeed"])
        forced = actions.send_sms(TO_N, "two", yes=True, force=True, cfg=cfg)
        self.assertTrue(forced["ok"])
        con = connect(cfg.db_path)
        self.assertEqual(usage_today(con, "sms"), 2)
        con.close()

    def test_send_failed_provider_does_not_count(self):
        self.enable_fake()
        cfg = load()
        with mock.patch.object(FakeProvider, "send_sms", side_effect=ProviderError("simulated carrier fail")):
            with self.assertRaises(ProviderError):
                actions.send_sms(TO_N, "nope", yes=True, cfg=cfg)
        con = connect(cfg.db_path)
        self.assertEqual(usage_today(con, "sms"), 0)
        con.close()

    def test_fake_requires_flag(self):
        import os

        self.enable_fake()
        os.environ.pop("CELL_FAKE", None)
        cfg = load()
        with self.assertRaises(ProviderError) as cm:
            get_provider(cfg)
        self.assertIn("CELL_FAKE=1", str(cm.exception))

    def test_missing_from_number(self):
        self.write_twilio_config(from_number="")
        cfg = load()
        cfg.from_number = ""
        with self.assertRaises(ProviderError) as cm:
            actions.send_sms(TO_N, "x", dry_run=True, cfg=cfg)
        self.assertIn("from_number not set", str(cm.exception))

    def test_need_yes_without_dry_run(self):
        self.write_twilio_config()
        cfg = load()
        with self.assertRaises(NeedConfirm):
            actions.send_sms(TO_N, "x", yes=False, cfg=cfg)

    def test_call_dry_run(self):
        self.write_twilio_config()
        out = actions.call(TO_N, say="hi", dry_run=True)
        self.assertEqual(out["would"], "place_call")
        self.assertEqual(FakeProvider.calls, [])

    def test_buy_dry_run(self):
        out = actions.buy_number("+15125550111", dry_run=True)
        self.assertEqual(out["would"], "buy_number")
        self.assertEqual(FakeProvider.bought, [])

    def test_inbox_falls_back_local_on_provider_error(self):
        self.write_twilio_config()
        cfg = load()

        class Boom:
            def list_messages(self, **_kwargs):
                raise ProviderError("simulated inbox fail")

        with mock.patch("cell.actions.get_provider", return_value=Boom()):
            box = actions.inbox(cfg=cfg)
        self.assertEqual(box["source"], "local")
        self.assertIn("simulated inbox fail", box["provider_error"] or "")

    def test_clamp_limit(self):
        self.assertEqual(actions._clamp_limit(0), 1)
        self.assertEqual(actions._clamp_limit(500), 100)
        self.assertEqual(actions._clamp_limit("nope"), 20)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
