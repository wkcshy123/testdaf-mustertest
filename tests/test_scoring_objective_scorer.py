import unittest

from scoring_platform.services.objective_scorer import _check_short_text


class ObjectiveScorerFuzzyMatchTest(unittest.TestCase):
    def test_fuzzy_match_rejects_changed_deadline(self) -> None:
        result = _check_short_text(
            "Anmeldung bis Montag",
            {"answer": "Anmeldung bis Freitag", "acceptable_variants": []},
        )
        self.assertFalse(result["is_correct"])

    def test_fuzzy_match_rejects_negation_mismatch(self) -> None:
        result = _check_short_text(
            "keine Anmeldung an der Uni",
            {"answer": "Online Anmeldung an der Uni", "acceptable_variants": []},
        )
        self.assertFalse(result["is_correct"])


if __name__ == "__main__":
    unittest.main()
