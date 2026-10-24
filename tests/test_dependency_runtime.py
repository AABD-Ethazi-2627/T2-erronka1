"""The serving image must consume the lock, including transitives and hashes."""

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.export_runtime import check, render

ROOT = Path(__file__).resolve().parents[1]


class RuntimeExportTests(unittest.TestCase):
    def test_export_includes_transitives_and_hashes_without_research_packages(self):
        exported = render(ROOT)
        requirements = exported.replace("\\\n", " ").splitlines()
        packages = {}
        for line in requirements:
            if not line or line.startswith("#"):
                continue
            self.assertIn("==", line)
            self.assertIn("--hash=sha256:", line)
            packages[line.split("==", 1)[0]] = line
        for name in ("fastapi", "pydantic", "pydantic-core", "h11", "scipy", "numpy"):
            self.assertIn(name, packages)
        for name in ("catboost", "pytest", "httpx2", "kafka-python", "matplotlib"):
            self.assertNotIn(name, packages)
        self.assertTrue(check(ROOT, ROOT / "scoring/requirements.txt"))

    def test_drift_and_missing_file_fail_without_rewriting_the_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "requirements.txt"
            self.assertFalse(check(ROOT, path))
            self.assertFalse(path.exists())
            path.write_text("fastapi==0.0.1\n")
            self.assertFalse(check(ROOT, path))
            self.assertEqual(path.read_text(), "fastapi==0.0.1\n")
            path.write_bytes(render(ROOT).encode("utf-8"))
            self.assertTrue(check(ROOT, path))

    def test_failed_export_is_not_treated_as_an_empty_valid_lock(self):
        with patch("scripts.export_runtime.subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess([], 2, "", "missing group")
            with self.assertRaisesRegex(RuntimeError, "missing group"):
                render(ROOT)
