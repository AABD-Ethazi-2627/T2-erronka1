"""Observability tests for CG14 (G07): real observations, no mocks."""

import json
import threading

import pytest

from cg14_validation import ValidationMetrics, parse_csv_event
from cg14_validation.validator import stable_event_id

VALID = "2026-10-15T08:09:06Z,CNC-049,L,300.5,309.8,1345,62.7,153,0,0,0,0,0,0"
ACTIVE_LABEL = "2026-10-15T08:09:06Z,CNC-049,L,300.5,309.8,1345,62.7,153,1,0,0,0,0,0"
HEADER = (
    "machine_id,machine_type,air_temp_K,process_temp_K,rpm,torque_Nm,"
    "tool_wear_min,machine_failure,failure_TWF,failure_HDF,"
    "failure_PWF,failure_OSF,failure_RNF"
)


def _observe(metrics, line):
    result = parse_csv_event(line, source_uri="u", record_ref="m:1")
    metrics.observe(result)
    return result


def test_fresh_metrics_start_at_zero_and_snapshot_is_json_serializable():
    snapshot = ValidationMetrics().snapshot()

    assert snapshot["received"] == 0
    assert snapshot["latency_mean_s"] == 0.0
    json.dumps(snapshot)


def test_valid_rejected_and_warning_counts_come_from_real_results():
    metrics = ValidationMetrics()

    _observe(metrics, VALID)
    _observe(metrics, ACTIVE_LABEL)  # valid telemetry + STRIPPED warning
    _observe(metrics, HEADER)  # rejected HEADER_ROW

    snapshot = metrics.snapshot()
    assert snapshot["received"] == 3
    assert snapshot["valid"] == 2
    assert snapshot["rejected"] == 1
    assert snapshot["rejected_by_code"] == {"HEADER_ROW": 1}
    assert snapshot["warnings_by_code"] == {"TRAINING_LABEL_STRIPPED": 1}


def test_latency_stats_reflect_real_samples_and_reject_garbage():
    metrics = ValidationMetrics()

    with metrics.time_validation():
        _observe(metrics, VALID)
    metrics.observe_latency(0.5)

    snapshot = metrics.snapshot()
    assert snapshot["latency_samples"] == 2
    assert snapshot["latency_max_s"] >= 0.5
    assert 0.0 <= snapshot["latency_mean_s"] <= snapshot["latency_max_s"]

    for bad in (-1.0, float("nan"), float("inf"), True, "fast"):
        with pytest.raises(ValueError):
            metrics.observe_latency(bad)


def test_publish_failures_and_retries_are_counted_separately():
    metrics = ValidationMetrics()
    metrics.record_publish_failure()
    metrics.record_retry()
    metrics.record_retry()

    snapshot = metrics.snapshot()
    assert snapshot["publish_failures"] == 1
    assert snapshot["retries"] == 2


def test_concurrent_observers_do_not_lose_counts():
    metrics = ValidationMetrics()
    threads = [
        threading.Thread(target=lambda: [_observe(metrics, VALID) for _ in range(50)])
        for _ in range(4)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert metrics.snapshot()["received"] == 200


def test_identical_readings_at_different_times_are_different_events():
    """Two legitimate reads may share every sensor value; timestamp splits them."""
    first = stable_event_id(VALID, "lab_fixture")
    moved = stable_event_id(VALID.replace("08:09:06", "08:09:07", 1), "lab_fixture")

    assert first != moved


def test_exact_replay_keeps_stable_id_for_safe_dedup():
    line = VALID
    first = parse_csv_event(line, source_uri="u", record_ref="a:1")
    second = parse_csv_event(line, source_uri="u", record_ref="b:9")

    assert first.valid and second.valid
    assert first.event_id == second.event_id
