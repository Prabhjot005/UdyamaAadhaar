import unittest

from app.normalization import NameNormalizationOptions, normalize_name


class NameNormalizerTest(unittest.TestCase):
    def test_final_example(self):
        self.assertEqual(normalize_name(" M/S ABC Technologies Pvt. Ltd. "), "abc technology")

    def test_unicode_special_chars_and_suffixes(self):
        self.assertEqual(normalize_name("Café-Tech & Co."), "cafe technology")

    def test_duplicate_tokens_and_abbreviations(self):
        self.assertEqual(normalize_name("abc abc tech svc"), "abc technology services")

    def test_acronym_spacing(self):
        self.assertEqual(normalize_name("A B C Tech"), "abc technology")

    def test_numbers_and_roman_numerals(self):
        self.assertEqual(normalize_name("First Systems II Pvt Ltd"), "1st technology 2")

    def test_optional_token_sorting(self):
        options = NameNormalizationOptions(sort_tokens=True)
        self.assertEqual(normalize_name("tech abc", options), "abc technology")


if __name__ == "__main__":
    unittest.main()
