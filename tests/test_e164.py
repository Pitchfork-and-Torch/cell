import unittest

from cell.e164 import PhoneError, normalize


class TestE164(unittest.TestCase):
    def test_us_ten(self):
        self.assertEqual(normalize("5125551212"), "+15125551212")

    def test_already_plus(self):
        self.assertEqual(normalize("+44 7700 900123"), "+447700900123")

    def test_one_prefix(self):
        self.assertEqual(normalize("1 (512) 555-1212"), "+15125551212")

    def test_empty(self):
        with self.assertRaises(PhoneError):
            normalize("")


if __name__ == "__main__":
    unittest.main()
