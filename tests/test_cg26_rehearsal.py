import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class RehearsalCliTests(unittest.TestCase):
    def run_cli(self, manifest, output):
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.rehearse_cg26",
                "--manifest",
                str(manifest),
                "--output",
                str(output),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def test_missing_bundle_does_not_publish_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "result.json"
            process = self.run_cli(root / "missing.json", output)
            self.assertNotEqual(process.returncode, 0)
            self.assertFalse(output.exists())
            self.assertNotIn("PASS", process.stdout)

    def test_existing_evidence_is_preserved_before_loading_models(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "result.json"
            previous = b'{"prior_run": true}\n'
            output.write_bytes(previous)
            process = self.run_cli(root / "missing.json", output)
            self.assertNotEqual(process.returncode, 0)
            self.assertIn("FileExistsError", process.stderr)
            self.assertEqual(output.read_bytes(), previous)
