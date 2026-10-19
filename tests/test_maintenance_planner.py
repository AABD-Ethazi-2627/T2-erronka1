import itertools
import unittest
from datetime import UTC, datetime

from planning.maintenance import build_plan, review_task

NOW = datetime(2026, 10, 19, 10, tzinfo=UTC)


def event(identifier="a", machine="CNC-001", score=0.7, kind="H", **kw):
    return {
        "event_id": identifier,
        "machine_id": machine,
        "machine_type": kind,
        "timestamp": "2026-10-19T09:59:00Z",
        "failure_score": score,
        "anomaly_alert": False,
        "source_kind": "smb_csv",
        **kw,
    }


class MaintenancePlannerTests(unittest.TestCase):
    def test_type_is_context_not_a_fixed_risk_or_eta(self):
        plans = [build_plan([event(kind=t)], NOW) for t in ["H", "M", "L"]]
        for p in plans:
            t = p["tasks"][0]
            self.assertEqual(t["priority"], "P1")
            self.assertIsNone(t["eta_minutes"])
            self.assertTrue(t["requires_human_review"])
            self.assertEqual(t["action"], "REVIEW_DATA_AND_RISK")
        self.assertEqual(len({p["tasks"][0]["review_due_at"] for p in plans}), 1)

    def test_dedup_preserves_evidence_and_escalation(self):
        events = [event("a", score=0.2), event("b", score=0.8), event("b", score=0.8)]
        p = build_plan(events, NOW)
        self.assertEqual(len(p["tasks"]), 1)
        self.assertEqual(p["tasks"][0]["evidence_event_ids"], ["a", "b"])
        self.assertEqual(p["tasks"][0]["priority"], "P1")
        with self.assertRaises(ValueError):
            build_plan([event("a"), event("a", score=0.1)], NOW)

    def test_no_overlap_and_missed_deadline_visible(self):
        p = build_plan([event("a", "A"), event("b", "B"), event("c", "C")], NOW)
        tasks = p["tasks"]
        for a, b in itertools.pairwise(tasks):
            self.assertLessEqual(a["proposed_end"], b["proposed_start"])
        self.assertTrue(tasks[-1]["review_deadline_missed"])

    def test_invalid_and_ok_inputs(self):
        self.assertEqual(build_plan([event(score=0.1499)], NOW)["tasks"], [])
        for score in [float("nan"), -1, 1.1]:
            with self.assertRaises(ValueError):
                build_plan([event(score=score)], NOW)
        with self.assertRaises(ValueError):
            build_plan([event()], NOW.replace(tzinfo=None))

    def test_human_review_is_explicit_and_validated(self):
        p = build_plan([event()], NOW)
        t = p["tasks"][0]
        with self.assertRaises(ValueError):
            review_task(t, "complete", "lab-reviewer", "checked", NOW)
        approved = review_task(
            t, "approve", "lab-reviewer", "Demo evidence checked", NOW
        )
        self.assertEqual(approved["status"], "APPROVED")
        completed = review_task(
            approved, "complete", "lab-reviewer", "Review performed", NOW
        )
        self.assertEqual(completed["status"], "COMPLETED")
        self.assertEqual(t["status"], "PROPOSED")

    def test_weekend_deadline_and_dst(self):
        friday = datetime.fromisoformat("2026-10-23T14:45:00+00:00")
        task = build_plan([event(score=0.15)], friday)["tasks"][0]
        self.assertEqual(task["review_due_at"], "2026-10-26T15:45:00+00:00")
        self.assertEqual(task["proposed_start"], "2026-10-26T08:00:00+00:00")
        critical = build_plan([event()], friday)["tasks"][0]
        self.assertTrue(critical["review_deadline_missed"])

    def test_anomaly_stale_future_and_capacity(self):
        task = build_plan(
            [event(score=0.01, anomaly_alert=True, timestamp="2026-10-19T09:00:00Z")],
            NOW,
        )["tasks"][0]
        self.assertEqual(task["priority"], "P3")
        self.assertIn("STALE_EVIDENCE", task["warnings"])
        with self.assertRaises(ValueError):
            build_plan([event(timestamp="2026-10-19T10:01:00Z")], NOW)
        tasks = build_plan([event("a", "A"), event("b", "B")], NOW, capacity=2)["tasks"]
        self.assertEqual(tasks[0]["proposed_start"], tasks[1]["proposed_start"])
        self.assertNotEqual(tasks[0]["resource"], tasks[1]["resource"])
        self.assertFalse(any(t["review_deadline_missed"] for t in tasks))

    def test_exports_are_draft_and_do_not_overwrite(self):
        import tempfile
        from pathlib import Path

        from scripts.plan_maintenance import export_plan

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "draft"
            export_plan(build_plan([event()], NOW), output)
            ics = (output / "reviews-draft.ics").read_text()
            self.assertIn("STATUS:TENTATIVE", ics)
            self.assertNotIn("ATTENDEE", ics)
            with self.assertRaises(FileExistsError):
                export_plan(build_plan([], NOW), output)

    def test_conflict_is_visible_and_not_independent_confirmation(self):
        task = build_plan([event("a", score=0.2), event("b", score=0.8)], NOW)["tasks"][
            0
        ]
        self.assertIn("CONFLICTING_SAME_TIME_PREDICTIONS", task["warnings"])
        self.assertIsNone(task["independent_failure_confirmations"])
        with self.assertRaises(ValueError):
            review_task(task, "approve", "", "reason", NOW)
