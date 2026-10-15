"""Exercise CI's real artifact checks, including a tampered source manifest."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.check_ml_artifacts import check

ROOT = Path(__file__).resolve().parents[1]


class ArtifactCheckTests(unittest.TestCase):
    def test_delivered_models_match_saved_scores_and_reports(self):
        check(ROOT)

    def test_mismatched_source_hash_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(ROOT / "data", root / "data")
            shutil.copytree(ROOT / "models", root / "models")
            path = root / "models/offline-ai4i-v2/report.json"
            report = json.loads(path.read_text())
            report["source_sha256"] = "bad"
            path.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, "source hash"):
                check(root)
