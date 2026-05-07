import unittest

from app.normalization import normalize_address, normalize_address_with_metadata


class AddressNormalizerTest(unittest.TestCase):
    def test_special_character_strip_and_whitespace(self):
        self.assertEqual(normalize_address("Flat #101/A, Near Main Rd!!!"), "FLAT 101/A")

    def test_whitespace_normalization(self):
        self.assertEqual(normalize_address("5th  Main,   HSR   Layout"), "5TH MAIN, HSR LAYOUT")

    def test_road_suffix_expansion(self):
        self.assertEqual(normalize_address("MG RD, 4TH ST, 12TH LN"), "MG ROAD, 4TH STREET, 12TH LANE")

    def test_unit_and_floor_expansion(self):
        self.assertEqual(
            normalize_address("FLT 201, APT 4B, BLDG 5, 3rd FL, GR FL, 1st BSMT"),
            "FLAT 201, APARTMENT 4B, BUILDING 5, 3RD FLOOR, GROUND FLOOR, 1ST BASEMENT",
        )

    def test_industrial_zone_expansion(self):
        self.assertEqual(normalize_address("Peenya Indl Estate Ph-2"), "PEENYA INDUSTRIAL ESTATE PHASE 2")

    def test_regional_suffix_mapping(self):
        self.assertEqual(
            normalize_address("Bilekhalli, Jngr, Bommanahll"),
            "BILEKAHALLI, JAYANAGAR, BOMMANAHALLI",
        )

    def test_landmark_metadata_extraction(self):
        result = normalize_address_with_metadata("Opposite Metro Station")
        self.assertEqual(result.normalized_address, "")
        self.assertEqual(result.landmarks, ["OPPOSITE METRO STATION"])

    def test_landmark_extraction_from_mixed_address(self):
        result = normalize_address_with_metadata("FLT 201, Opp Metro Station, MG Rd")
        self.assertEqual(result.normalized_address, "FLAT 201, MG ROAD")
        self.assertEqual(result.landmarks, ["OPPOSITE METRO STATION"])


if __name__ == "__main__":
    unittest.main()
