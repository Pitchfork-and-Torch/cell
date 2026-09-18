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

    def test_cc_00_prefix(self):
        self.assertEqual(normalize("00447700900123"), "+447700900123")

    def test_too_short(self):
        with self.assertRaises(PhoneError):
            normalize("123")

    def test_letters_only(self):
        with self.assertRaises(PhoneError):
            normalize("not-a-number")



    def test_us_011_intl_prefix(self):
        # US international access code 011, same idea as 00 abroad.
        self.assertEqual(normalize("011441234567890"), "+441234567890")
        self.assertEqual(normalize("011 44 7700 900123"), "+447700900123")

if __name__ == "__main__":
    unittest.main()
