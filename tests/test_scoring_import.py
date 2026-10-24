"""Synthetic historical bytes, offline transactions and unchanged API conflicts."""

import copy
import hashlib
import io
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing, redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from api_client import api_client
from fastapi.responses import JSONResponse
from test_scoring_replay import AnomalyDouble, RiskDouble, manifest

from scoring.response_ledger import InferenceConflict, canonical, response
from scoring.score_api import Telemetry, create_app
from scripts.archive_consumer import consume
from scripts.import_scoring_responses import VERSION, digest, main, migrate, prepare
from scripts.validate_contracts import contract_hashes, validators

ROOT = Path(__file__).resolve().parents[1]


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.ledger = self.root / "responses.sqlite3"
        self.config = manifest()
        self.target = self.root / "configuration.json"
        self.target.write_text(canonical(self.config), encoding="utf-8")
        self.event = json.loads(
            (ROOT / "contracts/examples/valid/telemetry.json").read_text()
        )
        self.event["source"] = {
            "kind": "lab_fixture",
            "uri": "synthetic://import/é",
            "record_ref": "row-1",
        }
        self.event = Telemetry.model_validate(self.event).model_dump()
        self.prediction = {
            **self.event,
            "scored_at": "2020-01-02T03:04:05.123Z",
            "failure_score": 0.8,
            "risk_alert": True,
            "alert_level": "CRITICA",
            "anomaly_score": 0.5,
            "anomaly_alert": True,
            **{
                k: self.config[k]
                for k in (
                    "model_version",
                    "policy",
                    "risk_threshold",
                    "anomaly_threshold",
                    "prediction_scope",
                    "temporal_prediction_enabled",
                    "score_semantics",
                )
            },
            "model_artifact_sha256": self.config["files"]["rf.pkl"],
        }
        # Retain unusual whitespace, original order, UTF-8 and a trailing LF.
        self.body = (
            json.dumps(self.prediction, indent=2, ensure_ascii=False) + "\n"
        ).encode()
        self.bundle = {
            "version": VERSION,
            "configuration": self.config,
            "configuration_evidence": "synthetic://configuration/original",
            "contracts": contract_hashes(),
            "entries": [self.entry("one", self.event, self.body)],
        }
        self.bundle_path = self.root / "bundle.json"

    def entry(self, name, event, body):
        raw = canonical(event).encode()
        (self.root / (name + "-telemetry.json")).write_bytes(raw)
        (self.root / (name + "-response.json")).write_bytes(body)
        return {
            "telemetry": {"file": name + "-telemetry.json", "sha256": digest(raw)},
            "response": {"file": name + "-response.json", "sha256": digest(body)},
            "identity_evidence": [
                {
                    "system": system,
                    "event_id": event["event_id"],
                    "reference": "synthetic://" + system + "/row-1",
                }
                for system in ("cg14", "filebeat")
            ],
        }

    def prepared(self):
        self.bundle_path.write_text(canonical(self.bundle), encoding="utf-8")
        return prepare(
            self.bundle_path, digest(self.bundle_path.read_bytes()), self.target
        )

    def initialized(self):
        rows = self.prepared()
        migrate(self.ledger, rows, apply=True, create=True)
        return rows

    def snapshot(self):
        with closing(sqlite3.connect(self.ledger)) as con:
            return list(con.iterdump())

    def cli(self, *options, process=False):
        self.bundle_path.write_text(canonical(self.bundle), encoding="utf-8")
        arguments = [
            str(self.bundle_path),
            "--bundle-sha256",
            digest(self.bundle_path.read_bytes()),
            "--configuration",
            str(self.target),
            "--ledger",
            str(self.ledger),
            *options,
        ]
        if not process:
            stdout, stderr = io.StringIO(), io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = main(arguments)
            return subprocess.CompletedProcess(
                arguments, code, stdout.getvalue(), stderr.getvalue()
            )
        return subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "scripts.import_scoring_responses",
                *arguments,
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=45,
        )

    def test_default_validation_has_no_target_or_backup_writes(self):
        result = self.cli(process=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["mode"], "validate")
        self.assertFalse(self.ledger.exists())
        self.assertNotEqual(self.cli("--import").returncode, 0)
        self.assertFalse(self.ledger.exists())
        self.assertEqual(
            self.cli("--import", "--create-ledger", process=True).returncode, 0
        )
        before = self.ledger.read_bytes()
        self.assertEqual(self.cli("--dry-run").returncode, 0)
        self.assertEqual(self.ledger.read_bytes(), before)
        repeated = self.cli("--import")
        self.assertEqual(repeated.returncode, 0, repeated.stderr)
        self.assertEqual(json.loads(repeated.stdout)["duplicate"], 1)
        self.assertEqual(self.ledger.read_bytes(), before)

    def test_requires_backup_and_preserves_original_database(self):
        first = self.initialized()
        original = self.snapshot()
        event = {**self.event, "event_id": "f" * 64}
        body = canonical({**self.prediction, "event_id": event["event_id"]}).encode()
        self.bundle["entries"] = [self.entry("two", event, body)]
        rows = self.prepared()
        with self.assertRaisesRegex(ValueError, "backup"):
            migrate(self.ledger, rows, apply=True)
        self.assertEqual(self.snapshot(), original)
        occupied = self.root / "occupied-backup"
        occupied.write_bytes(b"preserve")
        with self.assertRaises(FileExistsError):
            migrate(self.ledger, rows, apply=True, backup=occupied)
        self.assertEqual(occupied.read_bytes(), b"preserve")
        self.assertEqual(self.snapshot(), original)
        backup = self.root / "before.sqlite3"
        migrate(self.ledger, rows, apply=True, backup=backup)
        with closing(sqlite3.connect(backup)) as con:
            self.assertEqual(list(con.iterdump()), original)
        self.assertEqual(migrate(self.ledger, first)["duplicate"], 1)
        self.assertEqual(
            migrate(self.ledger, rows, apply=True, backup=backup)["duplicate"], 1
        )

    def test_existing_api_response_cannot_be_replaced_by_other_wire_bytes(self):
        validate = validators(ROOT / "contracts")["prediction"].validate
        response(
            self.ledger, self.event, self.config, lambda: self.prediction, validate
        )
        with closing(sqlite3.connect(self.ledger)) as con, con:
            con.execute("DROP TABLE scoring_imports")  # Pre-import ledger schema.
        before = self.snapshot()
        with self.assertRaisesRegex(InferenceConflict, "wire bytes"):
            migrate(
                self.ledger, self.prepared(), apply=True, backup=self.root / "backup"
            )
        self.assertEqual(self.snapshot(), before)
        self.assertFalse((self.root / "backup").exists())
        self.body = JSONResponse(json.loads(canonical(self.prediction))).body
        self.bundle["entries"] = [self.entry("one", self.event, self.body)]
        self.assertEqual(
            migrate(
                self.ledger, self.prepared(), apply=True, backup=self.root / "backup"
            )["importable"],
            1,
        )

    def test_malformed_missing_incompatible_and_retargeted_inputs_fail_closed(self):
        original = copy.deepcopy(self.bundle)
        cases = [
            lambda b: b.update(unknown=True),
            lambda b: b.update(contracts={}),
            lambda b: b.update(entries=[]),
            lambda b: b["configuration"].pop("versions"),
            lambda b: b["configuration"].update(risk_threshold=True),
            lambda b: b["configuration"].update(policy="new"),
            lambda b: b["entries"][0]["response"].update(sha256="0" * 64),
            lambda b: b["entries"][0]["telemetry"].update(file="../escape.json"),
            lambda b: b["entries"][0].update(identity_evidence=[]),
            lambda b: b["entries"][0]["identity_evidence"][0].update(event_id="e" * 64),
        ]
        for change in cases:
            with self.subTest(change=cases.index(change)):
                self.bundle = copy.deepcopy(original)
                change(self.bundle)
                self.assertNotEqual(self.cli().returncode, 0)
                self.assertFalse(self.ledger.exists())
        self.bundle = original
        for change in (
            {"scored_at": "absent"},
            {"machine_id": "CNC-999"},
            {"risk_threshold": 0.9},
            {"model_artifact_sha256": "c" * 64},
            {"risk_alert": False},
            {"machine_failure": 1},
        ):
            with self.subTest(change=change):
                self.bundle["entries"] = [
                    self.entry(
                        "bad",
                        self.event,
                        canonical({**self.prediction, **change}).encode(),
                    )
                ]
                self.assertNotEqual(self.cli().returncode, 0)
                self.assertFalse(self.ledger.exists())

    def test_duplicate_keys_nonfinite_deep_and_oversized_snapshots_are_rejected(self):
        for body in (
            b'{"x":1,"x":2}',
            b'{"x":NaN}',
            b'{"x":1e999}',
            b"[" * 65 + b"0" + b"]" * 65,
            b" " * 32769,
            b"\xff",
        ):
            with self.subTest(body=body[:15]):
                self.bundle["entries"] = [self.entry("bad", self.event, body)]
                self.assertNotEqual(self.cli().returncode, 0)

    def test_conflicts_inside_batch_and_existing_ledger_leave_no_rows(self):
        rows = self.initialized()
        before = self.snapshot()
        changed = {**self.prediction, "scored_at": "2020-01-03T00:00:00Z"}
        self.bundle["entries"].append(
            self.entry("conflict", self.event, canonical(changed).encode())
        )
        with self.assertRaises(InferenceConflict):
            self.prepared()
        self.bundle["entries"] = [self.bundle["entries"][-1]]
        with self.assertRaises(InferenceConflict):
            migrate(
                self.ledger, self.prepared(), apply=True, backup=self.root / "backup"
            )
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(migrate(self.ledger, rows)["duplicate"], 1)

    def test_mid_batch_error_and_commit_failure_roll_back_all_rows(self):
        self.initialized()
        before = self.snapshot()
        self.bundle["entries"] = []
        for number in (1, 2):
            event = {**self.event, "event_id": str(number) * 64}
            self.bundle["entries"].append(
                self.entry(
                    str(number),
                    event,
                    canonical(
                        {**self.prediction, "event_id": event["event_id"]}
                    ).encode(),
                )
            )
        rows = self.prepared()

        def fail(stage):
            raise sqlite3.OperationalError("synthetic insert failure")

        with self.assertRaises(sqlite3.OperationalError):
            migrate(
                self.ledger,
                rows,
                apply=True,
                backup=self.root / "before-insert",
                checkpoint=fail,
            )
        self.assertEqual(self.snapshot(), before)

        class FailedCommit(sqlite3.Connection):
            def commit(self):
                raise sqlite3.OperationalError("synthetic commit failure")

        real_connect = sqlite3.connect

        def connect(*args, **kwargs):
            return real_connect(*args, **kwargs, factory=FailedCommit)

        with (
            patch(
                "scripts.import_scoring_responses.sqlite3.connect", side_effect=connect
            ),
            self.assertRaises(sqlite3.OperationalError),
        ):
            migrate(self.ledger, rows, apply=True, backup=self.root / "before-commit")
        self.assertEqual(self.snapshot(), before)

    def test_killed_import_recovers_atomic_original_and_retry_is_idempotent(self):
        self.initialized()
        before = self.snapshot()
        event = {**self.event, "event_id": "e" * 64}
        self.bundle["entries"] = [
            self.entry(
                "crash",
                event,
                canonical({**self.prediction, "event_id": event["event_id"]}).encode(),
            )
        ]
        self.prepared()
        child = """
import os,sys
from pathlib import Path
from scripts.import_scoring_responses import digest,prepare,migrate
bundle,config,ledger,backup=map(Path,sys.argv[1:])
rows=prepare(bundle,digest(bundle.read_bytes()),config)
migrate(ledger,rows,apply=True,backup=backup,checkpoint=lambda stage:os._exit(73))
"""
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                "-c",
                child,
                str(self.bundle_path),
                str(self.target),
                str(self.ledger),
                str(self.root / "before-crash"),
            ],
            cwd=ROOT,
            capture_output=True,
            check=False,
            timeout=45,
        )
        self.assertEqual(result.returncode, 73, result.stderr)
        with self.assertRaisesRegex(ValueError, "sidecar"):
            migrate(self.ledger, self.prepared())
        rows = self.prepared()
        migrate(self.ledger, rows, apply=True, backup=self.root / "retry-backup")
        # Explicit import permits SQLite's own journal recovery before backup.
        with closing(sqlite3.connect(self.root / "retry-backup")) as con:
            self.assertEqual(list(con.iterdump()), before)
        self.assertEqual(migrate(self.ledger, rows, apply=True)["duplicate"], 1)

    def test_ledger_corruption_sidecars_and_wrong_schema_are_rejected(self):
        rows = self.prepared()
        self.ledger.write_bytes(b"not sqlite")
        self.assertNotEqual(self.cli().returncode, 0)
        self.ledger.unlink()
        with closing(sqlite3.connect(self.ledger)) as con:
            con.execute("CREATE TABLE unrelated (x)")
            con.commit()
        with self.assertRaisesRegex(ValueError, "schema"):
            migrate(self.ledger, rows)
        sidecar = Path(str(self.ledger) + "-wal")
        sidecar.write_bytes(b"synthetic")
        with self.assertRaisesRegex(ValueError, "sidecar"):
            migrate(self.ledger, rows)

    def test_batch_duplicate_and_backup_restoration(self):
        self.bundle["entries"] *= 2
        rows = self.initialized()
        self.assertEqual(len(rows), 1)
        before = self.snapshot()
        self.bundle["entries"] = [
            self.entry(
                "new",
                {**self.event, "event_id": "e" * 64},
                canonical({**self.prediction, "event_id": "e" * 64}).encode(),
            )
        ]
        new = self.prepared()
        backup = self.root / "restore-source.sqlite3"
        migrate(self.ledger, new, apply=True, backup=backup)
        restored = self.root / "restored.sqlite3"
        restored.write_bytes(backup.read_bytes())
        with closing(sqlite3.connect(restored)) as con:
            self.assertEqual(list(con.iterdump()), before)
        self.assertEqual(migrate(restored, rows)["duplicate"], 1)
        self.assertEqual(migrate(restored, new)["importable"], 1)

    def test_wal_mode_is_rejected_without_creating_sidecars(self):
        rows = self.prepared()
        with closing(sqlite3.connect(self.ledger)) as con:
            self.assertEqual(
                con.execute("PRAGMA journal_mode=WAL").fetchone(), ("wal",)
            )
        before = self.ledger.read_bytes()
        with self.assertRaisesRegex(ValueError, "WAL mode"):
            migrate(self.ledger, rows)
        self.assertEqual(self.ledger.read_bytes(), before)
        self.assertFalse(Path(str(self.ledger) + "-wal").exists())

    def test_target_configuration_and_existing_event_conflicts_are_atomic(self):
        self.initialized()
        before = self.snapshot()
        self.target.write_text(canonical({**self.config, "metadata": "changed"}))
        self.assertNotEqual(self.cli().returncode, 0)
        self.target.write_text(canonical(self.config))
        event = {**self.event, "rpm": 999.0}
        self.bundle["entries"] = [
            self.entry(
                "changed", event, canonical({**self.prediction, "rpm": 999.0}).encode()
            )
        ]
        rows = self.prepared()
        with self.assertRaisesRegex(InferenceConflict, "event identity"):
            migrate(self.ledger, rows, apply=True, backup=self.root / "unused")
        self.assertEqual(self.snapshot(), before)
        self.assertFalse((self.root / "unused").exists())


class ImportAPITests(unittest.IsolatedAsyncioTestCase):
    async def test_corrupt_bytes_and_orphan_binding_never_rescore(self):
        fixture = ImportTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.initialized()
        app = create_app(fixture.root / "absent.json", ledger_path=fixture.ledger)
        async with api_client(app) as client:
            risk = RiskDouble()
            app.state.models = {"rf.pkl": risk, "if.pkl": AnomalyDouble()}
            app.state.manifest = fixture.config
            with closing(sqlite3.connect(fixture.ledger)) as con, con:
                con.execute("UPDATE scoring_imports SET body=?", (fixture.body + b" ",))
            with patch("scoring.score_api.log"):
                self.assertEqual(
                    (await client.post("/predict", json=fixture.event)).status_code, 500
                )
            with closing(sqlite3.connect(fixture.ledger)) as con, con:
                con.execute("UPDATE scoring_imports SET body=?", (fixture.body,))
                con.execute("DELETE FROM scoring_responses")
            with patch("scoring.score_api.log"):
                self.assertEqual(
                    (await client.post("/predict", json=fixture.event)).status_code, 500
                )
            self.assertEqual(risk.calls, 0)

    async def test_original_wire_bytes_restart_conflicts_and_archive_ack(self):
        fixture = ImportTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.initialized()
        original_inputs = {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in fixture.root.glob("*.json")
        }
        for _ in range(2):
            app = create_app(fixture.root / "absent.json", ledger_path=fixture.ledger)
            async with api_client(app) as client:
                self.assertEqual(
                    (await client.post("/predict", json=fixture.event)).status_code, 503
                )
                risk = RiskDouble()
                app.state.models = {"rf.pkl": risk, "if.pkl": AnomalyDouble()}
                app.state.manifest = fixture.config
                replay = await client.post("/predict", json=fixture.event)
                self.assertEqual(replay.status_code, 200, replay.text)
                self.assertEqual(replay.content, fixture.body)
                self.assertEqual(
                    replay.json()["scored_at"], fixture.prediction["scored_at"]
                )
                self.assertIn("x-cnc-manifest-sha256", replay.headers)
                conflict = await client.post(
                    "/predict", json={**fixture.event, "rpm": 1600}
                )
                self.assertEqual(conflict.status_code, 409)
                app.state.manifest = {**fixture.config, "anomaly_threshold": 0.2}
                self.assertEqual(
                    (await client.post("/predict", json=fixture.event)).status_code, 409
                )
                self.assertEqual(risk.calls, 0)
        ack = []
        archive = fixture.root / "archive"
        consume(
            archive, [("old", "prediction", fixture.body)], lambda: ack.append(True)
        )
        stats = consume(
            archive, [("retry", "prediction", replay.content)], lambda: ack.append(True)
        )
        self.assertEqual((stats["duplicate"], stats["rejected"]), (1, 0))
        self.assertEqual(ack, [True, True])
        self.assertEqual(
            {
                p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in fixture.root.glob("*.json")
            },
            original_inputs,
        )


if __name__ == "__main__":
    unittest.main()
