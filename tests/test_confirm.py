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


if __name__ == "__main__":
    unittest.main()
