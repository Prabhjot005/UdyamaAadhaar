import unittest

from app.similarity_matching.matcher import _weighted_vector_score


class SimilarityWeightingTest(unittest.TestCase):
    def test_weighted_score_uses_name_pincode_and_address_weights(self):
        incoming = {
            "normalized_name": "AARAV PRECISION TOOLS",
            "normalized_address": "PLOT 12 INDUSTRIAL AREA PEENYA",
            "normalized_pincode": "560058",
        }
        matched = {
            "normalized_name": "AARAV PRECISION TOOLS",
            "normalized_address": "PLOT 99 INDUSTRIAL AREA PEENYA",
            "normalized_pincode": "560058",
        }

        score, details = _weighted_vector_score(incoming, matched)

        expected = (
            (0.65 * details["name_score"])
            + (0.25 * details["pincode_score"])
            + (0.10 * details["address_score"])
        )
        self.assertAlmostEqual(score, expected)
        self.assertEqual(details["name_weight"], 0.65)
        self.assertEqual(details["pincode_weight"], 0.25)
        self.assertEqual(details["address_weight"], 0.10)
        self.assertEqual(details["name_score"], 1.0)
        self.assertEqual(details["pincode_score"], 1.0)


if __name__ == "__main__":
    unittest.main()
