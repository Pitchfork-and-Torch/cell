import json
import os
import subprocess
import sys
import unittest
from io import StringIO
from pathlib import Path
from unittest import mock

import harness  # noqa: F401
from cell.cli import main
from cell.mcp_server import handle
from cell.providers.fake import FakeProvider
from harness import TO_N, TOKEN, CellHomeCase

ROOT = Path(__file__).resolve().parents[1]


class TestCliHelp(unittest.TestCase):
    def test_help(self):
        buf = StringIO()
        with mock.patch("sys.stdout", buf):
            code = main(["--help"])
        self.assertEqual(code, 0)
        out = buf.getvalue()
        self.assertIn("send", out)
        self.assertIn("dry-run", out)

    def test_send_help_lists_gates(self):
        buf = StringIO()
        with mock.patch("sys.stdout", buf):
            code = main(["send", "--help"])
        self.assertEqual(code, 0)
        out = buf.getvalue()
        self.assertIn("--yes", out)
        self.assertIn("--dry-run", out)


class TestCliIsolation(CellHomeCase):
    def _run(self, argv):
        buf = StringIO()
        err = StringIO()
        with mock.patch("sys.stdout", buf), mock.patch("sys.stderr", err), mock.patch(
            "sys.stdin.isatty", return_value=False
        ):
            code = main(argv)
        return code, buf.getvalue(), err.getvalue()

    def test_send_requires_yes_json(self):
        self.write_twilio_config()
        code, out, _err = self._run(["--json", "send", TO_N, "hello"])
        self.assertEqual(code, 2)
        payload = json.loads(out)
        self.assertFalse(payload["ok"])
        self.assertIn("Needs --yes", payload["error"])

    def test_send_json_flag_after_subcommand(self):
        self.write_twilio_config()
        code, out, _err = self._run(["send", TO_N, "hello", "--dry-run", "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["dry_run"])
        self.assertEqual(payload["would"], "send_sms")
        self.assertEqual(payload["to"], TO_N)

    def test_send_dry_run_does_not_need_yes(self):
        self.write_twilio_config()
        code, out, _err = self._run(["--json", "send", TO_N, "hello", "--dry-run"])
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertTrue(payload["dry_run"])
        self.assertFalse(payload["would_block_rate"])
        self.assertIn("segment", payload["cost"])

    def test_send_empty_body(self):
        self.write_twilio_config()
        code, out, _err = self._run(["--json", "send", TO_N, "   ", "--dry-run"])
        self.assertEqual(code, 1)
        payload = json.loads(out)
        self.assertIn("empty SMS body", payload["error"])

    def test_send_bad_number(self):
        self.write_twilio_config()
        code, out, _err = self._run(["--json", "send", "12", "hello", "--dry-run"])
        self.assertEqual(code, 1)
        payload = json.loads(out)
        self.assertFalse(payload["ok"])

    def test_doctor_offline_ok_and_masks_token(self):
        self.write_twilio_config()
        code, out, _err = self._run(["--json", "doctor", "--offline"])
        self.assertEqual(code, 0)
        self.assertNotIn(TOKEN, out)
        payload = json.loads(out)
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["offline"])
        names = {c["name"]: c for c in payload["checks"]}
        self.assertTrue(names["twilio_sid"]["ok"])
        self.assertTrue(names["twilio_token"]["ok"])
        self.assertEqual(names["provider_api"]["detail"], "skipped (offline)")

    def test_doctor_offline_via_dry_run_flag(self):
        self.write_twilio_config()
        code, out, _err = self._run(["doctor", "--dry-run", "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertTrue(payload["offline"])

    def test_doctor_missing_creds(self):
        code, out, _err = self._run(["--json", "doctor", "--offline"])
        self.assertEqual(code, 1)
        payload = json.loads(out)
        self.assertFalse(payload["ok"])
        names = {c["name"]: c for c in payload["checks"]}
        self.assertFalse(names["twilio_sid"]["ok"])
        self.assertFalse(names["from_number"]["ok"])

    def test_inbox_local_empty(self):
        self.write_twilio_config()
        code, out, _err = self._run(["--json", "inbox", "--local"])
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertEqual(payload["source"], "local")
        self.assertEqual(payload["messages"], [])

    def test_watch_once_local(self):
        self.write_twilio_config()
        code, out, _err = self._run(["--json", "watch", "--once", "--local"])
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertEqual(payload["source"], "local")

    def test_fake_send_yes_then_local_inbox(self):
        self.enable_fake()
        code, out, _err = self._run(["--json", "send", TO_N, "ping-from-test", "--yes"])
        self.assertEqual(code, 0)
        sent = json.loads(out)
        self.assertTrue(sent["ok"])
        self.assertFalse(sent["dry_run"])
        self.assertTrue(sent["message"]["sid"].startswith("SM"))
        self.assertEqual(len(FakeProvider.mailbox), 1)

        code, out, _err = self._run(["--json", "inbox", "--local"])
        self.assertEqual(code, 0)
        box = json.loads(out)
        self.assertEqual(box["source"], "local")
        self.assertEqual(len(box["messages"]), 1)
        self.assertEqual(box["messages"][0]["body"], "ping-from-test")
        self.assertEqual(box["messages"][0]["to"], TO_N)

    def test_webhook_pin_requires_yes(self):
        self.write_twilio_config()
        code, out, _err = self._run(["--json", "numbers", "webhook", "https://example.com/sms"])
        self.assertEqual(code, 2)
        payload = json.loads(out)
        self.assertIn("Needs --yes", payload["error"])

    def test_webhook_pin_dry_run(self):
        self.write_twilio_config()
        code, out, _err = self._run(
            ["--json", "numbers", "webhook", "https://example.com/sms", "--dry-run"]
        )
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertTrue(payload["dry_run"])
        self.assertEqual(payload["would"], "set_webhook")
        self.assertIn("HavenID", payload["warning"])

    def test_buy_dry_run(self):
        self.write_twilio_config()
        code, out, _err = self._run(["--json", "numbers", "buy", "+15125550111", "--dry-run"])
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertTrue(payload["dry_run"])
        self.assertEqual(payload["number"], "+15125550111")

    def test_call_dry_run(self):
        self.write_twilio_config()
        code, out, _err = self._run(["--json", "call", TO_N, "--say", "hi", "--dry-run"])
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertTrue(payload["dry_run"])
        self.assertEqual(payload["would"], "place_call")

    def test_limit_must_be_positive(self):
        self.write_twilio_config()
        code, _out, err = self._run(["inbox", "--limit", "0"])
        self.assertEqual(code, 2)
        self.assertTrue("must be >= 1" in err or "must be >= 1" in _out)

    def test_scripts_entry_help(self):
        env = os.environ.copy()
        env["CELL_HOME"] = str(self.home)
        env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "cell.py"), "--help"],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(ROOT),
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("send", proc.stdout)


class TestMcp(unittest.TestCase):
    def test_initialize(self):
        reply = handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        self.assertEqual(reply["result"]["serverInfo"]["name"], "cell")

    def test_tools_list(self):
        reply = handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        names = {t["name"] for t in reply["result"]["tools"]}
        self.assertTrue({"cell_status", "cell_send", "cell_inbox", "cell_call", "cell_doctor"} <= names)
        send = next(t for t in reply["result"]["tools"] if t["name"] == "cell_send")
        self.assertIn("dry_run", send["inputSchema"]["properties"])


class TestMcpActions(CellHomeCase):
    def test_send_dry_run_tool(self):
        self.write_twilio_config()
        reply = handle(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "cell_send",
                    "arguments": {"to": TO_N, "body": "preview", "dry_run": True},
                },
            }
        )
        payload = json.loads(reply["result"]["content"][0]["text"])
        self.assertTrue(payload["dry_run"])
        self.assertFalse(reply["result"]["isError"])

    def test_send_needs_confirm(self):
        self.write_twilio_config()
        reply = handle(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {"name": "cell_send", "arguments": {"to": TO_N, "body": "nope"}},
            }
        )
        self.assertTrue(reply["result"]["isError"])
        self.assertIn("needs confirm", reply["result"]["content"][0]["text"].lower())

    def test_doctor_offline_tool(self):
        self.write_twilio_config()
        reply = handle(
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {"name": "cell_doctor", "arguments": {"offline": True}},
            }
        )
        payload = json.loads(reply["result"]["content"][0]["text"])
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["offline"])

    def test_inbox_local_tool(self):
        self.write_twilio_config()
        reply = handle(
            {
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {"name": "cell_inbox", "arguments": {"local": True}},
            }
        )
        payload = json.loads(reply["result"]["content"][0]["text"])
        self.assertEqual(payload["source"], "local")


if __name__ == "__main__":
    unittest.main()
