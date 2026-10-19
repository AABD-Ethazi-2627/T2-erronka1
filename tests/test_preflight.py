import tempfile
import unittest
from pathlib import Path

from scripts.integration_preflight import inspect_checkout


class PreflightTests(unittest.TestCase):
    def test_missing_or_broken_api_never_counts_as_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertFalse(inspect_checkout(root)["ready"])
            (root / "scoring").mkdir()
            (root / "scoring/score_api.py").write_text("def health():\n")
            result = inspect_checkout(root)
            self.assertFalse(result["api_parses"])
            self.assertFalse(result["ready"])
