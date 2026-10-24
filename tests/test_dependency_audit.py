"""An unavailable feed or an uncovered lock source must never look clean."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from scripts.audit_dependencies import (
    PyPIRedirectHandler,
    audit,
    requirements_rows,
    uv_tool_version,
    validate_metadata_url,
)


def package(name="demo", version="1.0", source=None):
    return {
        "name": name,
        "version": version,
        "source": source or {"registry": "https://pypi.org/simple"},
    }


def metadata(url):
    return {
        "info": {"version": "1.0", "requires_python": ">=3.11"},
        "vulnerabilities": [],
    }


class DependencyAuditTests(unittest.TestCase):
    def test_metadata_fetch_origin_is_restricted_to_pypi_https(self):
        validate_metadata_url("https://pypi.org/pypi/demo/1.0/json")
        validate_metadata_url("https://pypi.org:443/pypi/demo/json")
        for url in (
            "http://pypi.org/pypi/demo/json",
            "https://evil.invalid/pypi/demo/json",
            "https://pypi.org.evil.invalid/pypi/demo/json",
            "https://user@pypi.org/pypi/demo/json",
            "https://pypi.org/simple/demo",
            "https://pypi.org/pypi/demo/json?redirect=https://evil.invalid",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_metadata_url(url)

    def test_redirect_is_rejected_before_requesting_an_unapproved_origin(self):
        handler = PyPIRedirectHandler()
        with self.assertRaises(ValueError):
            handler.redirect_request(
                object(),
                None,
                302,
                "Found",
                {},
                "https://evil.invalid/metadata.json",
            )

    def test_separate_research_pins_are_covered_and_unknown_syntax_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "research.txt"
            path.write_text(
                "# generated pins\nnumpy==1.26.4\n    # via pandas\npsutil==7.1.0\n"
            )
            rows = requirements_rows(path)
            self.assertEqual([row["name"] for row in rows], ["numpy", "psutil"])
            self.assertTrue(audit(rows, Path("."), metadata)["passed"])
            path.write_text("numpy>=1.26\n")
            with self.assertRaisesRegex(ValueError, "pin"):
                requirements_rows(path)

    def test_all_rows_including_marker_only_and_project_are_accounted_for(self):
        rows = [package(), package("colorama"), package("app", source={"virtual": "."})]
        report = audit(rows, Path("."), metadata)
        self.assertTrue(report["passed"])
        self.assertEqual(len(report["packages"]), 3)
        self.assertEqual(report["packages"][2]["status"], "project")

    def test_active_advisories_fail_and_withdrawn_advisories_remain_visible(self):
        def fetch(url):
            data = metadata(url)
            data["vulnerabilities"] = [
                {"id": "GHSA-active", "aliases": ["CVE-123"], "withdrawn": None},
                {"id": "PYSEC-active", "aliases": ["CVE-123"], "withdrawn": None},
                {"id": "GHSA-old", "aliases": [], "withdrawn": "2026-01-01"},
            ]
            return data

        report = audit([package()], Path("."), fetch)
        self.assertFalse(report["passed"])
        result = report["packages"][0]
        self.assertEqual(len(result["advisories"]), 3)
        self.assertEqual(len(result["active_advisory_groups"]), 1)
        self.assertTrue(
            audit(
                [package()],
                Path("."),
                lambda u: {
                    **metadata(u),
                    "vulnerabilities": [{"id": "old", "withdrawn": "2026-01-01"}],
                },
            )["passed"]
        )

    def test_missing_or_malformed_advisory_feed_and_lookup_error_fail_closed(self):
        for value in (
            {"info": {}},
            {"vulnerabilities": None},
            {"vulnerabilities": [{}]},
            {"vulnerabilities": [{"id": "a", "withdrawn": True}]},
        ):
            with self.subTest(value=value):
                report = audit([package()], Path("."), lambda u, data=value: data)
                self.assertFalse(report["passed"])
                self.assertEqual(report["packages"][0]["status"], "error")

        def fail(url):
            raise TimeoutError("unavailable")

        report = audit([package(), package("other")], Path("."), fail)
        self.assertEqual(len(report["packages"]), 2)
        self.assertFalse(report["passed"])

    def test_unknown_sources_and_private_registry_are_not_silently_skipped(self):
        for source in (
            {"git": "https://example.invalid/repo"},
            {"registry": "https://example.invalid/simple"},
        ):
            with self.subTest(source=source):
                self.assertFalse(
                    audit([package(source=source)], Path("."), metadata)["passed"]
                )

    def test_local_wheel_hash_provenance_and_containment_are_required(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "vendor").mkdir()
            wheel = root / "vendor/demo.whl"
            with ZipFile(wheel, "w") as archive:
                archive.writestr(
                    "kafka_python-1.0+cncguard.2.dist-info/METADATA",
                    "Name: kafka-python\nVersion: 1.0+cncguard.2\nRequires-Python: >=3.9\n",
                )
            digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
            provenance = {
                "upstream": {"version": "1.0"},
                "patched": {
                    "filename": wheel.name,
                    "version": "1.0+cncguard.2",
                    "sha256": digest,
                },
            }
            (root / "vendor/kafka-python-provenance.json").write_text(
                json.dumps(provenance)
            )
            row = package("kafka-python", "1.0+cncguard.2", {"path": "vendor/demo.whl"})
            row["wheels"] = [{"hash": "sha256:" + digest}]
            result = audit([row], root, metadata)
            self.assertTrue(result["passed"])
            self.assertEqual(result["packages"][0]["status"], "local-upstream-only")
            self.assertEqual(result["packages"][0]["requires_python"], ">=3.9")
            self.assertEqual(
                result["packages"][0]["upstream_requires_python"], ">=3.11"
            )
            wheel.write_bytes(b"tampered")
            self.assertFalse(audit([row], root, metadata)["passed"])
            row["source"]["path"] = "../outside.whl"
            self.assertFalse(audit([row], root, metadata)["passed"])

    def test_latest_failure_does_not_leave_a_partial_clean_report(self):
        def fetch(url):
            if url.endswith("/1.0/json"):
                return metadata(url)
            raise TimeoutError()

        self.assertFalse(audit([package()], Path("."), fetch, latest=True)["passed"])

    def test_ci_cannot_silently_use_a_different_uv_than_the_audited_image(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "deploy").mkdir()
            workflows = root / ".github/workflows"
            workflows.mkdir(parents=True)
            (root / "deploy/images.json").write_text(
                json.dumps(
                    {
                        "uv": "ghcr.io/astral-sh/uv:0.13.5@sha256:" + "a" * 64,
                    }
                )
            )
            workflow = workflows / "test.yml"
            workflow.write_text(
                "- uses: astral-sh/setup-uv@sha\n  with:\n    version: '0.13.5'\n"
            )
            self.assertEqual(uv_tool_version(root), "0.13.5")
            workflow.write_text(workflow.read_text().replace("0.13.5", "0.13.1"))
            with self.assertRaisesRegex(ValueError, "uv"):
                uv_tool_version(root)
            workflow.write_text(workflow.read_text().replace("0.13.1", "0.13.5"))
            (workflows / "named.yml").write_text(
                "- name: Install tool\n  uses: astral-sh/setup-uv@sha\n  with:\n    version: '0.13.1'\n"
            )
            with self.assertRaisesRegex(ValueError, "uv"):
                uv_tool_version(root)
