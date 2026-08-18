import json
import unittest
from io import StringIO
from unittest import mock

from cell.cli import main
from cell.mcp_server import handle


class TestCliHelp(unittest.TestCase):
    def test_help(self):
        buf = StringIO()
        with mock.patch("sys.stdout", buf):
            code = main(["--help"])
        self.assertEqual(code, 0)
        self.assertIn("send", buf.getvalue())

    def test_send_requires_yes_json(self):
        buf = StringIO()
        err = StringIO()
        with mock.patch("sys.stdout", buf), mock.patch("sys.stderr", err), mock.patch("sys.stdin.isatty", return_value=False):
            code = main(["--json", "send", "+15125551212", "hello"])
        self.assertEqual(code, 2)
        payload = json.loads(buf.getvalue())
        self.assertFalse(payload["ok"])
        self.assertIn("Needs --yes", payload["error"])


class TestMcp(unittest.TestCase):
    def test_initialize(self):
        reply = handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        self.assertEqual(reply["result"]["serverInfo"]["name"], "cell")

    def test_tools_list(self):
        reply = handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        names = {t["name"] for t in reply["result"]["tools"]}
        self.assertTrue({"cell_status", "cell_send", "cell_inbox", "cell_call"} <= names)


if __name__ == "__main__":
    unittest.main()
