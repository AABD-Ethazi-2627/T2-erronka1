"""A consistent retrain must not replace the sealed load-test model."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import cg32_lab as lab


class DeliveryBundleTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = self.root / "manifest.json"
        self.identity = self.root / "identity.json"
        files = {}
        for name in ("rf.pkl", "if.pkl"):
            content = f"sealed local fixture {name}".encode()
            (self.root / name).write_bytes(content)
            files[name] = hashlib.sha256(content).hexdigest()
        self.manifest.write_text(
            json.dumps({"model_version": "same-label", "files": files}),
            encoding="utf-8",
        )
        self.identity.write_text(
            json.dumps(
                {
                    "manifest_sha256": lab.sha_file(self.manifest),
                    "model_hashes": files,
                }
            ),
            encoding="utf-8",
        )
        self.reference = patch.object(lab, "DELIVERY_RECORD", self.identity)
        self.reference.start()
        self.addCleanup(self.reference.stop)

    def test_accepts_exact_sealed_bundle(self):
        result = lab.verify_bundle(self.manifest)
        self.assertEqual(result["sha256"], lab.sha_file(self.manifest))
        self.assertEqual(result["path"], self.manifest.resolve())

    def test_rejects_consistent_replacement_with_same_model_version(self):
        replacement = b"locally retrained but different bytes"
        (self.root / "rf.pkl").write_bytes(replacement)
        manifest = json.loads(self.manifest.read_text(encoding="utf-8"))
        manifest["files"]["rf.pkl"] = hashlib.sha256(replacement).hexdigest()
        self.manifest.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(SystemExit, "sealed CG26 delivery"):
            lab.verify_bundle(self.manifest)

    def test_rejects_artifact_corruption_without_changing_manifest(self):
        (self.root / "if.pkl").write_bytes(b"corrupted")
        with self.assertRaisesRegex(SystemExit, "artifact hash mismatch: if.pkl"):
            lab.verify_bundle(self.manifest)

    def test_rejects_inconsistent_sealed_record(self):
        identity = json.loads(self.identity.read_text(encoding="utf-8"))
        identity["model_hashes"].pop("if.pkl")
        self.identity.write_text(json.dumps(identity), encoding="utf-8")
        with self.assertRaisesRegex(SystemExit, "file identities differ"):
            lab.verify_bundle(self.manifest)


if __name__ == "__main__":
    unittest.main()
