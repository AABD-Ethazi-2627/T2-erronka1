"""Fail-closed OTel input/linkage guards; no Java or project services."""

import importlib.util
import io
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "deploy/images/nifi-patches/otel-qualification/qualify.py"


def load_tool():
    if not TOOL.exists():
        raise AssertionError("qualification implementation not present")
    spec = importlib.util.spec_from_file_location("otel_qualification", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def jar(files):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        for name, data in files:
            archive.writestr(name, data)
    return stream.getvalue()


class OtelQualificationGuards(unittest.TestCase):
    def test_archive_rejects_duplicate_dependency_instead_of_selecting_last(self):
        q = load_tool()
        with self.assertWarns(UserWarning):
            data = jar(
                [
                    ("META-INF/bundled-dependencies/a.jar", b"first"),
                    ("META-INF/bundled-dependencies/a.jar", b"second"),
                ]
            )
        with self.assertRaisesRegex(ValueError, "duplicate"):
            list(q.jar_entries(data))

    def test_archive_rejects_path_escape_before_returning_payload(self):
        q = load_tool()
        data = jar([("META-INF/bundled-dependencies/../a.jar", b"unsafe")])
        with self.assertRaisesRegex(ValueError, "path"):
            list(q.jar_entries(data))

    def test_checked_input_rejects_symlink_even_to_matching_bytes(self):
        q = load_tool()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "actual.jar"
            path.write_bytes(b"known")
            link = Path(tmp) / "linked.jar"
            link.symlink_to(path)
            with self.assertRaisesRegex(ValueError, "link"):
                q.checked(
                    link,
                    "7117fff2d0fd294462b3c802b7cb8753579f23f3946b99b5c5a67b78a7a1856c",
                )

    def test_checked_input_drift_does_not_create_output(self):
        q = load_tool()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "input.jar"
            path.write_bytes(b"wrong")
            with self.assertRaisesRegex(ValueError, "integrity"):
                q.checked(path, "0" * 64)
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()), ["input.jar"])

    def test_manifest_ancestry_rejects_missing_parent(self):
        q = load_tool()
        roots = {
            "child": {
                "Nar-Id": "child",
                "Nar-Group": "g",
                "Nar-Version": "1",
                "Nar-Dependency-Id": "missing",
                "Nar-Dependency-Group": "g",
                "Nar-Dependency-Version": "1",
            }
        }
        with self.assertRaisesRegex(ValueError, "parent"):
            q.parent_chain(roots, "child")

    def test_manifest_ancestry_rejects_cycle(self):
        q = load_tool()
        roots = {
            name: {
                "Nar-Id": name,
                "Nar-Group": "g",
                "Nar-Version": "1",
                "Nar-Dependency-Id": parent,
                "Nar-Dependency-Group": "g",
                "Nar-Dependency-Version": "1",
            }
            for name, parent in [("a", "b"), ("b", "a")]
        }
        with self.assertRaisesRegex(ValueError, "cycle"):
            q.parent_chain(roots, "a")

    def test_manifest_ancestry_preserves_actual_child_to_parent_order(self):
        q = load_tool()
        roots = {
            "child": {
                "Nar-Id": "child",
                "Nar-Group": "g",
                "Nar-Version": "1",
                "Nar-Dependency-Id": "parent",
                "Nar-Dependency-Group": "g",
                "Nar-Dependency-Version": "1",
            },
            "parent": {"Nar-Id": "parent", "Nar-Group": "g", "Nar-Version": "1"},
        }
        self.assertEqual(q.parent_chain(roots, "child"), ["child", "parent"])

    def test_linkage_negative_control_missing_api_method_is_detected(self):
        q = load_tool()
        key = ("method", "parse", "(Ljava/lang/String;)V")
        old = {"io/opentelemetry/Api": {"members": {key: 1}, "parents": []}}
        new = {"io/opentelemetry/Api": {"members": {}, "parents": []}}
        refs = [
            (
                "consumer/Caller",
                ("io/opentelemetry/Api", "parse", "(Ljava/lang/String;)V", "method"),
            )
        ]
        result = q.newly_broken(old, new, refs)
        self.assertEqual(
            result,
            [
                {
                    "consumer": "consumer/Caller",
                    "reference": [
                        "io/opentelemetry/Api",
                        "parse",
                        "(Ljava/lang/String;)V",
                        "method",
                    ],
                }
            ],
        )

    def test_linkage_resolves_preserved_inherited_member(self):
        q = load_tool()
        key = ("method", "context", "()V")
        models = {
            "io/opentelemetry/Child": {
                "members": {},
                "parents": ["io/opentelemetry/Base"],
            },
            "io/opentelemetry/Base": {"members": {key: 1}, "parents": []},
        }
        refs = [
            ("consumer/Caller", ("io/opentelemetry/Child", "context", "()V", "method"))
        ]
        self.assertEqual(q.newly_broken(models, models, refs), [])

    def test_linkage_refuses_vacuous_consumer_result(self):
        q = load_tool()
        with self.assertRaisesRegex(ValueError, "consumer"):
            q.newly_broken({}, {}, [])

    def test_api_closure_includes_common_required_by_context(self):
        q = load_tool()
        resolve = getattr(q, "required_closure", None)
        self.assertIsNotNone(resolve, "published transitive dependency guard absent")
        poms = {
            "g:api:1": [
                {
                    "groupId": "g",
                    "artifactId": "context",
                    "version": "1",
                    "scope": "compile",
                    "optional": None,
                }
            ],
            "g:context:1": [
                {
                    "groupId": "g",
                    "artifactId": "common",
                    "version": "1",
                    "scope": "compile",
                    "optional": None,
                }
            ],
            "g:common:1": [],
        }
        self.assertEqual(
            resolve(poms, "g:api:1"), ["g:api:1", "g:common:1", "g:context:1"]
        )
        with self.assertRaisesRegex(ValueError, "missing"):
            resolve(
                {"g:api:1": poms["g:api:1"], "g:context:1": poms["g:context:1"]},
                "g:api:1",
            )

    def test_real_static_entrypoint_keeps_class_index_separate_from_pom_models(self):
        # Four genuine minimal class-file byte structures and 189 tiny ZIPs exercise
        # the real CLI, including its nonvacuous missing-API mutation control.
        # This is a synthetic static contract, not a NiFi/JVM acceptance fixture.
        def klass(name, parent="java/lang/Object"):
            pool = (
                b"\x01"
                + struct.pack(">H", len(name))
                + name.encode()
                + b"\x07\x00\x01"
                + b"\x01"
                + struct.pack(">H", len(parent))
                + parent.encode()
                + b"\x07\x00\x03"
            )
            return (
                struct.pack(">IHHH", 0xCAFEBABE, 0, 52, 5)
                + pool
                + struct.pack(">HHHHHHH", 0x21, 2, 4, 0, 0, 0, 0)
            )

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            tools = base / "tools"
            tools.mkdir()
            cache = base / "cache"
            cache.mkdir()
            proof = base / "proof"
            proof.mkdir()
            for name in ("qualify.py", "run_phase.py"):
                shutil.copyfile(TOOL.parent / name, tools / name)
            q = load_tool()
            fixed = {}
            pins = []
            identities = {
                "api": "io/opentelemetry/api/OpenTelemetry",
                "context": "io/opentelemetry/context/Context",
                "common": "io/opentelemetry/common/ComponentLoader",
            }
            leaf = proof / "expanded-old/nifi-gcp-nar/NAR-INF/bundled-dependencies"
            leaf.mkdir(parents=True)
            for artifact, identity in identities.items():
                data = jar([(identity + ".class", klass(identity))])
                (leaf / f"opentelemetry-{artifact}-1.62.0.jar").write_bytes(data)
                name = f"opentelemetry-{artifact}-1.67.0.jar"
                (cache / name).write_bytes(data)
                fixed[name] = {"sha256": q.sha(data)}
                dependency = {"api": "context", "context": "common"}.get(artifact)
                body = (
                    f"<dependencies><dependency><groupId>io.opentelemetry</groupId><artifactId>opentelemetry-{dependency}</artifactId><version>1.67.0</version><scope>compile</scope></dependency></dependencies>"
                    if dependency
                    else ""
                )
                pom = (
                    f'<project xmlns="http://maven.apache.org/POM/4.0.0"><groupId>io.opentelemetry</groupId><artifactId>opentelemetry-{artifact}</artifactId><version>1.67.0</version>{body}</project>'
                ).encode()
                name = f"opentelemetry-{artifact}-1.67.0.pom"
                (cache / name).write_bytes(pom)
                pins.append(
                    {
                        "file": name,
                        "sha256": q.sha(pom),
                        "coordinate": f"io.opentelemetry:opentelemetry-{artifact}:1.67.0",
                    }
                )
            data = jar(
                [
                    (
                        "consumer/Actual.class",
                        klass("consumer/Actual", "io/opentelemetry/api/OpenTelemetry"),
                    )
                ]
            )
            (leaf / "consumer.jar").write_bytes(data)
            for index in range(185):
                (leaf / f"empty-{index}.jar").write_bytes(jar([]))
            for version in ("1.62.0", "1.67.0"):
                name = f"opentelemetry-api-{version}-sources.jar"
                data = jar(
                    [
                        (
                            "io/opentelemetry/api/trace/propagation/W3CTraceContextPropagator.java",
                            b"// synthetic static fixture\n",
                        )
                    ]
                )
                (cache / name).write_bytes(data)
                pins.append(
                    {
                        "file": name,
                        "sha256": q.sha(data),
                        "coordinate": f"io.opentelemetry:opentelemetry-api:{version}",
                    }
                )
            original = base / "original.nar"
            original.write_bytes(b"synthetic source integrity sentinel")
            known = {
                "image_id": "synthetic-not-an-image",
                "existing_fixed_artifacts": fixed,
                "nar_chain": [
                    {
                        "id": "nifi-gcp-nar",
                        "path": str(original).lstrip("/"),
                        "sha256": q.sha(original.read_bytes()),
                    }
                ],
            }
            (tools / "known-inputs.json").write_text(json.dumps(known))
            (tools / "public-pins.json").write_text(json.dumps({"files": pins}))
            result = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(tools / "run_phase.py"),
                    "static",
                    "--proof",
                    str(proof),
                ],
                env=os.environ | {"CNC_OTEL_CACHE": str(cache)},
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads((proof / "static-result.json").read_text())
            self.assertEqual(report["references_examined"], 1)
            self.assertEqual(
                report["variants"]["api-context-common"][
                    "negative_missing_api_class_new_failures"
                ],
                1,
            )
            self.assertEqual(
                report["variants"]["api-context-common"][
                    "newly_broken_direct_or_otel_inherited_references"
                ],
                [],
            )

    def test_aligned_selection_cannot_add_unobserved_family_artifact(self):
        path = TOOL.with_name("aligned.py")
        self.assertTrue(path.exists(), "aligned selection guard not implemented")
        spec = importlib.util.spec_from_file_location("otel_aligned", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        known = {
            "old_gcp_otel": {
                "opentelemetry-api-1.62.0.jar": "a",
                "opentelemetry-sdk-common-1.62.0.jar": "b",
            }
        }
        self.assertEqual(
            module.select_observed(known, ["api", "sdk-common"]),
            {
                "opentelemetry-api-1.62.0.jar": "opentelemetry-api-1.67.0.jar",
                "opentelemetry-sdk-common-1.62.0.jar": "opentelemetry-sdk-common-1.67.0.jar",
            },
        )
        with self.assertRaisesRegex(ValueError, "unobserved"):
            module.select_observed(known, ["api", "sdk-common", "exporter-otlp"])


if __name__ == "__main__":
    unittest.main()
