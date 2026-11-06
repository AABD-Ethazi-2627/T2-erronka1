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


class CorrectedCoverageGuards(unittest.TestCase):
    def helper(self):
        path = TOOL.with_name("coverage.py")
        spec = importlib.util.spec_from_file_location("otel_coverage", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def model(self, parents=(), members=None, flags=1):
        return {
            "parents": list(parents),
            "members": members or {},
            "flags": flags,
            "references": [],
            "reference_details": [],
            "descriptor_types": [],
        }

    def test_emitted_report_cannot_promote_qualification(self):
        q = load_tool()
        r = q.preparation_report(status="component-tested")
        self.assertIsNone(r["replacement"])
        self.assertFalse(r["runtime_approved"])
        for kw in ({"runtime_approved": True}, {"replacement": "applied"}):
            with self.assertRaisesRegex(ValueError, "promotion"):
                q.preparation_report(**kw)

    def test_unresolved_classifies_exact_jdk_inheritance_and_new_incubator(self):
        c = self.helper()
        owner = "io/opentelemetry/Enum"
        model = {owner: self.model(["java/lang/Enum"])}
        refs = [
            (
                "gcp!exporter.jar!outside/Caller.class",
                (owner, "ordinal", "()I", "method"),
            ),
            (
                "gcp!opentelemetry-sdk-1.67.0.jar!io/opentelemetry/Sdk.class",
                ("io/opentelemetry/api/incubator/BoundThing", "", "", "class"),
            ),
        ]
        records = c.classify_unresolved(model, refs, "aligned", set())
        self.assertEqual(
            [r["category"] for r in records],
            ["jdk-inherited-member", "internal-optional-incubator"],
        )
        self.assertTrue(
            all(r["scenario"] == "aligned" and not r["seen_in_old"] for r in records)
        )
        c.require_closed(records)

    def test_unresolved_unknown_new_sdk_symbol_fails_even_if_absent_before(self):
        c = self.helper()
        refs = [
            (
                "gcp!opentelemetry-sdk-1.67.0.jar!io/opentelemetry/Sdk.class",
                ("io/opentelemetry/common/impl/ConfigUtil", "", "", "class"),
            )
        ]
        records = c.classify_unresolved({}, refs, "sdk-new-api-old", set())
        self.assertEqual(records[0]["category"], "unknown")
        with self.assertRaisesRegex(ValueError, "unclassified"):
            c.require_closed(records)

    def test_external_incubator_reference_fails_closed(self):
        c = self.helper()
        r = c.classify_unresolved(
            {},
            [
                (
                    "gcp!consumer.jar!outside/C.class",
                    ("io/opentelemetry/api/incubator/Thing", "", "", "class"),
                )
            ],
            "aligned",
            set(),
        )
        with self.assertRaisesRegex(ValueError, "unclassified"):
            c.require_closed(r)

    def test_external_otel_contrib_incubator_is_not_sdk_internal(self):
        c = self.helper()
        rows = c.classify_unresolved(
            {},
            [
                (
                    "g!opentelemetry-gcp-resources-1.37.0-alpha.jar!io/opentelemetry/contrib/C.class",
                    ("io/opentelemetry/api/incubator/Missing", "", "", "class"),
                )
            ],
            "aligned",
            set(),
        )
        with self.assertRaisesRegex(ValueError, "unclassified"):
            c.require_closed(rows)

    def test_jdk_method_name_alone_cannot_hide_missing_owner_or_wrong_signature(self):
        c = self.helper()
        owner = "io/opentelemetry/Missing"
        for models, ref in [
            ({}, (owner, "ordinal", "()I", "method")),
            (
                {owner: self.model(["java/lang/Object"])},
                (owner, "ordinal", "()I", "method"),
            ),
            (
                {owner: self.model(["java/lang/Enum"])},
                (owner, "ordinal", "()J", "method"),
            ),
        ]:
            with self.subTest(ref=ref, models=models):
                rows = c.classify_unresolved(
                    models, [("g!x.jar!C.class", ref)], "aligned", set()
                )
                with self.assertRaises(ValueError):
                    c.require_closed(rows)

    def test_abi_delta_reports_removed_abstract_access_static_and_external_impact(self):
        c = self.helper()
        key = ("method", "work", "()V")
        old = {"io/opentelemetry/Base": self.model(members={key: 1})}
        new = {"io/opentelemetry/Base": self.model(members={key: 0x409})}
        outside = {"outside/Impl": self.model(["io/opentelemetry/Base"])}
        report = c.abi_delta(
            old,
            new,
            outside,
            [
                (
                    "g!outside.jar!outside/Impl.class",
                    ("io/opentelemetry/Base", "work", "()V", "method", 10),
                )
            ],
        )
        self.assertEqual(len(report["new_abstract_members"]), 1)
        self.assertEqual(len(report["static_changes"]), 1)
        self.assertTrue(report["external_impacts"])
        removed = c.abi_delta(old, {"io/opentelemetry/Base": self.model()}, {}, [])
        self.assertEqual(len(removed["declared_public_protected_removals"]), 1)

    def test_existing_input_inventory_is_verified_before_class_parsing(self):
        c = self.helper()
        q = load_tool()
        with tempfile.TemporaryDirectory() as tmp:
            b = Path(tmp)
            top = b / "top"
            top.mkdir()
            leaf = b / "expanded/gcp/NAR-INF/bundled-dependencies"
            leaf.mkdir(parents=True)
            (leaf / "a.jar").write_bytes(b"changed")
            known = {
                "nar_chain": [
                    {
                        "id": "gcp",
                        "direct_jars": [
                            {
                                "entry": "META-INF/bundled-dependencies/a.jar",
                                "sha256": q.sha(b"old"),
                            }
                        ],
                    }
                ],
                "launcher_jars": [],
            }
            with self.assertRaisesRegex(ValueError, "integrity"):
                c.verify_expanded(known, b / "expanded", top)

    def test_inventory_rejects_extra_jars_and_expected_origins_use_pins(self):
        c = self.helper()
        q = load_tool()
        with tempfile.TemporaryDirectory() as tmp:
            b = Path(tmp)
            top = b / "top"
            top.mkdir()
            leaf = b / "expanded/gcp/NAR-INF/bundled-dependencies"
            leaf.mkdir(parents=True)
            (leaf / "a.jar").write_bytes(b"old")
            known = {
                "nar_chain": [
                    {
                        "id": "gcp",
                        "direct_jars": [
                            {
                                "entry": "META-INF/bundled-dependencies/a.jar",
                                "sha256": q.sha(b"old"),
                            }
                        ],
                    }
                ],
                "launcher_jars": [],
            }
            c.verify_expanded(known, b / "expanded", top)
            self.assertEqual(
                c.expected_origin(known, {"files": []}, "a.jar"), q.sha(b"old")
            )
            (leaf / "planted.jar").write_bytes(b"new")
            with self.assertRaisesRegex(ValueError, "inventory"):
                c.verify_expanded(known, b / "expanded", top)

    def test_consumer_results_are_parsed_from_observed_output_only(self):
        c = self.helper()
        rows = c.observed_consumers(
            "consumer-init\tA\tPASS\t-\nconsumer-init\tB\tFAIL\tjava.lang.NoClassDefFoundError\n"
        )
        self.assertEqual(
            rows,
            {
                "A": {"status": "PASS", "cause": "-"},
                "B": {"status": "FAIL", "cause": "java.lang.NoClassDefFoundError"},
            },
        )
        with self.assertRaisesRegex(ValueError, "coverage"):
            c.require_consumer_parity(rows, {"A": rows["A"]}, ["A", "B"])
        c.require_consumer_parity(rows, rows, ["A", "B"])

    def test_parser_retains_methodref_interface_methodref_and_descriptor_types(self):
        pool = []

        def utf(value):
            pool.append(b"\x01" + struct.pack(">H", len(value)) + value.encode())
            return len(pool)

        def entry(tag, *values):
            pool.append(bytes([tag]) + b"".join(struct.pack(">H", v) for v in values))
            return len(pool)

        caller = entry(7, utf("outside/Caller"))
        parent = entry(7, utf("java/lang/Object"))
        owner = entry(7, utf("io/opentelemetry/Api"))
        name = utf("work")
        desc = utf("()Lio/opentelemetry/Result;")
        nt = entry(12, name, desc)
        entry(10, owner, nt)
        entry(11, owner, nt)
        data = struct.pack(">IHHH", 0xCAFEBABE, 0, 52, len(pool) + 1) + b"".join(pool)
        data += struct.pack(">HHHHH", 0x21, caller, parent, 0, 0)
        data += struct.pack(">HHHHHH", 1, 1, name, desc, 0, 0)
        model = load_tool().parse(data)
        methods = [r for r in model["reference_details"] if r[3] == "method"]
        self.assertEqual({r[4] for r in methods}, {10, 11})
        self.assertEqual(model["descriptor_types"], ["io/opentelemetry/Result"])

    def test_abi_guard_accepts_external_implementation_of_new_abstract(self):
        c = self.helper()
        key = ("method", "work", "()V")
        old = {"io/opentelemetry/Base": self.model(members={key: 1})}
        new = {"io/opentelemetry/Base": self.model(members={key: 0x401})}
        outside = {"outside/Impl": self.model(["io/opentelemetry/Base"], {key: 1})}
        self.assertEqual(c.abi_delta(old, new, outside, [])["external_impacts"], [])

    def test_security_source_diff_requires_real_encoding_change(self):
        c = self.helper()
        with tempfile.TemporaryDirectory() as tmp:
            b = Path(tmp)
            entry = "io/opentelemetry/api/trace/propagation/internal/W3CTraceContextEncoding.java"
            for v in ("1.62.0", "1.67.0"):
                (b / (v + ".jar")).write_bytes(jar([(entry, b"same")]))
            with self.assertRaisesRegex(ValueError, "empty"):
                c.source_change(b / "1.62.0.jar", b / "1.67.0.jar", entry)


if __name__ == "__main__":
    unittest.main()
