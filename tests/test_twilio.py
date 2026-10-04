import base64
import json
import unittest
from pathlib import Path

from cell.config import Config
from cell.ed25519 import public_key, sign, verify
from cell.providers.twilio import _msg_from_twilio, twilio_signature_ok
from cell.store import connect
from cell.webhook import _twilio_ok, ingest_sms


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


# RFC 8032 test 1 seed. Not a Telnyx or Twilio credential.
_RFC_SEED = bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")
_FAKE_TWILIO = "fake-twilio-auth-token"


class TestWebhookFailClosed(unittest.TestCase):
    def setUp(self) -> None:
        import tempfile

        self._tmp = tempfile.TemporaryDirectory(prefix="cell-webhook-")
        self.home = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _cfg(self, **kwargs: str) -> Config:
        return Config(home=self.home, **kwargs)

    def test_rfc8032_vector(self):
        pk = public_key(_RFC_SEED)
        self.assertEqual(pk.hex(), "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a")
        sig = sign(_RFC_SEED, b"")
        self.assertEqual(
            sig.hex(),
            "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e06522490155"
            "5fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b",
        )
        self.assertTrue(verify(pk, sig, b""))
        self.assertFalse(verify(pk, sig, b"x"))

    def test_twilio_empty_token_is_rejected(self):
        cfg = self._cfg(twilio_auth_token="", public_url="https://example.test")
        form = {"MessageSid": "SMfake", "From": "+15125550100", "To": "+15125550199", "Body": "hi"}
        self.assertFalse(_twilio_ok(cfg, {"X-Twilio-Signature": "anything"}, "/sms", form))
        status, error, msg = ingest_sms(cfg, {}, b"Body=hi", "application/x-www-form-urlencoded", "/sms")
        self.assertEqual(status, 403)
        self.assertEqual(error, "bad twilio signature")
        self.assertIsNone(msg)
        self.assertFalse(self.home.joinpath("state.sqlite").exists())

    def test_telnyx_json_requires_signature(self):
        body = json.dumps(
            {"data": {"payload": {"id": "msg_fake", "from": {"phone_number": "+15125550100"}, "to": [{"phone_number": "+15125550199"}], "text": "hi"}}}
        ).encode()
        api_only = ingest_sms(
            self._cfg(telnyx_api_key="KEY0187example"),
            {"Content-Type": "application/json"},
            body,
            "application/json",
            "/sms",
        )
        self.assertEqual(api_only[0], 403)
        self.assertEqual(api_only[1], "telnyx not configured")
        self.assertFalse((self.home / "state.sqlite").exists())

        pk = base64.b64encode(public_key(_RFC_SEED)).decode("ascii")
        cfg = self._cfg(telnyx_api_key="KEY0187example", telnyx_public_key=pk)
        unsigned = ingest_sms(cfg, {}, body, "application/json", "/sms", now=1700000000)
        self.assertEqual(unsigned[0], 403)
        self.assertEqual(unsigned[1], "bad telnyx signature")

        bad = ingest_sms(
            cfg,
            {"telnyx-signature-ed25519": base64.b64encode(b"\x00" * 64).decode(), "telnyx-timestamp": "1700000000"},
            body,
            "application/json",
            "/sms",
            now=1700000000,
        )
        self.assertEqual(bad[0], 403)
        self.assertEqual(bad[1], "bad telnyx signature")
        self.assertFalse((self.home / "state.sqlite").exists())

        stamp = "1700000000"
        sig = base64.b64encode(sign(_RFC_SEED, stamp.encode() + b"|" + body)).decode("ascii")
        headers = {"telnyx-signature-ed25519": sig, "telnyx-timestamp": stamp}
        stale = ingest_sms(cfg, headers, body, "application/json", "/sms", now=1700000000 + 301)
        self.assertEqual(stale[0], 403)
        self.assertEqual(stale[1], "stale telnyx timestamp")
        self.assertFalse((self.home / "state.sqlite").exists())

        # API key must not be accepted as a fallback public key.
        swapped = self._cfg(telnyx_api_key=pk, telnyx_public_key=base64.b64encode(b"\x02" * 32).decode())
        fallback = ingest_sms(swapped, headers, body, "application/json", "/sms", now=1700000000)
        self.assertEqual(fallback[0], 403)
        self.assertEqual(fallback[1], "bad telnyx signature")

        ok = ingest_sms(
            cfg,
            headers,
            body,
            "application/json",
            "/sms",
            now=1700000000,
        )
        self.assertEqual(ok[0], 200)
        self.assertIsNotNone(ok[2])
        con = connect(self.home / "state.sqlite")
        try:
            row = con.execute("select sid, body from messages").fetchone()
        finally:
            con.close()
        self.assertEqual(row["sid"], "msg_fake")
        self.assertEqual(row["body"], "hi")

    def test_signed_twilio_form_is_stored(self):
        cfg = self._cfg(twilio_auth_token=_FAKE_TWILIO, public_url="https://example.test")
        form = {"MessageSid": "SMfake", "From": "+15125550100", "To": "+15125550199", "Body": "hi"}
        raw = b"MessageSid=SMfake&From=%2B15125550100&To=%2B15125550199&Body=hi"
        import hashlib
        import hmac

        url = "https://example.test/sms"
        material = url + "".join(k + form[k] for k in sorted(form))
        header = base64.b64encode(hmac.new(_FAKE_TWILIO.encode(), material.encode(), hashlib.sha1).digest()).decode()
        status, _error, msg = ingest_sms(cfg, {"X-Twilio-Signature": header}, raw, "application/x-www-form-urlencoded", "/sms")
        self.assertEqual(status, 200)
        assert msg is not None
        self.assertEqual(msg.sid, "SMfake")


if __name__ == "__main__":
    unittest.main()
