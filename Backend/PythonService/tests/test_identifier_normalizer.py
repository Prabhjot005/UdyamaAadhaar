import unittest

from app.normalization import normalize_gstin, normalize_pan, normalize_pincode


class IdentifierNormalizerTest(unittest.TestCase):
    def test_pan_noise_cleaning_and_validation(self):
        result = normalize_pan("PAN NO: ABCPD1234F")
        self.assertEqual(result.normalized_pan, "ABCPD1234F")
        self.assertTrue(result.is_valid)

    def test_pan_invalid_status_character(self):
        result = normalize_pan("ABCZE1234F")
        self.assertEqual(result.normalized_pan, "ABCZE1234F")
        self.assertFalse(result.is_valid)

    def test_gstin_noise_cleaning_validation_and_state(self):
        result = normalize_gstin("GSTIN: 29ABCPD1234F1Z5")
        self.assertEqual(result.normalized_gstin, "29ABCPD1234F1Z5")
        self.assertTrue(result.is_valid)
        self.assertEqual(result.embedded_pan, "ABCPD1234F")
        self.assertEqual(result.state_code, "29")
        self.assertEqual(result.state_name, "Karnataka")

    def test_gstin_invalid_when_embedded_pan_is_invalid(self):
        result = normalize_gstin("29ABCZE1234F1Z5")
        self.assertFalse(result.is_valid)

    def test_gstin_pincode_alignment_consistent(self):
        result = normalize_gstin("29ABCPD1234F1Z5", "560058")
        self.assertTrue(result.pincode_alignment)

    def test_gstin_pincode_alignment_inconsistent(self):
        result = normalize_gstin("29ABCPD1234F1Z5", "400001")
        self.assertFalse(result.pincode_alignment)

    def test_pincode_extraction_deduplicates_end_values(self):
        result = normalize_pincode("Peenya, Bangalore - 560058 560058")
        self.assertEqual(result.normalized_pincode, "560058")
        self.assertTrue(result.is_valid)
        self.assertEqual(result.region, "South")

    def test_pincode_invalid_starting_zero(self):
        result = normalize_pincode("PIN 060058")
        self.assertEqual(result.normalized_pincode, "")
        self.assertFalse(result.is_valid)


if __name__ == "__main__":
    unittest.main()
