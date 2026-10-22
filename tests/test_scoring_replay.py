"""Canonical HTTP replay and real SQLite/archive boundaries, without training."""

import asyncio
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import asynccontextmanager, closing
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
from api_client import api_client
from fastapi.responses import JSONResponse

from scoring.scope import SCOPE
from scoring.score_api import create_app
from scripts.archive_consumer import consume
from scripts.rehearse_cg26 import CASES, _rehearsal

ROOT = Path(__file__).resolve().parents[1]


class RiskDouble:
    calls = 0

    def predict_proba(self, frame):
        self.calls += 1
        return np.array([[0.2, 0.8]])


class AnomalyDouble:
    def score_samples(self, frame):
        return np.array([-0.5])


class RehearsalRiskDouble:
    def predict_proba(self, frame):
        risk = 0.8 if frame.iloc[0]["rpm"] == 500 else 0.01
        return np.array([[1 - risk, risk]])


def manifest():
    return {
        **SCOPE,
        "model_version": "synthetic-replay-only",
        "policy": "f2",
        "versions": {"sklearn": "synthetic"},
        "files": {"rf.pkl": "a" * 64, "if.pkl": "b" * 64},
        "risk_threshold": 0.5,
        "anomaly_threshold": 0.4,
    }


REPLAY_CHILD = """
import json
import sys
from scoring.response_ledger import response
from scripts.validate_contracts import validators

def forbidden():
    raise AssertionError('Replay rescored after process restart')

data = json.load(sys.stdin)
result = response(data['path'], data['event'], data['manifest'], forbidden,
                  validators()['prediction'].validate)
print(json.dumps(result))
"""


class ScoringReplayTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.ledger = self.root / "responses.sqlite3"
        self.event = json.loads(
            (ROOT / "contracts/examples/valid/telemetry.json").read_text()
        )

    def app(self):
        return create_app(self.root / "absent.json", ledger_path=self.ledger)

    def ready(self, app, config=None):
        risk = RiskDouble()
        app.state.models = {"rf.pkl": risk, "if.pkl": AnomalyDouble()}
        app.state.manifest = config or manifest()
        return risk

    async def test_lost_http_response_restart_and_archive_replay(self):
        app = self.app()
        async with api_client(app) as client:
            risk = self.ready(app)
            first = await client.post("/predict", json=self.event)
            self.assertEqual(first.status_code, 200, first.text)
            original = first.json()
            repeated = await client.post(
                "/predict", json=dict(reversed(list(self.event.items())))
            )
            self.assertEqual(repeated.json(), original)
            self.assertEqual(repeated.content, first.content)
            self.assertEqual(risk.calls, 1)
        # Treat the original response as lost before publication. Recover from
        # the same durable ledger using a new application, then publish twice.
        restarted = self.app()
        async with api_client(restarted) as client:
            risk = self.ready(restarted)
            recovered = await client.post("/predict", json=self.event)
            self.assertEqual(recovered.json(), original)
            self.assertEqual(recovered.content, first.content)
            self.assertEqual(risk.calls, 0)
        # Start a real, lightweight interpreter rather than reimporting the
        # complete scientific test stack through multiprocessing.spawn.
        restarted_process = await asyncio.to_thread(
            subprocess.run,
            [sys.executable, "-B", "-c", REPLAY_CHILD],
            input=json.dumps(
                {"path": str(self.ledger), "event": self.event, "manifest": manifest()}
            ),
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        self.assertEqual(json.loads(restarted_process.stdout), original)
        acked = []
        messages = [
            ("delivery-1", "prediction", first.content),
            ("delivery-2", "prediction", recovered.content),
        ]
        stats = consume(self.root / "archive", messages, lambda: acked.append(True))
        self.assertEqual(
            (stats["stored"], stats["duplicate"], stats["rejected"]), (1, 1, 0)
        )
        self.assertEqual(acked, [True])
        replayed = consume(
            self.root / "archive",
            [("delivery-1", "prediction", recovered.content)],
            lambda: acked.append(True),
        )
        self.assertEqual(replayed["replay"], 1)
        changed = {**original, "scored_at": "2026-10-21T00:00:00Z"}
        stats = consume(
            self.root / "archive",
            [("changed", "prediction", json.dumps(changed).encode())],
            lambda: None,
        )
        self.assertEqual(stats["rejected"], 1)
        rejects = list((self.root / "archive/rejected").glob("*.json"))
        self.assertEqual(
            json.loads(rejects[0].read_text())["detail"],
            "Event identity content conflict",
        )

    async def test_same_id_different_valid_payload_conflicts_before_inference(self):
        app = self.app()
        async with api_client(app) as client:
            risk = self.ready(app)
            self.assertEqual(
                (await client.post("/predict", json=self.event)).status_code, 200
            )
            for change in (
                {"rpm": 1600},
                {"timestamp": "2000-01-01T00:00:00Z"},
                {"source": {**self.event["source"], "record_ref": "other"}},
            ):
                rejected = await client.post("/predict", json={**self.event, **change})
                self.assertEqual(rejected.status_code, 409, rejected.text)
            self.assertEqual(risk.calls, 1)
            invalid = await client.post("/predict", json={**self.event, "rpm": -1})
            self.assertEqual(invalid.status_code, 422)

    async def test_configuration_reuse_conflicts_and_new_archive_identity_succeeds(
        self,
    ):
        app = self.app()
        async with api_client(app) as client:
            risk = self.ready(app)
            first = await client.post("/predict", json=self.event)
            self.assertEqual(first.status_code, 200)
            for key, value in (
                ("model_version", "v2"),
                ("risk_threshold", 0.8),
                ("anomaly_threshold", 0.2),
                ("files", {"rf.pkl": "a" * 64, "if.pkl": "c" * 64}),
                ("versions", {"sklearn": "changed"}),
            ):
                app.state.manifest = {**manifest(), key: value}
                rejected = await client.post("/predict", json=self.event)
                self.assertEqual(rejected.status_code, 409, rejected.text)
            self.assertEqual(risk.calls, 1)
            for config in (
                {**manifest(), "policy": "f1"},
                {**manifest(), "files": {"rf.pkl": "c" * 64, "if.pkl": "b" * 64}},
            ):
                app.state.manifest = config
                changed = await client.post("/predict", json=self.event)
                self.assertEqual(changed.status_code, 200, changed.text)
            self.assertEqual(risk.calls, 3)
            changed_payload = await client.post(
                "/predict", json={**self.event, "rpm": 1600}
            )
            self.assertEqual(changed_payload.status_code, 409)
            independent = await client.post(
                "/predict", json={**self.event, "event_id": "e" * 64}
            )
            self.assertEqual(independent.status_code, 200)

    async def test_concurrent_apps_share_one_committed_response(self):
        apps = [self.app(), self.app()]
        async with api_client(apps[0]) as a, api_client(apps[1]) as b:
            risks = [self.ready(app) for app in apps]
            results = await asyncio.gather(
                *(client.post("/predict", json=self.event) for client in (a, b, a, b))
            )
            self.assertEqual([r.status_code for r in results], [200] * 4)
            self.assertTrue(all(r.json() == results[0].json() for r in results))
            self.assertEqual(sum(r.calls for r in risks), 1)

    async def test_concurrent_payload_conflict_keeps_the_winner(self):
        apps = [self.app(), self.app()]
        events = [self.event, {**self.event, "rpm": 1600}]
        async with api_client(apps[0]) as a, api_client(apps[1]) as b:
            risks = [self.ready(app) for app in apps]
            results = await asyncio.gather(
                a.post("/predict", json=events[0]), b.post("/predict", json=events[1])
            )
            self.assertEqual(sorted(r.status_code for r in results), [200, 409])
            winner = next(
                i for i, result in enumerate(results) if result.status_code == 200
            )
            replay = await a.post("/predict", json=events[winner])
            self.assertEqual(replay.json(), results[winner].json())
            self.assertEqual(sum(r.calls for r in risks), 1)

    def test_memory_database_is_not_a_durable_configuration(self):
        with self.assertRaisesRegex(ValueError, "persistent response ledger"):
            create_app(self.root / "absent", ledger_path=":memory:")

    async def test_rehearsal_uses_new_identity_for_trace_variant(self):
        path = self.root / "manifest.json"
        path.write_text(json.dumps(manifest()))
        frame = pd.DataFrame(
            [{**self.event, "rpm": rpm} for rpm in (1500.0, 500.0)],
            index=list(CASES.values()),
        )
        observed = []

        @asynccontextmanager
        async def ready_client(app):
            async with api_client(app) as client:
                if not observed:
                    self.ready(app)
                    app.state.models["rf.pkl"] = RehearsalRiskDouble()
                observed.append(app)
                yield client

        with (
            patch("scripts.rehearse_cg26.load_training_source", return_value=frame),
            patch(
                "scripts.rehearse_cg26.split_development",
                return_value=(frame, None, None),
            ),
            patch("scripts.rehearse_cg26._rehearsal_client", side_effect=ready_client),
        ):
            result = await _rehearsal(path)
        self.assertEqual(result["status"], "isolated_rehearsal_passed")
        self.assertTrue(result["trace_invariance"])
        self.assertIn("scoring/response_ledger.py", result["execution_files_sha256"])
        with closing(sqlite3.connect(self.ledger)) as con, con:
            self.assertEqual(
                con.execute("SELECT count(*) FROM scoring_events").fetchone()[0], 3
            )

    async def test_inference_and_storage_failures_never_commit_success(self):
        app = self.app()
        async with api_client(app) as client:
            risk = self.ready(app)
            with (
                patch.object(
                    risk, "predict_proba", side_effect=RuntimeError("failure")
                ),
                patch("scoring.score_api.log"),
            ):
                failure = await client.post("/predict", json=self.event)
            self.assertEqual(failure.status_code, 500)
            with closing(sqlite3.connect(self.ledger)) as con, con:
                # Failed inference rolls back schema creation as well.
                self.assertEqual(
                    con.execute(
                        "SELECT count(*) FROM sqlite_master "
                        "WHERE name='scoring_responses'"
                    ).fetchone()[0],
                    0,
                )
            with (
                patch(
                    "scoring.response_ledger.sqlite3.connect",
                    side_effect=sqlite3.OperationalError("disk unavailable"),
                ),
                patch("scoring.score_api.log"),
            ):
                failure = await client.post("/predict", json=self.event)
            self.assertEqual(failure.status_code, 500)
            success = await client.post("/predict", json=self.event)
            self.assertEqual(success.status_code, 200, success.text)
            with patch.object(
                risk, "predict_proba", side_effect=AssertionError("must replay")
            ):
                self.assertEqual(
                    (await client.post("/predict", json=self.event)).json(),
                    success.json(),
                )

    async def test_unready_bundle_does_not_serve_previously_cached_success(self):
        app = self.app()
        async with api_client(app) as client:
            self.ready(app)
            self.assertEqual(
                (await client.post("/predict", json=self.event)).status_code, 200
            )
            app.state.models = None
            self.assertEqual(
                (await client.post("/predict", json=self.event)).status_code, 503
            )

    async def test_timeout_after_commit_recovers_without_rescoring(self):
        app = self.app()

        @app.middleware("http")
        async def lose_success(request, call_next):
            result = await call_next(request)
            self.assertEqual(result.status_code, 200)
            return JSONResponse(
                status_code=504, content={"detail": "synthetic proxy timeout"}
            )

        async with api_client(app) as client:
            self.ready(app)
            self.assertEqual(
                (await client.post("/predict", json=self.event)).status_code, 504
            )
        with closing(sqlite3.connect(self.ledger)) as con, con:
            committed = json.loads(
                con.execute("SELECT response FROM scoring_responses").fetchone()[0]
            )
        restarted = self.app()
        async with api_client(restarted) as client:
            risk = self.ready(restarted)
            recovered = await client.post("/predict", json=self.event)
            self.assertEqual(recovered.status_code, 200)
            self.assertEqual(recovered.json(), committed)
            self.assertEqual(risk.calls, 0)

    async def test_failed_commit_rolls_back_and_returns_no_success(self):
        class FailedCommit(sqlite3.Connection):
            def __exit__(self, kind, value, traceback):
                if kind is None:
                    self.rollback()
                    raise sqlite3.OperationalError("synthetic commit failure")
                return super().__exit__(kind, value, traceback)

        connect = sqlite3.connect
        app = self.app()
        async with api_client(app) as client:
            risk = self.ready(app)
            with (
                patch(
                    "scoring.response_ledger.sqlite3.connect",
                    side_effect=lambda *args, **kwargs: connect(
                        *args, **kwargs, factory=FailedCommit
                    ),
                ),
                patch("scoring.score_api.log"),
            ):
                failed = await client.post("/predict", json=self.event)
            self.assertEqual(failed.status_code, 500)
            with closing(connect(self.ledger)) as con, con:
                self.assertEqual(
                    con.execute(
                        "SELECT count(*) FROM sqlite_master "
                        "WHERE name='scoring_responses'"
                    ).fetchone()[0],
                    0,
                )
            succeeded = await client.post("/predict", json=self.event)
            self.assertEqual(succeeded.status_code, 200, succeeded.text)
            self.assertEqual(risk.calls, 2)
