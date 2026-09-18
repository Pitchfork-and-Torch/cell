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

    def test_strip_extension_suffix(self):
        # Contact/PBX paste often includes x/ext; digits-only scrub glued them on.
        self.assertEqual(normalize("5125551212x123"), "+15125551212")
        self.assertEqual(normalize("5125551212 ext 99"), "+15125551212")
        self.assertEqual(normalize("512-555-1212x4"), "+15125551212")
        self.assertEqual(normalize("+15125551212;ext=99"), "+15125551212")
        self.assertEqual(normalize("1 (512) 555-1212 x12"), "+15125551212")

    def test_vanity_letters_map_to_keypad(self):
        self.assertEqual(normalize("1-800-FLOWERS"), "+18003569377")
        self.assertEqual(normalize("800-FLOWERS"), "+18003569377")
        self.assertEqual(normalize("+1-800-FLOWERS"), "+18003569377")
        self.assertEqual(normalize("1-800-GOT-JUNK"), "+18004685865")

    def test_tel_sip_uri_scheme_not_vanity_mapped(self):
        # tel:/sip: must be stripped before vanity keypad mapping.
        self.assertEqual(normalize("tel:+15551234567"), "+15551234567")
        self.assertEqual(normalize("TEL:+1-555-123-4567"), "+15551234567")
        self.assertEqual(normalize("sip:+15551234567@sip.example.com"), "+15551234567")
        self.assertEqual(normalize("sips:+15551234567@sip.example.com"), "+15551234567")
        self.assertEqual(normalize("tel:+15551234567;phone-context=nanp"), "+15551234567")
        # Vanity still works after scheme strip.
        self.assertEqual(normalize("tel:1-800-FLOWERS"), "+18003569377")


if __name__ == "__main__":
    unittest.main()
