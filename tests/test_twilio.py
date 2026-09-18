import unittest
from unittest import mock

from cell.config import Config
from cell.providers.twilio import TwilioProvider, _iso_utc, _msg_from_twilio, twilio_signature_ok


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
        self.assertEqual(m.created, "2026-08-15T00:00:00+00:00")

    def test_parse_outbound(self):
        m = _msg_from_twilio({"sid": "SMout", "direction": "outbound-api", "body": "x"})
        self.assertEqual(m.direction, "outbound")
        self.assertEqual(m.created, "")

    def test_iso_utc(self):
        self.assertEqual(_iso_utc("Sat, 12 Sep 2026 10:00:00 -0500"), "2026-09-12T15:00:00+00:00")
        self.assertEqual(_iso_utc(""), "")
        self.assertEqual(_iso_utc("not a date"), "not a date")

    def test_thread_merge_sorts_by_time_not_weekday(self):
        cfg = Config(twilio_account_sid="ACtest", twilio_auth_token="tok", from_number="+15125551111")
        provider = TwilioProvider(cfg)

        def fake_req(_method, _suffix, **kwargs):
            query = kwargs.get("query") or {}
            if "From" in query:
                return {
                    "messages": [
                        {
                            "sid": "SMin",
                            "direction": "inbound",
                            "from": "+15125550000",
                            "to": "+15125551111",
                            "body": "older",
                            "date_created": "Sat, 12 Sep 2026 10:00:00 +0000",
                        }
                    ]
                }
            return {
                "messages": [
                    {
                        "sid": "SMout",
                        "direction": "outbound-api",
                        "from": "+15125551111",
                        "to": "+15125550000",
                        "body": "newer",
                        "date_created": "Fri, 18 Sep 2026 10:00:00 +0000",
                    }
                ]
            }

        with mock.patch.object(provider, "_req", side_effect=fake_req):
            msgs = provider.list_messages(limit=10, with_n="+15125550000")
        # "Sat" > "Fri" as strings; the Sep 18 message must still come first.
        self.assertEqual([m.sid for m in msgs], ["SMout", "SMin"])


    def test_thread_fetches_both_directions_when_from_page_is_full(self):
        """From= returning PageSize==limit must not skip the To= side."""
        cfg = Config(twilio_account_sid="ACtest", twilio_auth_token="tok", from_number="+15125551111")
        provider = TwilioProvider(cfg)
        calls = []

        def fake_req(_method, _suffix, **kwargs):
            query = kwargs.get("query") or {}
            calls.append(dict(query))
            if "From" in query:
                n = query["PageSize"]
                return {
                    "messages": [
                        {
                            "sid": f"SMin{i}",
                            "direction": "inbound",
                            "from": "+15125550000",
                            "to": "+15125551111",
                            "body": f"in{i}",
                            "date_created": f"Thu, {10 + i} Sep 2026 10:00:00 +0000",
                        }
                        for i in range(n)
                    ]
                }
            if "To" in query:
                return {
                    "messages": [
                        {
                            "sid": "SMout1",
                            "direction": "outbound-api",
                            "from": "+15125551111",
                            "to": "+15125550000",
                            "body": "out1",
                            "date_created": "Fri, 18 Sep 2026 12:00:00 +0000",
                        }
                    ]
                }
            return {"messages": []}

        with mock.patch.object(provider, "_req", side_effect=fake_req):
            msgs = provider.list_messages(limit=5, with_n="+15125550000")
        self.assertEqual(len(calls), 2)
        self.assertIn("From", calls[0])
        self.assertIn("To", calls[1])
        self.assertEqual(msgs[0].sid, "SMout1")
        self.assertIn("SMout1", [m.sid for m in msgs])

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
