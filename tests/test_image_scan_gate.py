import unittest

from scripts.enforce_image_scan import validate


def report(*findings, image="api"):
    return {
        "SchemaVersion": 2,
        "ArtifactType": "container_image",
        "ArtifactName": "cnc-guard-audit:" + image,
        "Metadata": {"ImageID": "sha256:" + "0" * 64},
        "Results": [
            {
                "Target": "fixture (alpine 3.23)",
                "Class": "os-pkgs",
                "Type": "alpine",
                "Packages": [{"Name": "fixture-package", "Version": "1"}],
                "Vulnerabilities": [
                    {
                        "VulnerabilityID": vulnerability,
                        "PkgName": package,
                        "InstalledVersion": version,
                    }
                    for vulnerability, package, version in findings
                ],
            },
            {
                "Target": "Python",
                "Class": "lang-pkgs",
                "Type": {"filebeat": "gobinary", "kibana": "node-pkg"}.get(
                    image, "python-pkg"
                ),
                "Packages": [{"Name": "fixture-python-package", "Version": "1"}],
            },
            {
                "Target": "uv",
                "Class": "lang-pkgs",
                "Type": "rustbinary",
                "Packages": [{"Name": "fixture-rust-package", "Version": "1"}],
            },
        ],
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

    def test_targets_without_packages_and_misdirected_reports_fail(self):
        for packages in (None, [], [{}], [{"Name": "unversioned"}]):
            data = report()
            data["Results"][0]["Packages"] = packages
            with self.subTest(packages=packages):
                self.assertTrue(validate("api", data))
        self.assertTrue(validate("api", report(image="python")))
        data = report()
        del data["Metadata"]
        self.assertTrue(validate("api", data))
        data = report()
        data["Results"] = data["Results"][:1]
        self.assertTrue(validate("api", data))

    def test_uv_clean_report_needs_rust_packages_but_not_os_or_vulnerabilities(self):
        data = report()
        data["ArtifactName"] = "isolated-uv:fixture"
        data["Results"] = [
            {
                "Target": "uv",
                "Class": "lang-pkgs",
                "Type": "rustbinary",
                "Packages": [{"Name": "fixture-rust-package", "Version": "1"}],
            }
        ]
        self.assertEqual(
            validate("uv", data, expected_artifact="isolated-uv:fixture"), []
        )
        self.assertTrue(validate("api", data, expected_artifact="isolated-uv:fixture"))

    def test_every_unexpected_finding_fails(self):
        errors = validate("api", report(("CVE-X", "pkg", "1")))
        self.assertEqual(len(errors), 1)

    def test_java_node_and_go_runtimes_cannot_pass_with_os_only(self):
        for image in ("kafka", "nifi", "elasticsearch", "kibana", "go", "filebeat"):
            data = report(image=image)
            data["Results"] = data["Results"][:1]
            with self.subTest(image=image):
                self.assertIn(
                    "image report is missing required runtime package coverage",
                    validate(image, data, expected_artifact=data["ArtifactName"]),
                )

    def test_java_runtime_reports_pass_only_with_required_language_targets(self):
        for image in ("kafka", "nifi", "elasticsearch"):
            data = report(image=image)
            data["Results"][1]["Type"] = "jar"
            with self.subTest(image=image):
                self.assertEqual(
                    validate(image, data, expected_artifact=data["ArtifactName"]), []
                )
        api = report()
        api["Results"] = api["Results"][:2]
        self.assertTrue(validate("api", api))
        nifi = report(image="nifi")
        nifi["Results"][1]["Type"] = "jar"
        nifi["Results"] = nifi["Results"][:2]
        self.assertTrue(validate("nifi", nifi, expected_artifact=nifi["ArtifactName"]))

    def test_filebeat_requires_only_the_reachability_checked_module_finding(self):
        verified = ("GO-2026-5932", "golang.org/x/crypto", "v0.57.0")
        self.assertEqual(validate("filebeat", report(verified, image="filebeat")), [])
        self.assertTrue(validate("filebeat", report(image="filebeat")))
        self.assertTrue(
            validate(
                "filebeat", report(verified, ("CVE-X", "pkg", "1"), image="filebeat")
            )
        )

    def test_kibana_requires_only_the_exact_backported_node_forge_finding(self):
        verified = (
            ("CVE-2026-85393", "node-forge", "1.4.0+cncguard.1"),
            ("CVE-2026-19693", "extract-zip", "2.0.1+cncguard.1"),
            ("CVE-2026-56876", "extract-zip", "2.0.1+cncguard.1"),
        )
        self.assertEqual(validate("kibana", report(*verified, image="kibana")), [])
        self.assertTrue(validate("kibana", report(image="kibana")))
        self.assertTrue(
            validate("kibana", report(*verified, ("CVE-X", "pkg", "1"), image="kibana"))
        )
