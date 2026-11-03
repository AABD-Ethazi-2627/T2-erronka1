import unittest

from domain import gallery_machine, kpis, validate_machines
from read_contracts import COLUMNS, evaluation, history, scenario

SENTINEL = {
    "id": "CNC-004",
    "zenbakia": 4,
    "tenperatura": 21.0,
    "rpm": 1801,
    "torque": 5.0,
    "higadura": 7,
    "egoera": "Normala",
    "giro_tenperatura": None,
    "event_id": "sentinel",
    "timestamp": "2026-11-03T00:00:00Z",
    "model_version": "fixture",
    "model_artifact_sha256": "a" * 64,
    "policy": {"name": "fixture"},
    "quality_flag": "OK",
    "source": {"kind": "fixture", "uri": "fixture://sentinel"},
    "prediction_scope": "AI4I_CURRENT_STATE_ONLY",
    "score_semantics": "uncalibrated_current_state_score",
    "temporal_prediction_enabled": False,
    "failure_score": 0.123,
    "risk_alert": False,
    "alert_level": "OK",
}


def history_fixture():
    return {
        "datuak": dict(zip(COLUMNS, [["2026-11-03T00:00:00Z"], [21.0], [5.0], [None]])),
        "metadata": {
            "coverage": {"n": 1},
            "from": "2026-11-02T00:00:00Z",
            "to": "2026-11-03T01:00:00Z",
            "source": SENTINEL["source"],
        },
        "next_cursor": None,
    }


def evaluation_fixture():
    return {
        "available": True,
        "scope": "offline",
        "decision_rule": "risk_alert@policy",
        "model_version": "fixture",
        "model_artifact_sha256": "a" * 64,
        "partition": "validation_reused_for_threshold",
        "threshold": 0.5,
        "labels": [0, 1],
        "confusion_matrix": [[8, 2], [1, 3]],
        "provenance": {"kind": "fixture", "artifact_sha256": "b" * 64},
    }


class ReadContracts(unittest.TestCase):
    def test_empty_single_full_nullable_and_provenance(self):
        self.assertEqual(validate_machines([]), [])
        self.assertEqual(validate_machines([SENTINEL]), [SENTINEL])
        self.assertEqual(gallery_machine(SENTINEL)["source"], SENTINEL["source"])
        row = {
            **SENTINEL,
            "tenperatura": None,
            "rpm": None,
            "torque": None,
            "higadura": None,
        }
        self.assertEqual(validate_machines([row]), [row])
        self.assertIsNone(kpis([row])["tenperatura"])
        self.assertIsNone(kpis([])["tenperatura"])

    def test_invalid_and_duplicate_never_fabricate(self):
        for key in ("tenperatura", "rpm", "torque", "higadura", "failure_score"):
            for bad in (float("nan"), float("inf"), True, "21"):
                with self.subTest(key=key, bad=bad), self.assertRaises(ValueError):
                    validate_machines([{**SENTINEL, key: bad}])
        with self.assertRaises(ValueError):
            validate_machines([SENTINEL, SENTINEL])

    def test_history_container_metadata_and_cursor(self):
        payload = history_fixture()
        payload["next_cursor"] = "opaque-token"
        frame = history(payload)
        self.assertEqual(list(frame.columns), COLUMNS)
        self.assertEqual(frame.iloc[0, 1], 21)
        self.assertIsNone(frame.iloc[0, 3])
        self.assertEqual(
            frame.attrs,
            {"metadata": payload["metadata"], "next_cursor": "opaque-token"},
        )
        payload["datuak"] = {k: [] for k in COLUMNS}
        self.assertTrue(history(payload).empty)

    def test_history_malformed_and_nonfinite(self):
        for mutate in (
            lambda p: p.pop("metadata"),
            lambda p: p["datuak"][COLUMNS[1]].append(1),
            lambda p: p["datuak"].update({COLUMNS[1]: [float("nan")]}),
            lambda p: p["datuak"].update(Ordua=["12:00"]),
            lambda p: p["datuak"].update(Ordua=[None]),
        ):
            payload = history_fixture()
            mutate(payload)
            with self.assertRaises((ValueError, TypeError)):
                history(payload)

    def test_binary_evaluation_metrics_and_zero_denominators(self):
        payload = evaluation_fixture()
        result = evaluation(payload, SENTINEL)
        self.assertEqual((result["FP"], result["FN"], result["n"]), (2, 1, 14))
        self.assertEqual(result["recall"], 0.75)
        payload["confusion_matrix"] = [[0, 0], [0, 0]]
        result = evaluation(payload, SENTINEL)
        self.assertIsNone(result["accuracy"])
        self.assertIsNone(result["f1"])

    def test_absent_invalid_incompatible_evaluation(self):
        for changes in (
            {"available": False},
            {"confusion_matrix": [[1, 2, 3]] * 3},
            {"confusion_matrix": [[1, 2], [3, float("nan")]]},
            {"model_artifact_sha256": "other"},
            {"partition": None},
            {"decision_rule": None},
            {"provenance": {}},
            {"model_artifact_sha256": None},
            {"threshold": float("nan")},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                evaluation({**evaluation_fixture(), **changes}, SENTINEL)

    def test_scenario_explicit_inputs_no_probability(self):
        self.assertEqual(scenario(20, 2, 100), 220)
        for value in (None, float("nan"), float("inf"), -1, True):
            with self.assertRaises(ValueError):
                scenario(20, value, 100)
