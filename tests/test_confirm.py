import unittest

from cell.confirm import gsm7_ok, require_yes, segments
from cell.models import NeedConfirm


class TestConfirm(unittest.TestCase):
    def test_segments_short(self):
        self.assertEqual(segments("hello"), 1)

    def test_segments_long_gsm(self):
        self.assertGreaterEqual(segments("a" * 161), 2)

    def test_ucs2(self):
        self.assertFalse(gsm7_ok("hello \u2603"))
        self.assertEqual(segments("x" * 71 + "\u2603"), 2)

    def test_need_yes(self):
        with self.assertRaises(NeedConfirm):
            require_yes(yes=False, auto=False, what="send", note="costs", tty_prompt=False)

    def test_gsm7_escape_septets(self):
        # Extension chars cost 2 septets; 81 braces = 162 > 160 single-SMS cap.
        self.assertTrue(gsm7_ok("{" * 81))
        self.assertEqual(segments("{" * 80), 1)  # 160 septets
        self.assertEqual(segments("{" * 81), 2)  # 162 septets -> multipart
        self.assertTrue(gsm7_ok("price €9"))
        self.assertEqual(segments("€" * 80), 1)
        self.assertEqual(segments("€" * 81), 2)

    def test_ucs2_emoji_units(self):
        # Each emoji is one Python char but two UTF-16 code units.
        emoji = "\U0001F600"  # grinning face
        self.assertFalse(gsm7_ok(emoji))
        self.assertEqual(segments(emoji * 35), 1)  # 70 units
        self.assertEqual(segments(emoji * 36), 2)  # 72 units -> multipart
        # Old len()-based math wrongly reported 70 emoji as a single segment.
        self.assertGreaterEqual(segments(emoji * 70), 2)


if __name__ == "__main__":
    unittest.main()
