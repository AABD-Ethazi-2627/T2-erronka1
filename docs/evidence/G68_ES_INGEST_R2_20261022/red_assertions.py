"""Expected failures against raw HTTP captured before the corrections."""

import json
import unittest
from pathlib import Path

raw = json.loads((Path(__file__).resolve().parent / "red-result.json").read_text())
errors = [
    op["response"] for op in raw["operations"] if op["path"].endswith("/_doc/rejected")
]


class BeforeFix(unittest.TestCase):
    def test_template_only_accepts_valid_prediction(self):
        self.assertEqual(raw["F1"]["actual_status"], 201)

    def test_old_verifier_unknown_root_mapping_assertion(self):
        self.assertIn("strict_dynamic_mapping_exception", json.dumps(errors[0]))

    def test_old_verifier_unknown_source_mapping_assertion(self):
        self.assertIn("strict_dynamic_mapping_exception", json.dumps(errors[1]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
