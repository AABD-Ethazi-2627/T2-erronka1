"""Autonomous scheduling, lifecycle ownership and durable accounting contracts."""

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import httpx
from test_scoring_replay import manifest

from scripts.build_automatic_graph_flow import build
from scripts.build_automatic_graph_flow import main as export_flow
from scripts.platform_io import exclusive_lock
from scripts.run_automatic_graph import (
    accounting,
    check_es,
    cycle,
    load_config,
    worker_arguments,
)
from scripts.run_durable_pipeline import main as worker_main


class AutomaticGraphTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.manifest = self.directory / "manifest.json"
        self.manifest.write_text(json.dumps(manifest()))
        self.config = json.loads(
            (
                Path(__file__).resolve().parents[1]
                / "deploy/cg14/automatic-graph.example.json"
            ).read_bytes()
        )
        self.config.update(
            root=str(self.directory / "worker"), manifest=str(self.manifest)
        )

    def load(self, config):
        path = self.directory / "graph.json"
        path.write_text(json.dumps(config))
        return load_config(path)

    def test_required_destinations_and_closed_config_fail_before_consumption(self):
        self.assertEqual(self.load(self.config), self.config)
        for field, value in (
            ("es_url", ""),
            ("es_index", ""),
            ("manifest", "relative"),
            ("max_records", True),
            ("max_polls", 0),
            ("timeout", float("inf")),
            ("timeout", 0),
            ("max_poll_interval_ms", 1000),
            ("offset_reset", "latest"),
            ("source_kind", "inferred"),
            ("root", "."),
        ):
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                self.load({**self.config, field: value})
        with self.assertRaises(ValueError):
            self.load({**self.config, "ignore_es": True})
        with self.assertRaises(ValueError):
            self.load({k: v for k, v in self.config.items() if k != "es_url"})
        self.assertFalse(Path(self.config["root"]).exists())

    def test_cycle_pins_transport_before_worker_and_preserves_error_then_recovers(self):
        root = Path(self.config["root"])

        def blocked(args):
            self.assertEqual(
                json.loads((root / "automatic-config.json").read_bytes()), self.config
            )
            self.assertIn("--es-url", args)
            self.assertIn("--es-index", args)
            with (
                self.assertRaises(BlockingIOError),
                exclusive_lock(root / "automatic-owner.lock", blocking=False),
            ):
                self.fail("Competing cycle acquired ownership")
            raise RuntimeError("Synthetic destination unavailable")

        with (
            patch("scripts.run_automatic_graph.check_es"),
            patch("scripts.run_automatic_graph.run_worker", side_effect=blocked),
            self.assertRaisesRegex(RuntimeError, "destination unavailable"),
        ):
            cycle(self.config)
        failed = next((root / "automatic-cycles").glob("*.json"))
        before = failed.read_bytes()
        self.assertEqual(json.loads(before)["status"], "blocked")
        with (
            patch("scripts.run_automatic_graph.check_es"),
            patch("scripts.run_automatic_graph.run_worker", return_value=0) as run,
        ):
            self.assertEqual(cycle(self.config), 0)
            run.assert_called_once_with(worker_arguments(self.config))
        self.assertEqual(failed.read_bytes(), before)
        self.assertEqual(len(list((root / "automatic-cycles").glob("*.json"))), 2)
        for field in (
            "topic",
            "group_id",
            "bootstrap_servers",
            "source_namespace",
            "es_index",
        ):
            with (
                self.subTest(field=field),
                patch("scripts.run_automatic_graph.run_worker") as run,
            ):
                with self.assertRaisesRegex(ValueError, "reconciliation"):
                    cycle({**self.config, field: "changed"})
                run.assert_not_called()

    def test_direct_worker_competition_fails_before_constructing_kafka_client(self):
        root = Path(self.config["root"])
        root.mkdir()
        with (
            exclusive_lock(root / "kafka-owner.lock", blocking=False),
            patch("kafka.KafkaConsumer") as consumer,
        ):
            with self.assertRaises(BlockingIOError):
                worker_main(worker_arguments(self.config))
            consumer.assert_not_called()

    def test_accounting_is_readonly_and_does_not_claim_producer_totals(self):
        root = Path(self.config["root"])
        self.assertEqual(
            accounting(root), {"observed": 0, "saved": 0, "rejected": 0, "pending": 0}
        )
        self.assertFalse(root.exists())
        root.mkdir()
        with closing(sqlite3.connect(root / "pipeline.sqlite3")) as con:
            con.execute("CREATE TABLE jobs (id TEXT, outcome TEXT)")
            con.executemany(
                "INSERT INTO jobs VALUES (?, ?)",
                [("1", "completed"), ("2", "rejected"), ("3", None)],
            )
            con.commit()
        before = (root / "pipeline.sqlite3").read_bytes()
        self.assertEqual(
            accounting(root), {"observed": 3, "saved": 1, "rejected": 1, "pending": 1}
        )
        self.assertEqual((root / "pipeline.sqlite3").read_bytes(), before)

    def test_es_setup_preflight_rejects_missing_guard_or_weak_mapping(self):
        from scripts.build_es_ingest_pipeline import EXPORT, PIPELINE_ID

        index = self.config["es_index"]
        for fault in (None, "settings", "pipeline", "mapping", "missing", "metadata"):

            def response(request, fault=fault):
                if fault == "missing":
                    return httpx.Response(404, json={"error": "missing index"})
                if request.url.path.endswith("/_settings"):
                    name = "_none" if fault == "settings" else PIPELINE_ID
                    body = {index: {"settings": {"index": {"final_pipeline": name}}}}
                elif "/_ingest/" in request.url.path:
                    body = {
                        PIPELINE_ID: {}
                        if fault == "pipeline"
                        else {
                            **json.loads(EXPORT.read_bytes()),
                            "created_date_millis": True if fault == "metadata" else 1,
                            "modified_date_millis": 2,
                        }
                    }
                else:
                    body = {
                        index: {
                            "mappings": {
                                "dynamic": "true" if fault == "mapping" else "strict"
                            }
                        }
                    }
                return httpx.Response(200, json=body)

            client = httpx.Client(transport=httpx.MockTransport(response))
            with (
                self.subTest(fault=fault),
                patch("scripts.run_automatic_graph.httpx.Client", return_value=client),
            ):
                if fault is None:
                    check_es(self.config)
                else:
                    with self.assertRaises((ValueError, httpx.HTTPStatusError)):
                        check_es(self.config)
        for error in (ValueError("missing guard"), httpx.ConnectError("ES down")):
            with (
                patch("scripts.run_automatic_graph.check_es", side_effect=error),
                patch("scripts.run_automatic_graph.run_worker") as run,
                self.assertRaises(type(error)),
            ):
                cycle(self.config)
            run.assert_not_called()

    def test_kafka_lifetime_lock_covers_close_and_is_released_after_cycle(self):
        root = Path(self.config["root"])

        def running(*args, **kwargs):
            with (
                self.assertRaises(BlockingIOError),
                exclusive_lock(root / "kafka-owner.lock", blocking=False),
            ):
                self.fail("Owner lock released while consumer is active")
            # The adapter owns close in its finally; this callback stands for
            # that entire lifecycle, including its explicit non-auto close.

        with (
            patch("kafka.KafkaConsumer") as consumer,
            patch("scripts.kafka_archive.run", side_effect=running),
        ):
            self.assertEqual(worker_main(worker_arguments(self.config)), 0)
            self.assertFalse(consumer.call_args.kwargs["enable_auto_commit"])
            self.assertFalse(consumer.call_args.kwargs["allow_auto_create_topics"])
        with exclusive_lock(root / "kafka-owner.lock", blocking=False):
            pass

    def test_export_has_automatic_source_and_retains_failures(
        self,
    ):
        flow = build()["flowContents"]
        self.assertEqual(
            json.loads(
                (
                    Path(__file__).resolve().parents[1]
                    / "nifi-flows/cg14_automatic_graph_nifi_2.12.0.json"
                ).read_bytes()
            ),
            build(),
        )
        processors = flow["processors"]
        contract = json.loads(
            (
                Path(__file__).parent / "fixtures/nifi-2.12-automatic-components.json"
            ).read_bytes()
        )["components"]
        for processor in processors:
            observed = contract[processor["type"]]
            self.assertEqual(processor["bundle"], observed["bundle"])
            routed = {
                relationship
                for connection in flow["connections"]
                if connection["source"]["id"] == processor["identifier"]
                for relationship in connection["selectedRelationships"]
            }
            self.assertEqual(
                routed | set(processor["autoTerminatedRelationships"]),
                set(observed["relationships"]),
            )
        self.assertTrue(all(p["scheduledState"] == "DISABLED" for p in processors))
        self.assertTrue(
            all(p["concurrentlySchedulableTaskCount"] == 1 for p in processors)
        )
        self.assertFalse(flow["inputPorts"])
        self.assertFalse(any("ConsumeKafka" in p["type"] for p in processors))
        execute = next(p for p in processors if p["name"] == "Single Kafka owner")
        self.assertIn(
            "scripts.run_automatic_graph", execute["properties"]["Command Arguments"]
        )
        self.assertEqual(execute["properties"]["TMPDIR"], "#{PROCESS_TEMP}")
        self.assertFalse(execute["autoTerminatedRelationships"])
        self.assertEqual(
            {
                c["selectedRelationships"][0]
                for c in flow["connections"]
                if c["source"]["id"] == execute["identifier"]
            },
            {"original", "output stream", "nonzero status"},
        )
        self.assertTrue(
            all(c["flowFileExpiration"] == "0 sec" for c in flow["connections"])
        )
        path = self.directory / "flow.json"
        export_flow(["--output", str(path)])
        self.assertEqual(json.loads(path.read_bytes()), build())
        with self.assertRaises(FileExistsError):
            export_flow(["--output", str(path)])


if __name__ == "__main__":
    unittest.main()
