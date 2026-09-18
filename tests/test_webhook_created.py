import unittest
from datetime import datetime, timezone
from unittest import mock

from cell.webhook import _from_telnyx_json, _from_twilio_form


class TestWebhookCreated(unittest.TestCase):
    def test_twilio_form_stamps_iso_utc(self):
        fixed = datetime(2026, 9, 18, 1, 30, 0, tzinfo=timezone.utc)
        with mock.patch("cell.webhook.datetime") as dt:
            dt.now.return_value = fixed
            dt.side_effect = lambda *a, **k: datetime(*a, **k)
            msg = _from_twilio_form(
                {
                    "MessageSid": "SMin1",
                    "From": "+15125550000",
                    "To": "+15125551111",
                    "Body": "hi",
                    "SmsStatus": "received",
                }
            )
        self.assertIsNotNone(msg)
        self.assertEqual(msg.created, "2026-09-18T01:30:00+00:00")
        self.assertEqual(msg.sid, "SMin1")

    def test_telnyx_json_stamps_iso_utc(self):
        fixed = datetime(2026, 9, 18, 1, 31, 0, tzinfo=timezone.utc)
        payload = b'{"data":{"payload":{"id":"msg-1","from":{"phone_number":"+15125550000"},"to":[{"phone_number":"+15125551111"}],"text":"yo"}}}'
        with mock.patch("cell.webhook.datetime") as dt:
            dt.now.return_value = fixed
            msg = _from_telnyx_json(payload)
        self.assertIsNotNone(msg)
        self.assertEqual(msg.created, "2026-09-18T01:31:00+00:00")
        self.assertEqual(msg.body, "yo")


if __name__ == "__main__":
    unittest.main()
