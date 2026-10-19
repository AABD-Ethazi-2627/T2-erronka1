import json
import unittest
from copy import deepcopy

from test_adaptive import manifest, rows

from planning.online import OnlineForecaster, crossing_proposal
from planning.selection import compare_candidates


class RuntimeTests(unittest.TestCase):
    def test_resume_is_identical_and_predicts_before_learning(self):
        source = rows()
        a = OnlineForecaster(manifest(), horizon_minutes=1)
        all_predictions = [a.observe(r) for r in source]
        b = OnlineForecaster(manifest(), horizon_minutes=1)
        partial = [b.observe(r) for r in source[:6]]
        b = OnlineForecaster.restore(json.loads(json.dumps(b.snapshot())), manifest())
        partial += [b.observe(r) for r in source[6:]]
        self.assertEqual(all_predictions, partial)
        self.assertEqual(a.snapshot(), b.snapshot())
        changed = deepcopy(source)
        changed[-1]["wear"] = 999
        c = OnlineForecaster(manifest(), horizon_minutes=1)
        result = [c.observe(r) for r in changed]
        self.assertEqual(
            result[-1]["evaluated_forecast"]["values"],
            all_predictions[-1]["evaluated_forecast"]["values"],
        )

    def test_bad_resume_and_out_of_order_are_rejected_without_mutation(self):
        engine = OnlineForecaster(manifest())
        engine.observe(rows()[0])
        before = engine.snapshot()
        engine.observe(rows()[0])
        self.assertEqual(engine.snapshot(), before)
        with self.assertRaises(ValueError):
            engine.observe(dict(rows()[0], wear=999))
        config = manifest()
        config["dataset_id"] = "different"
        with self.assertRaises(ValueError):
            OnlineForecaster.restore(before, config)

    def test_fixed_horizon_not_scored_on_wrong_timestamp(self):
        engine = OnlineForecaster(manifest(), horizon_minutes=5)
        engine.observe(rows()[0])
        result = engine.observe(rows()[1])
        self.assertIsNone(result["evaluated_forecast"])
        self.assertEqual(result["forecast"]["horizon_minutes"], 5)

    def test_crossing_is_a_model_estimate_not_failure_eta(self):
        engine = OnlineForecaster(manifest(), horizon_minutes=1)
        for r in rows():
            engine.observe(r)
        limits = {"wear": {"upper": 40, "unit": "min", "source": "synthetic test rule"}}
        proposal = crossing_proposal(
            engine, "A", "one", limits, max_minutes=20, minimum_updates=5
        )
        self.assertEqual(proposal["status"], "PROJECTED_LIMIT_CROSSING")
        self.assertAlmostEqual(proposal["crossings"]["wear"]["central_minutes"], 4)
        self.assertIsNone(proposal["failure_eta_minutes"])
        self.assertFalse(proposal["operationally_validated"])
        with self.assertRaises(ValueError):
            crossing_proposal(
                engine, "A", "one", {"wear": {"upper": 40, "unit": "K", "source": "x"}}
            )

    def test_selection_uses_earlier_validation_and_keeps_future_separate(self):
        source = [
            dict(
                rows()[0],
                at=f"2026-10-19T{i // 60:02}:{i % 60:02}:00Z",
                wear=float(10 + 2 * i),
            )
            for i in range(180)
        ]
        result = compare_candidates(source, manifest(), minimum_pairs=5)
        self.assertFalse(result["runtime_promotion_allowed"])
        self.assertGreater(result["acceptance"]["count"], 5)
        self.assertEqual(result["selection_basis"], "VALIDATION_ONLY")
        self.assertTrue(
            result["chronology"]["train_end"] < result["chronology"]["validation_start"]
        )

    def test_lab_registry_compare_and_swap_rollback_and_rejection(self):
        import tempfile

        from planning.registry import ShadowRegistry

        with tempfile.TemporaryDirectory() as directory:
            registry = ShadowRegistry(directory)
            report = {
                "lab_decision": "ACCEPTED_SHADOW_ONLY",
                "runtime_promotion_allowed": False,
            }
            first = registry.stage(report, OnlineForecaster(manifest()).snapshot())
            registry.activate(
                first,
                expected_active=None,
                actor="lab-agent",
                reason="fixture evaluation",
            )
            second = registry.stage(
                {
                    **report,
                    "baseline_kind": "CURRENT_CHAMPION",
                    "compared_shadow_version": first,
                    "champion_alpha": 0.25,
                },
                OnlineForecaster(manifest()).snapshot(),
            )
            with self.assertRaises(ValueError):
                registry.activate(
                    second,
                    expected_active=None,
                    actor="lab-agent",
                    reason="stale writer",
                )
            registry.activate(
                second,
                expected_active=first,
                actor="lab-agent",
                reason="second fixture",
            )
            registry.rollback(
                expected_active=second, actor="lab-agent", reason="rollback fixture"
            )
            self.assertEqual(registry.status()["active"], first)
            self.assertEqual(len(registry.status()["audit"]), 3)
            rejected = registry.stage(
                {"lab_decision": "REJECTED", "runtime_promotion_allowed": False},
                OnlineForecaster(manifest()).snapshot(),
            )
            with self.assertRaises(ValueError):
                registry.activate(
                    rejected, expected_active=first, actor="lab-agent", reason="invalid"
                )

    def test_stale_lifecycle_and_gap_never_reuse_rate(self):
        model = OnlineForecaster(manifest())
        for row in rows()[:4]:
            model.observe(row)
        model.observe(dict(rows()[4], run="two", wear=0))
        with self.assertRaises(ValueError):
            model.observe(dict(rows()[5], run="one"))
        output = model.observe(
            dict(rows()[5], run="two", at="2026-10-19T11:00:00Z", wear=8)
        )
        self.assertEqual(output["forecast"]["values"]["wear"], 8)
        self.assertIsNone(output["evaluated_forecast"])

    def test_candidate_must_beat_current_champion_not_only_persistence(self):
        source = [
            dict(
                rows()[0],
                at=f"2026-10-19T{i // 60:02}:{i % 60:02}:00Z",
                wear=float(10 + 2 * i),
            )
            for i in range(180)
        ]
        result = compare_candidates(
            source, manifest(), alphas=(0.25,), champion_alpha=0.25, minimum_pairs=5
        )
        self.assertEqual(result["lab_decision"], "REJECTED")
        self.assertEqual(result["baseline_kind"], "CURRENT_CHAMPION")

    def test_mechanism_adapter_preserves_type_and_does_not_invent_time(self):
        from planning.mechanisms import ai4i_margins

        row = {
            "asset_id": "A",
            "component_cycle": "one",
            "event_time": "2026-10-19T10:00:00Z",
            "machine_type": "L",
            "air_temp_K": 300.0,
            "process_temp_K": 308.0,
            "rpm": 1300.0,
            "torque_Nm": 50.0,
            "tool_wear_min": 200.0,
        }
        result = ai4i_margins(row)
        self.assertEqual(result["overstrain_margin"], 1000.0)
        self.assertLess(result["thermal_margin"], 0.0)
        high = ai4i_margins(dict(row, machine_type="H"))
        self.assertEqual(high["overstrain_margin"], 3000.0)
        del row["event_time"]
        with self.assertRaises(ValueError):
            ai4i_margins(row)

    def test_checkpoint_batch_replay_and_conflict_are_fail_closed(self):
        from planning.cycle import update_batch

        a = update_batch(
            rows()[:6], manifest(), batch_id="batch1", source_hash="a" * 64
        )
        duplicate = update_batch(
            rows()[:6],
            manifest(),
            batch_id="batch1",
            source_hash="a" * 64,
            checkpoint=a,
        )
        self.assertEqual(a, duplicate)
        with self.assertRaises(ValueError):
            update_batch(
                rows()[:6],
                manifest(),
                batch_id="batch1",
                source_hash="b" * 64,
                checkpoint=a,
            )
        b = update_batch(
            rows()[6:],
            manifest(),
            batch_id="batch2",
            source_hash="b" * 64,
            checkpoint=a,
        )
        self.assertEqual(len(b["processed_batches"]), 2)
        model = OnlineForecaster.restore(b["state"], manifest())
        full = OnlineForecaster(manifest())
        for row in rows():
            full.observe(row)
        self.assertEqual(model.snapshot(), full.snapshot())

    def test_inbox_requires_ready_hash_and_keeps_checkpoint_on_error(self):
        import csv
        import hashlib
        import tempfile
        from pathlib import Path

        from scripts.watch_adaptive import run_once

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inbox = root / "inbox"
            inbox.mkdir()
            source = inbox / "batch.csv"
            with source.open("w") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows()[0]))
                writer.writeheader()
                writer.writerows(rows())
            config = root / "manifest.json"
            config.write_text(json.dumps(manifest()))
            self.assertEqual(run_once(inbox, config, root / "work")["processed"], 0)
            (inbox / "batch.ready").write_text(
                json.dumps(
                    {
                        "csv": "batch.csv",
                        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                    }
                )
            )
            self.assertEqual(run_once(inbox, config, root / "work")["processed"], 1)
            checkpoint = (root / "work/checkpoint.json").read_bytes()
            self.assertEqual(run_once(inbox, config, root / "work")["processed"], 0)
            source.write_text("changed")
            with self.assertRaises(ValueError):
                run_once(inbox, config, root / "work")
            self.assertEqual((root / "work/checkpoint.json").read_bytes(), checkpoint)

    def test_rate_shift_diagnostic_uses_only_prior_errors(self):
        model = OnlineForecaster(manifest(), horizon_minutes=1)
        for i in range(30):
            model.observe(
                dict(rows()[0], at=f"2026-10-19T10:{i:02}:00Z", wear=10.0 + 2 * i)
            )
        output = model.observe(dict(rows()[0], at="2026-10-19T10:30:00Z", wear=200.0))
        self.assertTrue(output["diagnostics"]["wear"]["rate_shift_flag"])
        self.assertEqual(output["diagnostics"]["wear"]["prior_absolute_error_p95"], 0.0)

    def test_training_result_can_resume_selected_configuration(self):
        from planning.cycle import update_batch

        source = [
            dict(
                rows()[0],
                at=f"2026-10-19T{i // 60:02}:{i % 60:02}:00Z",
                wear=float(10 + 2 * i),
            )
            for i in range(180)
        ]
        report = compare_candidates(
            source, manifest(), alphas=(0.5,), horizon_minutes=5, minimum_pairs=5
        )
        next_row = dict(source[-1], at="2026-10-19T03:00:00Z", wear=370.0)
        checkpoint = update_batch(
            [next_row],
            manifest(),
            batch_id="new",
            source_hash="a" * 64,
            checkpoint=report,
        )
        self.assertEqual(checkpoint["state"]["alpha"], 0.5)
        self.assertEqual(checkpoint["state"]["horizon_minutes"], 5)

    def test_registry_rejects_replacement_without_champion_evaluation(self):
        import tempfile

        from planning.registry import ShadowRegistry

        with tempfile.TemporaryDirectory() as directory:
            registry = ShadowRegistry(directory)
            report = {
                "lab_decision": "ACCEPTED_SHADOW_ONLY",
                "runtime_promotion_allowed": False,
                "baseline_kind": "PERSISTENCE",
                "compared_shadow_version": None,
            }
            first = registry.stage(report, OnlineForecaster(manifest()).snapshot())
            registry.activate(
                first, expected_active=None, actor="lab-agent", reason="initial"
            )
            second = registry.stage(
                {**report, "fixture_revision": 2},
                OnlineForecaster(manifest()).snapshot(),
            )
            with self.assertRaises(ValueError):
                registry.activate(
                    second,
                    expected_active=first,
                    actor="lab-agent",
                    reason="no champion comparison",
                )

    def test_worker_recovers_after_interrupted_atomic_publish(self):
        import csv
        import hashlib
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        from scripts.watch_adaptive import run_once

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inbox = root / "inbox"
            inbox.mkdir()
            source = inbox / "batch.csv"
            with source.open("w") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows()[0]))
                writer.writeheader()
                writer.writerows(rows())
            (inbox / "batch.ready").write_text(
                json.dumps(
                    {
                        "csv": "batch.csv",
                        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                    }
                )
            )
            config = root / "manifest.json"
            config.write_text(json.dumps(manifest()))
            with (
                patch(
                    "scripts.watch_adaptive.os.replace",
                    side_effect=OSError("simulated interruption"),
                ),
                self.assertRaises(OSError),
            ):
                run_once(inbox, config, root / "work")
            self.assertFalse((root / "work/checkpoint.json").exists())
            self.assertEqual(run_once(inbox, config, root / "work")["processed"], 1)
            changed = manifest()
            changed["dataset_id"] = "different"
            config.write_text(json.dumps(changed))
            with self.assertRaises(ValueError):
                run_once(inbox, config, root / "work")

    def test_review_window_is_derived_from_predicted_crossing(self):
        model = OnlineForecaster(manifest(), horizon_minutes=1)
        for row in rows():
            model.observe(row)
        result = crossing_proposal(
            model,
            "A",
            "one",
            {"wear": {"upper": 40, "unit": "min", "source": "fixture"}},
            minimum_updates=5,
        )
        self.assertEqual(
            result["model_review_window"]["before"], "2026-10-19T10:15:00+00:00"
        )
        self.assertEqual(
            result["model_review_window"]["basis"],
            "EARLIEST_PROJECTED_SCENARIO_CROSSING",
        )
        self.assertTrue(result["requires_current_data_verification"])

    def test_worker_can_start_from_selected_model_state(self):
        import csv
        import hashlib
        import tempfile
        from pathlib import Path

        from scripts.watch_adaptive import run_once

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inbox = root / "inbox"
            inbox.mkdir()
            config = root / "manifest.json"
            config.write_text(json.dumps(manifest()))
            model = OnlineForecaster(manifest(), alpha=0.5, horizon_minutes=3)
            for row in rows()[:6]:
                model.observe(row)
            seed = root / "seed.json"
            seed.write_text(json.dumps({"state_after_acceptance": model.snapshot()}))
            source = inbox / "batch.csv"
            with source.open("w") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows()[0]))
                writer.writeheader()
                writer.writerows(rows()[6:])
            (inbox / "batch.ready").write_text(
                json.dumps(
                    {
                        "csv": source.name,
                        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                    }
                )
            )
            run_once(inbox, config, root / "work", seed=seed)
            state = json.loads((root / "work/checkpoint.json").read_text())["state"]
            self.assertEqual(state["alpha"], 0.5)
            self.assertEqual(state["horizon_minutes"], 3)

    def test_registry_recovers_from_interrupted_stage_publish(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        from planning.registry import ShadowRegistry

        with tempfile.TemporaryDirectory() as directory:
            registry = ShadowRegistry(directory)
            report = {
                "lab_decision": "ACCEPTED_SHADOW_ONLY",
                "runtime_promotion_allowed": False,
                "baseline_kind": "PERSISTENCE",
                "compared_shadow_version": None,
            }
            state = OnlineForecaster(manifest()).snapshot()

            def interrupt(value, handle, **kwargs):
                handle.write("{")
                raise OSError("simulated interruption")

            with (
                patch("planning.registry.json.dump", side_effect=interrupt),
                self.assertRaises(OSError),
            ):
                registry.stage(report, state)
            self.assertEqual(list((Path(directory) / "versions").glob("*.json")), [])
            version = registry.stage(report, state)
            registry.activate(
                version,
                expected_active=None,
                actor="lab-agent",
                reason="recovered synthetic stage",
            )
            self.assertEqual(registry.status()["active"], version)
