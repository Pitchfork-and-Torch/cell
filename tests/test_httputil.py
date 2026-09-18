import io
import json
import unittest
from unittest import mock
import urllib.error

from cell.httputil import HttpError, request


class TestHttpUtil(unittest.TestCase):
    def test_twilio_error_includes_hint(self):
        body = json.dumps({"code": 30034, "message": "A2P Campaign", "status": 400}).encode("utf-8")
        err = urllib.error.HTTPError(
            "https://example.invalid/x",
            400,
            "Bad Request",
            hdrs=None,
            fp=io.BytesIO(body),
        )
        with mock.patch("urllib.request.urlopen", side_effect=err):
            with self.assertRaises(HttpError) as cm:
                request("GET", "https://example.invalid/x")
        self.assertEqual(cm.exception.status, 400)
        self.assertEqual(cm.exception.code, 30034)
        self.assertIn("30034", str(cm.exception))
        self.assertIn("10DLC", str(cm.exception))

    def test_telnyx_error_list(self):
        body = json.dumps({"errors": [{"code": "10009", "detail": "unauthorized"}]}).encode("utf-8")
        err = urllib.error.HTTPError(
            "https://example.invalid/x",
            401,
            "Unauthorized",
            hdrs=None,
            fp=io.BytesIO(body),
        )
        with mock.patch("urllib.request.urlopen", side_effect=err):
            with self.assertRaises(HttpError) as cm:
                request("GET", "https://example.invalid/x")
        self.assertEqual(cm.exception.code, "10009")
        self.assertIn("TELNYX_API_KEY", str(cm.exception))

    def test_network_error(self):
        with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("timed out")):
            with self.assertRaises(HttpError) as cm:
                request("GET", "https://example.invalid/x")
        self.assertIn("network error", str(cm.exception))
        self.assertIsNone(cm.exception.code)


if __name__ == "__main__":
    unittest.main()
