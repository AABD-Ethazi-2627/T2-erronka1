"""Mutation checks for the public row-boundary audit."""

import copy
import json
import unittest
from pathlib import Path

from scripts.audit_cg40_partitions import audit


class PartitionAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(
            (
                Path(__file__).resolve().parents[2]
                / "docs/evidence/CG34_20261023/manifest.json"
            ).read_text()
        )

    def test_published_manifest(self):
        self.assertEqual(audit(self.manifest)["status"], "pass")

    def test_rejects_corrupt_boundaries(self):
        for mutation in (
            "duplicate", "outer_leak", "excluded", "repeated_fold", "missing_fold"
        ):
            with self.subTest(mutation=mutation):
                manifest = copy.deepcopy(self.manifest)
                if mutation == "duplicate":
                    manifest["outer"][0]["fit"].append(manifest["outer"][0]["fit"][0])
                elif mutation == "outer_leak":
                    manifest["outer"][0]["inner"][0]["fit"][0] = manifest["outer"][0]["held"][0]
                elif mutation == "excluded":
                    manifest["screening"][0]["fit"][0] = manifest["membership"]["excluded"][0]
                elif mutation == "repeated_fold":
                    manifest["outer"][1] = copy.deepcopy(manifest["outer"][0])
                else:
                    manifest["outer"].pop()
                with self.assertRaises(ValueError):
                    audit(manifest)
