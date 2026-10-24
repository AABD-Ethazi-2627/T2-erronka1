"""Regression tests for defects found during the CG14 hardening audit.

Each test below describes the EXPECTED (fixed) behavior. They are written
before the fix, so some of them fail against the current implementation.
"""

from pathlib import Path

from cg14_validation import parse_csv_event

FIXTURES = Path(__file__).parent / "fixtures" / "cg14"


def test_inference_forwards_telemetry_when_labels_are_active():
    """A real failure row must NOT lose its telemetry on the inference route.

    Labels are ground truth for evaluation, never model features: the adapter
    must strip them, forward the telemetry as valid, preserve the original
    for audit, and record a warning instead of dropping the event.
    """
    raw = (FIXTURES / "label_active_event.csv").read_text()

    result = parse_csv_event(
        raw, source_uri="fixture://cg14", record_ref="label_active_event.csv:1"
    )

    assert result.valid
    assert result.normalized_event is not None
    for label in (
        "machine_failure",
        "failure_TWF",
        "failure_HDF",
        "failure_PWF",
        "failure_OSF",
        "failure_RNF",
    ):
        assert label not in result.normalized_event
    assert result.original_record["machine_failure"] == "1"
    assert any(w.code == "TRAINING_LABEL_STRIPPED" for w in result.warnings)


def test_non_string_csv_input_is_rejected_without_exception():
    for bad in (None, 12345, b"2026-10-15T08:09:06Z,CNC-049"):
        result = parse_csv_event(
            bad,
            source_uri="fixture://cg14",
            record_ref="bad-type.csv:1",  # type: ignore[arg-type]
        )
        assert not result.valid
        assert result.issues[0].code == "INVALID_TYPE"


def test_oversized_csv_line_is_rejected_with_stable_code():
    huge = "X" * 9000

    result = parse_csv_event(huge, source_uri="fixture://cg14", record_ref="huge.csv:1")

    assert not result.valid
    assert result.issues[0].code == "MESSAGE_TOO_LARGE"
