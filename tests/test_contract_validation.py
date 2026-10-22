import json
import unittest
from pathlib import Path

from scripts.validate_contracts import validators


class ContractValidationTests(unittest.TestCase):
    def test_supplied_examples_and_negative_cases(self):
        root = Path("contracts/examples")
        checks = validators(Path("contracts"))
        for path in (root / "valid").glob("*.json"):
            checks[path.stem].validate(json.loads(path.read_text()))
        for path in (root / "invalid").glob("*.json"):
            if path.name == "manifest.json":
                continue
            schema = path.stem.split("_")[0]
            self.assertTrue(
                list(checks[schema].iter_errors(json.loads(path.read_text()))),
                path.name,
            )
