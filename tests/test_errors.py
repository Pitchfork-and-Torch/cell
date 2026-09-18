import unittest

from cell.errors import TWILIO_HINTS, annotate, extract_code, hint_for
from cell.models import ProviderError


class TestErrors(unittest.TestCase):
    def test_common_twilio_codes(self):
        self.assertIn("verified", hint_for(21211) or "")
        self.assertIn("10DLC", hint_for(30034) or "")
        self.assertIn("Toll-free", hint_for(30032) or "")
        self.assertIn("Auth failed", hint_for(20003) or "")
        self.assertIn("10DLC", hint_for("30034") or "")

    def test_all_hints_are_ascii(self):
        for code, text in TWILIO_HINTS.items():
            self.assertTrue(text, msg=code)
            self.assertEqual(text, text.encode("ascii", "strict").decode("ascii"))

    def test_extract_code_twilio_shape(self):
        self.assertEqual(extract_code({"code": 30034, "message": "A2P"}), 30034)

    def test_extract_code_telnyx_shape(self):
        self.assertEqual(
            extract_code({"errors": [{"code": "10009", "detail": "unauthorized"}]}),
            "10009",
        )

    def test_annotate_appends_once(self):
        msg = annotate("HTTP 400 (30034): A2P", 30034)
        self.assertIn("Hint:", msg)
        self.assertEqual(annotate(msg, 30034), msg)

    def test_unknown_code(self):
        self.assertIsNone(hint_for(99999))
        self.assertEqual(annotate("plain", None), "plain")

    def test_provider_error_to_dict(self):
        err = ProviderError("nope", code=21608, status=400, hint=hint_for(21608))
        d = err.to_dict()
        self.assertEqual(d["code"], 21608)
        self.assertIn("trial", (d.get("hint") or "").lower())


if __name__ == "__main__":
    unittest.main()
