import math
from pathlib import Path

import pytest

from cg14_validation import parse_csv_event, validate_event
from cg14_validation.validator import stable_event_id

FIXTURES = Path(__file__).parent / "fixtures" / "cg14"


def valid_event() -> dict[str, object]:
    raw = (FIXTURES / "valid_event.csv").read_text().strip()
    return {
        "event_id": stable_event_id(raw, "lab_fixture"),
        "machine_id": "CNC-049",
        "timestamp": "2026-10-15T08:09:06Z",
        "schema_version": "0.1.0",
        "quality_flag": "OK",
        "source": {
            "kind": "lab_fixture",
            "uri": "fixture://cg14/valid_event.csv",
            "record_ref": "valid_event.csv:1",
            "raw_record": raw,
        },
        "machine_type": "L",
        "air_temp_K": 300.5,
        "process_temp_K": 309.8,
        "rpm": 1345.0,
        "torque_Nm": 62.7,
        "tool_wear_min": 153.0,
    }


def test_valid_canonical_event_is_accepted():
    result = validate_event(valid_event())

    assert result.valid
    assert result.issues == ()
    assert result.normalized_event == valid_event()


def test_csv_adapter_keeps_raw_record_and_builds_replay_stable_id():
    raw = (FIXTURES / "valid_event.csv").read_text()
    first = parse_csv_event(
        raw, source_uri="fixture://cg14", record_ref="valid_event.csv:1"
    )
    second = parse_csv_event(
        raw, source_uri="fixture://cg14", record_ref="valid_event.csv:1"
    )

    assert first.valid
    assert first.event_id == second.event_id
    assert first.normalized_event["source"]["raw_record"] == raw.strip()


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("machine_type", "X", "INVALID_MACHINE_TYPE"),
        ("timestamp", "2026-10-15T10:09:06+02:00", "INVALID_TIMESTAMP"),
        ("timestamp", "2026-02-30T08:09:06Z", "INVALID_TIMESTAMP"),
        ("air_temp_K", math.nan, "NON_FINITE_NUMERIC"),
        ("rpm", "1456", "INVALID_NUMERIC"),
        ("torque_Nm", -1.0, "NEGATIVE_PHYSICAL_VALUE"),
    ],
)
def test_invalid_values_are_rejected_with_stable_codes(field, value, code):
    event = valid_event()
    event[field] = value

    result = validate_event(event)

    assert not result.valid
    assert code in {issue.code for issue in result.issues}
    assert result.original_record == event


def test_missing_field_is_rejected_without_repairing_the_original():
    event = valid_event()
    del event["process_temp_K"]

    result = validate_event(event)

    assert not result.valid
    assert any(
        issue.code == "MISSING_REQUIRED_FIELD" and issue.field == "process_temp_K"
        for issue in result.issues
    )
    assert "process_temp_K" not in result.original_record


def test_training_labels_are_rejected_on_inference_route():
    event = valid_event()
    event["machine_failure"] = 1

    result = validate_event(event)

    assert not result.valid
    assert any(issue.code == "TRAINING_LABEL_IN_INFERENCE" for issue in result.issues)


def test_csv_header_is_rejected_as_data():
    result = parse_csv_event(
        (FIXTURES / "header.csv").read_text(),
        source_uri="fixture://cg14",
        record_ref="header.csv:1",
    )

    assert not result.valid
    assert result.issues[0].code == "HEADER_ROW"


def test_malformed_csv_is_rejected():
    result = parse_csv_event(
        '2026-10-15T08:09:06Z,"CNC-049,L,300.5',
        source_uri="fixture://cg14",
        record_ref="malformed.csv:1",
    )

    assert not result.valid
    assert result.issues[0].code == "MALFORMED_CSV"


def test_csv_invalid_number_is_rejected():
    row = (
        (FIXTURES / "valid_event.csv")
        .read_text()
        .strip()
        .replace("1345", "not-a-number")
    )

    result = parse_csv_event(
        row, source_uri="fixture://cg14", record_ref="invalid-number.csv:1"
    )

    assert not result.valid
    assert result.issues[0].code == "INVALID_NUMERIC"


def test_csv_streaming_row_with_active_label_forwards_telemetry_stripped():
    raw = (FIXTURES / "label_active_event.csv").read_text()

    result = parse_csv_event(
        raw, source_uri="fixture://cg14", record_ref="label_active_event.csv:1"
    )

    # Failure telemetry must not be lost on the inference route: labels are
    # stripped (never model features), the original is preserved, and the
    # strip is reported as a warning for evaluation/audit.
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


def test_csv_inference_strips_zero_label_placeholders():
    raw = (FIXTURES / "valid_event.csv").read_text()

    result = parse_csv_event(
        raw, source_uri="fixture://cg14", record_ref="valid_event.csv:1"
    )

    assert result.valid
    assert result.event_id == stable_event_id(raw.strip(), "lab_fixture")
    for label in (
        "machine_failure",
        "failure_TWF",
        "failure_HDF",
        "failure_PWF",
        "failure_OSF",
        "failure_RNF",
    ):
        assert label not in result.normalized_event


def test_csv_training_mode_preserves_labels_including_known_inconsistency():
    raw = (FIXTURES / "label_active_event.csv").read_text()

    result = parse_csv_event(
        raw,
        source_uri="fixture://cg14",
        record_ref="label_active_event.csv:1",
        mode="training",
    )

    # machine_failure=1 without a subtype mirrors the 7 known historical
    # inconsistencies: preserved as-is, never auto-corrected.
    assert result.valid
    assert result.normalized_event["machine_failure"] == 1


def test_csv_label_out_of_range_is_rejected():
    row = (
        (FIXTURES / "valid_event.csv")
        .read_text()
        .strip()
        .replace(",0,0,0,0,0,0", ",0,0,2,0,0,0")
    )

    result = parse_csv_event(
        row, source_uri="fixture://cg14", record_ref="bad-label.csv:1"
    )

    assert not result.valid
    assert result.issues[0].code == "INVALID_LABEL"


def test_stream_header_with_timestamp_prefix_is_rejected_as_header():
    header = (
        "timestamp,machine_id,machine_type,air_temp_K,process_temp_K,rpm,"
        "torque_Nm,tool_wear_min,machine_failure,failure_TWF,failure_HDF,"
        "failure_PWF,failure_OSF,failure_RNF"
    )

    result = parse_csv_event(
        header, source_uri="fixture://cg14", record_ref="stream-header.csv:1"
    )

    assert not result.valid
    assert result.issues[0].code == "HEADER_ROW"


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("event_id", "not-a-hash", "INVALID_EVENT_ID"),
        ("machine_id", "MACHINE-49", "INVALID_MACHINE_ID"),
        ("machine_id", "CNC-051", None),  # outside training range but valid format
        ("schema_version", "9.9.9", "UNSUPPORTED_SCHEMA_VERSION"),
        ("quality_flag", "SUSPECT", "INVALID_QUALITY_FLAG"),
        ("source", "not-an-object", "INVALID_SOURCE"),
        ("rpm", True, "INVALID_NUMERIC"),
        ("rpm", math.inf, "NON_FINITE_NUMERIC"),
        ("timestamp", "2026-10-15T08:09:06", "INVALID_TIMESTAMP"),
    ],
)
def test_envelope_and_edge_cases(field, value, code):
    event = valid_event()
    event[field] = value

    result = validate_event(event)

    if code is None:
        assert result.valid  # format-valid IDs outside the observed range are kept
    else:
        assert not result.valid
        assert code in {issue.code for issue in result.issues}


def test_timestamp_with_millis_is_accepted():
    event = valid_event()
    event["timestamp"] = "2026-10-15T08:09:06.123456Z"

    assert validate_event(event).valid


def test_unknown_mode_is_rejected():
    assert not validate_event(valid_event(), mode="online").valid


def test_stable_id_is_deterministic_within_a_source_kind():
    raw = (FIXTURES / "valid_event.csv").read_text().strip()

    assert stable_event_id(raw, "lab_fixture") == stable_event_id(raw, "lab_fixture")
    assert stable_event_id(raw, "lab_fixture") != stable_event_id(
        raw, "cnc-simulator-v1"
    )


def test_stable_id_rejects_non_text_input_loudly():
    for bad in (None, 123, b"raw-bytes", ["x"]):
        with pytest.raises(TypeError):
            stable_event_id(bad)  # type: ignore[arg-type]


@pytest.mark.parametrize("token", ["nan", "inf", "-inf", "NaN", "Infinity"])
def test_csv_non_finite_strings_are_rejected_without_silent_repair(token):
    row = (FIXTURES / "valid_event.csv").read_text().strip().replace("300.5", token, 1)

    result = parse_csv_event(
        row, source_uri="fixture://cg14", record_ref=f"non-finite-{token}.csv:1"
    )

    assert not result.valid
    assert result.issues[0].code == "NON_FINITE_NUMERIC"
    assert result.normalized_event is None


@pytest.mark.parametrize(
    "line",
    [
        "",
        "   ",
        "2026-10-15T08:09:06Z",
        "2026-10-15T08:09:06Z,CNC-049,L,300.5",
        "2026-10-15T08:09:06Z,CNC-049,L,300.5,309.8,1345,62.7,153,0,0,0,0,0,0,EXTRA",
    ],
)
def test_csv_empty_and_wrong_column_counts_are_rejected(line):
    result = parse_csv_event(
        line, source_uri="fixture://cg14", record_ref="shape.csv:1"
    )

    assert not result.valid
    assert result.issues[0].code == "MALFORMED_CSV"


def test_csv_labels_with_surrounding_spaces_match_nifi_parity():
    row = (
        (FIXTURES / "label_active_event.csv")
        .read_text()
        .strip()
        .replace(",153,1,0,", ",153, 1 ,0,", 1)
    )

    result = parse_csv_event(row, source_uri="u", record_ref="spaces-label:1")

    assert result.valid  # int() tolera espacios; el Groovy hace trim explícito
    assert any(w.code == "TRAINING_LABEL_STRIPPED" for w in result.warnings)


def test_csv_crlf_and_millis_row_is_accepted():
    row = (FIXTURES / "valid_event.csv").read_text().strip().replace(
        "2026-10-15T08:09:06Z", "2026-10-15T08:09:06.123456Z", 1
    ) + "\r\n"

    result = parse_csv_event(
        row, source_uri="fixture://cg14", record_ref="millis.csv:1"
    )

    assert result.valid
    assert result.normalized_event["timestamp"] == "2026-10-15T08:09:06.123456Z"
