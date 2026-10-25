"""Safe NiFi migration and a historical template that cannot start by default."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.build_refreshed_lab_flow import build
from scripts.check_lab_compose import render
from scripts.check_repository_layout import check as check_layout
from scripts.image_inventory import check, read_images

ROOT = Path(__file__).resolve().parents[1]


class InfrastructureRefreshTests(unittest.TestCase):
    def test_layout_checker_accepts_continued_build_instructions(self):
        self.assertEqual(check_layout(), [])

    def test_active_pin_drift_and_floating_images_are_rejected(self):
        self.assertEqual(check(), [])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in (
                "deploy/images.json",
                "deploy/build-targets.json",
                "deploy/images/elasticsearch.Dockerfile",
                "deploy/images/filebeat.Dockerfile",
                "deploy/images/kafka.Dockerfile",
                "deploy/images/kibana.Dockerfile",
                "deploy/images/mock-python.Dockerfile",
                "deploy/images/nifi.Dockerfile",
                "deploy/images/python.Dockerfile",
                "deploy/images/wolfi-base.Dockerfile",
                "docker-compose.yml",
                "deploy/cg14/compose.yaml",
                "scoring/Dockerfile",
            ):
                destination = root / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, destination)
            nifi = root / "deploy/images/nifi.Dockerfile"
            nifi.write_text(
                nifi.read_text().replace(read_images()["nifi"], "apache/nifi:2.0.0")
            )
            self.assertTrue(any("nifi" in error for error in check(root)))
            inventory = root / "deploy/images.json"
            images = read_images(root)
            images["nifi"] = "apache/nifi:2.12.0"
            inventory.write_text(json.dumps(images))
            with self.assertRaisesRegex(ValueError, "digest"):
                read_images(root)

    def test_new_lan_and_cg32_images_are_in_the_scan_matrix(self):
        images = read_images()
        self.assertIn("haproxy", images)
        self.assertIn("wolfi", images)
        workflow = (ROOT / ".github/workflows/dependencies.yml").read_text()
        self.assertIn("uv, go, haproxy, wolfi", workflow)
        self.assertIn("exit-code: '0'", workflow)
        self.assertIn("scripts.enforce_image_scan", workflow)
        self.assertIn("ignore-unfixed: false", workflow)

    def test_retarget_preserves_routing_and_properties_but_disables_execution(self):
        old = json.loads((ROOT / "nifi-flows/cnc_lab_completed.json").read_text())
        refreshed = build()
        source, target = old["flowContents"], refreshed["flowContents"]
        self.assertEqual(source["connections"], target["connections"])
        for key in ("processors", "controllerServices"):
            self.assertEqual(len(source[key]), len(target[key]))
            for original, updated in zip(source[key], target[key], strict=True):
                self.assertEqual(original["identifier"], updated["identifier"])
                self.assertEqual(updated["scheduledState"], "DISABLED")
                self.assertEqual(updated["bundle"]["version"], "2.12.0")
        processors = {p["name"]: p for p in target["processors"]}
        services = {p["name"]: p for p in target["controllerServices"]}
        self.assertEqual(
            processors["RetryFlowFile"]["properties"]["Maximum Retries"], "2"
        )
        self.assertEqual(
            processors["PutElasticsearchJson"]["properties"]["Client Service"],
            source["controllerServices"][0]["identifier"],
        )
        self.assertEqual(
            processors["ExecuteGroovyScript"]["properties"]["Script Body"],
            next(p for p in source["processors"] if p["name"] == "ExecuteGroovyScript")[
                "properties"
            ]["groovyx-script-body"],
        )
        self.assertEqual(
            services["Elasticsearch local lab"]["properties"]["HTTP Hosts"],
            "http://elasticsearch:9200",
        )
        self.assertEqual(
            services["Elasticsearch local lab"]["properties"]["Authorization Scheme"],
            "NONE",
        )
        self.assertEqual(
            services["Elasticsearch local lab"]["properties"]["Connect Timeout"], "5000"
        )
        self.assertEqual(
            services["Elasticsearch local lab"]["properties"]["Read Timeout"], "60000"
        )
        self.assertEqual(
            services["CSVReader"]["properties"]["Treat First Line as Header"], "false"
        )
        self.assertEqual(
            services["JsonRecordSetWriter"]["properties"]["Output Grouping"],
            "output-array",
        )
        self.assertEqual(
            old["flowContents"]["processors"][0]["scheduledState"], "ENABLED"
        )
        self.assertEqual(
            refreshed,
            json.loads(
                (ROOT / "nifi-flows/cnc_lab_completed_nifi_2.12.0.json").read_text()
            ),
        )

    def test_historical_template_has_no_default_service_to_start(self):
        result = render(archive=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["services"], {})
        archive = render(archive=True)
        self.assertEqual(archive.returncode, 0, archive.stderr)
        self.assertEqual(len(json.loads(archive.stdout)["services"]), 6)
