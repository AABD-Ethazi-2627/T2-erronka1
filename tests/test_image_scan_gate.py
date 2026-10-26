import unittest

from scripts.enforce_image_scan import validate


def report(*findings):
    return {
        "SchemaVersion": 2,
        "ArtifactType": "container_image",
        "ArtifactName": "fixture@sha256:" + "0" * 64,
        "Results": [
            {
                "Target": "fixture (alpine 3.23)",
                "Class": "os-pkgs",
                "Type": "alpine",
                "Vulnerabilities": [
                    {
                        "VulnerabilityID": vulnerability,
                        "PkgName": package,
                        "InstalledVersion": version,
                    }
                    for vulnerability, package, version in findings
                ]
            }
        ]
    }


class ImageScanGateTests(unittest.TestCase):
    def test_missing_coverage_is_not_a_clean_scan(self):
        empty = report()
        empty["Results"] = []
        wrong_kind = {**report(), "ArtifactType": "filesystem"}
        unidentified = {**report(), "Results": [{"Vulnerabilities": []}]}
        for data in ({}, {"Results": []}, empty, wrong_kind, unidentified):
            with self.subTest(report=data):
                self.assertTrue(validate("api", data))

    def test_clean_regular_image_passes(self):
        self.assertEqual(validate("api", report()), [])

    def test_every_unexpected_finding_fails(self):
        errors = validate("api", report(("CVE-X", "pkg", "1")))
        self.assertEqual(len(errors), 1)

    def test_filebeat_requires_only_the_reachability_checked_module_finding(self):
        verified = ("GO-2026-5932", "golang.org/x/crypto", "v0.57.0")
        self.assertEqual(validate("filebeat", report(verified)), [])
        self.assertTrue(validate("filebeat", report()))
        self.assertTrue(validate("filebeat", report(verified, ("CVE-X", "pkg", "1"))))

    def test_kibana_requires_only_the_exact_backported_node_forge_finding(self):
        verified = (
            ("CVE-2026-85393", "node-forge", "1.4.0+cncguard.1"),
            ("CVE-2026-19693", "extract-zip", "2.0.1+cncguard.1"),
            ("CVE-2026-56876", "extract-zip", "2.0.1+cncguard.1"),
        )
        self.assertEqual(validate("kibana", report(*verified)), [])
        self.assertTrue(validate("kibana", report()))
        self.assertTrue(validate("kibana", report(*verified, ("CVE-X", "pkg", "1"))))
