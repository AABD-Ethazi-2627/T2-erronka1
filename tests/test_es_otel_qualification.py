"""Portable guards: fixtures/model checks are not ES runtime acceptance."""

import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

HERE = (
    Path(__file__).resolve().parents[1]
    / "deploy/images/elasticsearch-patches/otel-qualification"
)


def load(name):
    spec = importlib.util.spec_from_file_location(
        "_es_test_" + name, HERE / (name + ".py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


q = load("qualify")
r = load("run_reserved")


def inventory_fixture():
    pins = {
        p["file"]: p
        for p in json.loads((HERE / "reusable-official-pins.json").read_text())["files"]
    }
    rows = ["JAVA\t25.0.1\t25"]
    for realm in q.REALMS:
        module = "org.elasticsearch.telemetry.apm" if realm == "apm" else ""
        extensions = (
            "x-pack-esql,workload-identity" if realm == "esql-datasource-gcs" else ""
        )
        rows.extend(
            [
                f"REALM\t{realm}\tconsumer.Plugin\t{module}\t{extensions}\t"
                + ("a" * 64),
                f"POLICY\t{realm}\t" + ("b" * 64),
            ]
        )
        for artifact in q.TRIO:
            name = f"opentelemetry-{artifact}-1.67.0.jar"
            rows.extend(
                [
                    f"JAR\t{realm}\t{name}\t123\t" + pins[name]["sha256"],
                    f"MODULE\t{realm}\t{name}\tio.opentelemetry.{artifact}\ttrue\t1.67.0",
                ]
            )
        rows.append(f"GRAPH\t{realm}\t{module}\t{extensions}\tfalse\t" + ("a" * 64))
    for extension in ("x-pack-esql", "workload-identity"):
        rows.append(f"GRAPH\t{extension}\t\t\ttrue\t" + ("c" * 64))
    rows.extend(
        [
            "LOADER\telasticsearch-9.5.5.jar\t" + ("d" * 64) + "\t" + ("e" * 64),
            "STATUS\tinventory-only\treplacement=null\truntime_approved=false",
        ]
    )
    return "\n".join(rows) + "\n"


class MetadataGuards(unittest.TestCase):
    def test_separate_realms_accept_same_named_api_without_flattening(self):
        result = q.audit_rows(inventory_fixture())
        self.assertEqual(set(result["realms"]), set(q.REALMS))
        self.assertEqual(result["java_feature"], 25)
        self.assertEqual(
            result["realms"]["esql-datasource-gcs"]["extended_plugins"],
            ["x-pack-esql", "workload-identity"],
        )
        self.assertIsNone(result["replacement"])
        self.assertFalse(result["runtime_approved"])

    def test_truncated_inventory_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "incomplete"):
            q.audit_rows(inventory_fixture().rsplit("STATUS", 1)[0])

    def test_duplicate_jar_in_same_realm_is_rejected(self):
        text = inventory_fixture()
        row = next(row for row in text.splitlines() if row.startswith("JAR"))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            q.audit_rows(text.replace(row, row + "\n" + row))

    def test_module_name_collision_is_rejected_per_realm(self):
        with self.assertRaisesRegex(ValueError, "duplicate JPMS"):
            q.audit_rows(
                inventory_fixture().replace(
                    "io.opentelemetry.context", "io.opentelemetry.api"
                )
            )

    def test_missing_extension_boundary_is_not_declared_closed(self):
        text = "\n".join(
            x
            for x in inventory_fixture().splitlines()
            if not x.startswith("GRAPH\tworkload-identity")
        )
        with self.assertRaisesRegex(ValueError, "unresolved extension"):
            q.audit_rows(text)

    def test_current_api_bytes_must_match_existing_official_pin(self):
        text = inventory_fixture()
        pin = json.loads((HERE / "reusable-official-pins.json").read_text())["files"]
        digest = next(
            p["sha256"] for p in pin if p["file"] == "opentelemetry-api-1.67.0.jar"
        )
        with self.assertRaisesRegex(ValueError, "API trio input mismatch"):
            q.audit_rows(text.replace(digest, "0" * 64, 1))

    def test_sdk_selection_refuses_unobserved_and_never_selects_exporters(self):
        data = q.audit_rows(inventory_fixture())
        with self.assertRaisesRegex(ValueError, "unobserved SDK"):
            q.sdk_experiment(data)
        for artifact in q.SDK:
            data["realms"]["apm"]["jars"][f"opentelemetry-{artifact}-1.62.0.jar"] = {
                "sha256": "0" * 64
            }
        selected = q.sdk_experiment(data)
        self.assertEqual(len(selected), 6)
        self.assertFalse(
            any("exporter" in name or "incubator" in name for name in selected)
        )

    def test_official_exporter_metadata_flags_okhttp_closure_change(self):
        data = json.loads((HERE / "exporter-pom-observation.json").read_text())
        sender = next(x for x in data["files"] if "sender-okhttp" in x["coordinate"])
        dependency = next(
            x for x in sender["dependencies"] if x["artifactId"] == "okhttp-jvm"
        )
        self.assertEqual(dependency["version"], "5.5.0")
        self.assertIsNone(data["replacement"])
        self.assertFalse(data["runtime_approved"])


class RuntimeAndModelGuards(unittest.TestCase):
    def test_command_has_finite_resources_network_and_readonly_inputs(self):
        cmd = r.command("cnc-es-otel-inventory-test", HERE)
        for option, value in [
            ("--memory", "512m"),
            ("--memory-swap", "512m"),
            ("--cpus", "1"),
            ("--network", "none"),
            ("--cap-drop", "ALL"),
            ("--user", "1000:1000"),
        ]:
            self.assertEqual(cmd[cmd.index(option) + 1], value)
        self.assertIn("--read-only", cmd)
        self.assertIn("--pull=never", cmd)
        self.assertIn("-Xmx256m", cmd)
        self.assertIn("-XX:MaxMetaspaceSize=96m", cmd)
        self.assertIn("-XX:MaxDirectMemorySize=32m", cmd)
        self.assertTrue(cmd[cmd.index("--mount") + 1].endswith(",readonly"))
        self.assertEqual(
            cmd[cmd.index("--entrypoint") + 1], "/usr/share/elasticsearch/jdk/bin/java"
        )
        self.assertNotIn("elasticsearch", cmd)
        self.assertEqual(cmd[-1], "/usr/share/elasticsearch")

    def test_missing_provider_negative_control_detects_real_reference(self):
        key = ("method", "method", "()V")
        old = {"io/opentelemetry/Api": {"members": {key: 1}, "parents": []}}
        refs = [
            ("actual.Consumer", ("io/opentelemetry/Api", "method", "()V", "method"))
        ]
        broken = q.s.newly_broken(old, {}, refs)
        self.assertEqual(len(broken), 1)
        with self.assertRaisesRegex(ValueError, "no actual"):
            q.s.newly_broken(old, {}, [])

    def test_model_uses_explicit_runtime_feature_for_multi_release(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "fixture.jar"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr(
                    "META-INF/MANIFEST.MF",
                    "Manifest-Version: 1.0\nMulti-Release: true\n",
                )
                archive.writestr("test/A.class", b"base")
                archive.writestr("META-INF/versions/25/test/A.class", b"java25")
                archive.writestr("META-INF/versions/26/test/A.class", b"future")
            original = q.s.parse
            q.s.parse = lambda data: data
            try:
                self.assertEqual(
                    list(q.s.classes(path, 25)), [("test/A.class", b"java25")]
                )
                self.assertEqual(
                    list(q.s.classes(path, 21)), [("test/A.class", b"base")]
                )
            finally:
                q.s.parse = original

    def test_actual_extracted_file_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "input"
            path.write_bytes(b"fixture")
            link = Path(temp) / "link"
            link.symlink_to(path)
            with self.assertRaisesRegex(ValueError, "linked"):
                q.safe_file(link)


class NextPhaseGuards(unittest.TestCase):
    def test_extension_closure_preserves_graph_and_rejects_cycles(self):
        seal = load("seal_inventory")
        graph = {
            "leaf": {"extended_plugins": ["parent"]},
            "parent": {"extended_plugins": []},
        }
        self.assertEqual(seal.closure(graph, ["leaf"]), ["leaf", "parent"])
        graph["parent"]["extended_plugins"] = ["leaf"]
        with self.assertRaisesRegex(ValueError, "cycle"):
            seal.closure(graph, ["leaf"])

    def test_official_root_POMs_have_exact_bytes_and_only_six_changes(self):
        result = load("published_metadata").verify()
        self.assertEqual(result["root_poms"], 27)
        self.assertEqual(len(result["changed_roots"]), 6)
        self.assertFalse(result["real_maven_oracle_executed"])
        self.assertIsNone(result["replacement"])

    def test_published_exclusions_are_structured_and_retained(self):
        model = json.loads((HERE / "published-roots.json").read_text())
        p = next(
            x
            for x in model["files"]
            if "opentelemetry-instrumentation-api-incubator:" in x["coordinate"]
        )
        self.assertTrue(
            any(
                isinstance(d.get("exclusions"), list) and d["exclusions"]
                for d in p["dependencies"]
            )
        )

    def test_next_stage_uses_ES_image_and_preserves_resource_guards(self):
        plan = load("next_phase")
        cmd = plan.stage_command()
        self.assertIn(q.IMAGE, cmd)
        self.assertIn("/tools/StageInputs.java", cmd)
        self.assertEqual(cmd[-1], "/proof/input")
        self.assertIn("--read-only", cmd)
        self.assertEqual(cmd[cmd.index("--memory") + 1], "512m")
        self.assertEqual(cmd[cmd.index("--memory-swap") + 1], "512m")
        self.assertEqual(cmd[cmd.index("--network") + 1], "none")

    def test_loader_uses_actual_ES_implementation_and_keeps_candidate_overlay_scoped(
        self,
    ):
        plan = load("next_phase")
        current = plan.loader_command("current")
        fixed = plan.loader_command("sdk-six")
        self.assertIn("--module-path", current)
        self.assertIn("/usr/share/elasticsearch/lib", current)
        self.assertIn("/tools/EsLoaderProbe.java", current)
        mounts = [fixed[i + 1] for i, x in enumerate(fixed) if x == "--mount"]
        self.assertEqual(len(mounts), 2)
        self.assertTrue(all(m.endswith(",readonly") for m in mounts))
        self.assertIn("dst=/usr/share/elasticsearch/modules/apm,readonly", mounts[-1])
        with self.assertRaisesRegex(ValueError, "unknown"):
            plan.loader_command("all-exporters")

    def test_static_paths_keep_SPI_export_boundary_and_boot_parent_priority(self):
        static = load("static_stage")
        graph = {
            "child": {"extended_plugins": ["parent"], "spi": False},
            "parent": {"extended_plugins": ["ancestor"], "spi": True},
            "ancestor": {"extended_plugins": [], "spi": False},
        }
        files = {
            "lib/server.jar": {},
            "modules/child/child.jar": {},
            "modules/parent/private.jar": {},
            "modules/parent/spi/api.jar": {},
            "modules/ancestor/full.jar": {},
        }
        self.assertEqual(
            static.visible_paths("child", graph, files),
            [
                "lib/server.jar",
                "modules/ancestor/full.jar",
                "modules/parent/spi/api.jar",
                "modules/child/child.jar",
            ],
        )
        graph["ancestor"]["extended_plugins"] = ["child"]
        with self.assertRaisesRegex(ValueError, "cyclic"):
            static.visible_paths("child", graph, files)

    def test_staged_manifest_hashes_and_original_identity_are_not_vacuous(self):
        stage = load("stage_manifest")
        closure = json.loads((HERE / "inventory-result.json").read_text())[
            "required_graph_closure"
        ]
        with tempfile.TemporaryDirectory() as temp:
            tree = Path(temp)
            files = {}
            for realm in closure:
                files[f"modules/{realm}/{realm}.jar"] = realm.encode()
            for realm in q.REALMS:
                files[f"modules/{realm}/plugin-descriptor.properties"] = (
                    b"fixture descriptor"
                )
                files[f"modules/{realm}/entitlement-policy.yaml"] = b"fixture policy"
            files["lib/server.jar"] = b"fixture loader"
            rows = []
            records = {}
            for name, data in files.items():
                path = tree / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
                record = {"sha256": stage.digest(path), "size": len(data)}
                records[name] = record
                rows.append(f"COPY\t{name}\t{len(data)}\t{record['sha256']}")
            rows.append(
                f"STATUS\tstage-only\t{len(files)}\t{sum(len(d) for d in files.values())}\treplacement=null\truntime_approved=false"
            )
            inventory = {
                "realms": {},
                "loader": [
                    ["server.jar", records["lib/server.jar"]["sha256"], "class-hash"]
                ],
            }
            for realm in q.REALMS:
                inventory["realms"][realm] = {
                    "jars": {realm + ".jar": records[f"modules/{realm}/{realm}.jar"]},
                    "descriptor_sha256": records[
                        f"modules/{realm}/plugin-descriptor.properties"
                    ]["sha256"],
                    "entitlement_sha256": records[
                        f"modules/{realm}/entitlement-policy.yaml"
                    ]["sha256"],
                }
            result = stage.verify(inventory, "\n".join(rows), tree)
            self.assertEqual(len(result["module_closure"]), 11)
            (tree / "lib/server.jar").write_bytes(b"mutated loader")
            with self.assertRaisesRegex(ValueError, "hash/size drift"):
                stage.verify(inventory, "\n".join(rows), tree)

    def test_sealed_metadata_does_not_relabel_old_preparation_source(self):
        result = json.loads((HERE / "inventory-result.json").read_text())
        self.assertEqual(result["executed_source_commit"], "89f58fc")
        self.assertEqual(result["java_feature"], 27)
        self.assertFalse(result["runtime_approved"])
        self.assertIn("entitlement operation", result["missing_evidence"])


if __name__ == "__main__":
    unittest.main()
