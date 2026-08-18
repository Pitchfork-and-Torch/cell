import unittest

from cell.providers.twilio import _msg_from_twilio, twilio_signature_ok


class TestTwilioHelpers(unittest.TestCase):
    def test_parse_inbound(self):
        m = _msg_from_twilio(
            {
                "sid": "SMabc",
                "direction": "inbound",
                "from": "+15125550000",
                "to": "+15125551111",
                "body": "hi",
                "status": "received",
                "date_created": "Fri, 15 Aug 2026 00:00:00 +0000",
            }
        )
        self.assertEqual(m.direction, "inbound")
        self.assertEqual(m.from_n, "+15125550000")
        self.assertEqual(m.body, "hi")

    def test_parse_outbound(self):
        m = _msg_from_twilio({"sid": "SMout", "direction": "outbound-api", "body": "x"})
        self.assertEqual(m.direction, "outbound")

    def test_signature_roundtrip(self):
        token = "secret-token"
        url = "https://example.com/sms"
        params = {"From": "+15125550000", "Body": "hi", "To": "+15125551111"}
        import base64
        import hashlib
        import hmac

        s = url + "".join(k + params[k] for k in sorted(params))
        header = base64.b64encode(hmac.new(token.encode(), s.encode(), hashlib.sha1).digest()).decode()
        self.assertTrue(twilio_signature_ok(token, url, params, header))
        self.assertFalse(twilio_signature_ok(token, url, params, "nope"))


if __name__ == "__main__":
    unittest.main()
