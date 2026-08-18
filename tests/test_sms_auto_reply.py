import importlib.util
import unittest
from pathlib import Path

_PATH = Path(__file__).resolve().parents[1] / "scripts" / "sms_auto_reply.py"
_SPEC = importlib.util.spec_from_file_location("sms_auto_reply", _PATH)
mod = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(mod)


class TestAllowlist(unittest.TestCase):
    def test_operator_matches(self):
        self.assertTrue(mod.allowed("+15550001111", "5550001111"))
        self.assertTrue(mod.allowed("15550001111", "+1 (555) 000-1111"))

    def test_stranger_blocked(self):
        self.assertFalse(mod.allowed("+15551231234", "+15550001111"))
        self.assertFalse(mod.allowed("", "+15550001111"))

    def test_decide_skips(self):
        self.assertEqual(
            mod.decide(
                from_n="+15550001111",
                sid="SMold",
                body="hi",
                allow="+15550001111",
                seen={"SMold"},
                replies_count=0,
                daily=20,
            ),
            "seen",
        )
        self.assertEqual(
            mod.decide(
                from_n="+15551239999",
                sid="SMnew",
                body="hi",
                allow="+15550001111",
                seen=set(),
                replies_count=0,
                daily=20,
            ),
            "not-allowlist",
        )
        self.assertEqual(
            mod.decide(
                from_n="+15550001111",
                sid="SMnew",
                body="hi",
                allow="+15550001111",
                seen=set(),
                replies_count=20,
                daily=20,
            ),
            "daily-cap",
        )
        self.assertEqual(
            mod.decide(
                from_n="+15550001111",
                sid="SMnew",
                body="  ",
                allow="+15550001111",
                seen=set(),
                replies_count=0,
                daily=20,
            ),
            "empty-body",
        )
        self.assertEqual(
            mod.decide(
                from_n="+15550001111",
                sid="SMnew",
                body="hello",
                allow="+15550001111",
                seen=set(),
                replies_count=0,
                daily=20,
            ),
            "",
        )

    def test_ascii_sms(self):
        self.assertEqual(mod.ascii_sms("Hello \u2014 world"), "Hello - world")
        self.assertNotIn("\u2014", mod.ascii_sms("em\u2014dash"))
        self.assertTrue(len(mod.ascii_sms("x" * 400)) <= 280)

    def test_short_sender(self):
        self.assertTrue(mod.is_short_sender("22395"))
        self.assertTrue(mod.is_short_sender("87654"))
        self.assertTrue(mod.is_short_sender("VERIFY"))
        self.assertTrue(mod.is_short_sender("AMZN"))
        self.assertFalse(mod.is_short_sender("+15551231234"))
        self.assertFalse(mod.is_short_sender("+15550001111"))
        self.assertFalse(mod.is_short_sender(""))

    def test_extract_otp(self):
        self.assertEqual(mod.extract_otp("Your code is 847291"), "847291")
        self.assertEqual(mod.extract_otp("G-123456 is your Google verification code"), "123456")
        self.assertEqual(mod.extract_otp("847291"), "847291")
        self.assertEqual(mod.extract_otp("hello there"), "")

    def test_classify_forward_short_code(self):
        action, reason = mod.classify(
            from_n="22395",
            sid="SMfa",
            body="Your verification code is 112233",
            allow="+15550001111",
            seen=set(),
            replies_count=0,
            daily=20,
            forwards_count=0,
            forward_daily=40,
        )
        self.assertEqual(action, "forward")
        self.assertEqual(reason, "")
        self.assertIn("112233", mod.format_forward("22395", "Your verification code is 112233"))

    def test_classify_does_not_forward_long_code_stranger(self):
        action, reason = mod.classify(
            from_n="+15551239999",
            sid="SMstr",
            body="Your code is 999111",
            allow="+15550001111",
            seen=set(),
            replies_count=0,
            daily=20,
            forwards_count=0,
            forward_daily=40,
        )
        self.assertEqual(action, "skip")
        self.assertEqual(reason, "not-allowlist")

    def test_classify_forward_cap(self):
        action, reason = mod.classify(
            from_n="22395",
            sid="SMcap",
            body="code 111222",
            allow="+15550001111",
            seen=set(),
            replies_count=0,
            daily=20,
            forwards_count=40,
            forward_daily=40,
        )
        self.assertEqual(action, "skip")
        self.assertEqual(reason, "forward-cap")


if __name__ == "__main__":
    unittest.main()
