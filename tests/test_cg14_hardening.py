"""Security, integrity and resilience tests for CG14."""

import pytest

from cg14_validation import (
    PERMANENT_ISSUE_CODES,
    is_permanent_rejection,
    kafka_config_from_env,
    parse_csv_event,
    redact_for_log,
    redacted_config_for_log,
    retry_delays,
    should_retry,
    validate_event,
)


def _valid_canonical():
    from cg14_validation import stable_event_id

    return {
        "event_id": stable_event_id("hardening-probe", "lab_fixture"),
        "machine_id": "CNC-007",
        "timestamp": "2026-10-15T08:09:06Z",
        "schema_version": "0.1.0",
        "quality_flag": "OK",
        "source": {
            "kind": "lab_fixture",
            "uri": "fixture://cg14/hardening",
            "record_ref": "hardening:1",
            "raw_record": "probe",
        },
        "machine_type": "M",
        "air_temp_K": 300.0,
        "process_temp_K": 310.0,
        "rpm": 1400.0,
        "torque_Nm": 40.0,
        "tool_wear_min": 100.0,
    }


def test_canonical_json_with_labels_is_still_rejected_as_contamination():
    """JSON producers must not send labels on the inference route.

    (CSV rows strip them because the simulator always appends the 14-column
    shape; explicit JSON labels are a producer contract violation.)
    """
    event = _valid_canonical()
    event["machine_failure"] = 0

    result = validate_event(event)

    assert not result.valid
    assert any(i.code == "TRAINING_LABEL_IN_INFERENCE" for i in result.issues)


def test_non_mapping_canonical_event_is_rejected_without_exception():
    for bad in (None, "CNC-049", 42, ["x"]):
        result = validate_event(bad)  # type: ignore[arg-type]
        assert not result.valid
        assert result.issues[0].code == "INVALID_TYPE"


def test_field_length_budget_is_enforced(monkeypatch):
    monkeypatch.setenv("CG14_MAX_FIELD_CHARS", "16")
    line = "2026-10-15T08:09:06Z,CNC-049,L,300.5,309.8,1345,62.7,153,0,0,0,0,0,0"

    result = parse_csv_event(line, source_uri="u", record_ref="r")

    assert not result.valid
    assert result.issues[0].code == "MESSAGE_TOO_LARGE"


def test_all_rejection_codes_are_permanent_and_never_retried():
    for code in PERMANENT_ISSUE_CODES:
        assert is_permanent_rejection(code)
        assert not should_retry(code)
    for signal in (
        "KAFKA_UNAVAILABLE",
        "PUBLISH_FAILED",
        "SCORING_TIMEOUT",
        "SCORING_5XX",
    ):
        assert should_retry(signal)
        assert not is_permanent_rejection(signal)


def test_retry_schedule_is_bounded_and_rejects_bad_budgets():
    assert retry_delays(0) == []
    assert retry_delays(3, base_seconds=2.0, cap_seconds=60.0) == [2.0, 4.0, 8.0]
    assert retry_delays(5, base_seconds=30.0, cap_seconds=60.0)[-1] == 60.0
    with pytest.raises(ValueError):
        retry_delays(-1)
    with pytest.raises(ValueError):
        retry_delays(3, base_seconds=0)
    with pytest.raises(ValueError):
        retry_delays(10**6)  # unbounded memory from one integer: fail fast


def test_non_string_source_metadata_is_rejected():
    row = "2026-10-15T08:09:06Z,CNC-049,L,300.5,309.8,1345,62.7,153,0,0,0,0,0,0"

    result = parse_csv_event(row, source_uri=123, record_ref="r")  # type: ignore[arg-type]

    assert not result.valid
    assert "INVALID_SOURCE" in {i.code for i in result.issues}


def test_redaction_masks_credentials_and_key_material():
    assert redact_for_log("password=hunter2 rest") == "password=***REDACTED*** rest"
    assert redact_for_log("password: hunter2") == "password: ***REDACTED***"
    assert redact_for_log('secret="hunter2"') == 'secret="***REDACTED***"'
    assert "hunter2" not in redact_for_log("api_key=hunter2")
    assert "tok" not in redact_for_log("Bearer tok123")
    pem = "-----BEGIN PRIVATE KEY-----\nABC\n-----END PRIVATE KEY-----"
    assert "ABC" not in redact_for_log(pem)
    assert "tok-value" not in redact_for_log("authorization: Bearer tok-value")
    assert "tok-value" not in redact_for_log("token=tok-value")
    assert redact_for_log(12345) == "<non-text-redacted>"  # type: ignore[arg-type]


def test_malicious_strings_never_break_validation_or_logging():
    evil = '"; DROP TABLE x; -- $(rm -rf /) {{7*7}} %s %n\x00'
    row = f"2026-10-15T08:09:06Z,{evil},L,300.5,309.8,1345,62.7,153,0,0,0,0,0,0"

    result = parse_csv_event(row, source_uri="u", record_ref="evil:1")

    assert not result.valid
    logged = redact_for_log(str(result.issues[0]))
    assert result.issues[0].code in logged  # code stays searchable, payload safe


def test_kafka_config_requires_bootstrap_and_hides_secrets():
    missing = kafka_config_from_env({"KAFKA_SECURITY_PROTOCOL": "PLAINTEXT"})
    assert missing["errors"]

    bad_proto = kafka_config_from_env(
        {"KAFKA_BOOTSTRAP_SERVERS": "kafka:9092", "KAFKA_SECURITY_PROTOCOL": "ROT13"}
    )
    assert bad_proto["errors"]

    sasl = kafka_config_from_env(
        {
            "KAFKA_BOOTSTRAP_SERVERS": "kafka:9092",
            "KAFKA_SECURITY_PROTOCOL": "SASL_SSL",
            "KAFKA_SASL_MECHANISM": "SCRAM-SHA-512",
            "KAFKA_SASL_USERNAME": "cnc-nifi",
            "KAFKA_SASL_PASSWORD": "s3cr3t",
            "KAFKA_CA_CERT_PATH": "/certs/ca.crt",
        }
    )
    assert sasl["errors"] == []
    safe = redacted_config_for_log(sasl["config"])
    assert safe["sasl.password"] == "***REDACTED***"
    assert "s3cr3t" not in str(safe)


def test_duplicate_replay_yields_stable_id_but_distinct_events_differ():
    from cg14_validation import stable_event_id

    line = "2026-10-15T08:09:06Z,CNC-049,L,300.5,309.8,1345,62.7,153,0,0,0,0,0,0"
    same_a = parse_csv_event(line, source_uri="u", record_ref="a:1")
    same_b = parse_csv_event(line, source_uri="u", record_ref="b:9")
    other = stable_event_id(line.replace("CNC-049", "CNC-050", 1), "lab_fixture")

    assert same_a.valid and same_b.valid
    assert same_a.event_id == same_b.event_id  # replay-stable, safe to dedup
    assert same_a.event_id != other  # different machine is a different event


def test_missing_sensor_is_rejected_never_zero_filled():
    row = "2026-10-15T08:09:06Z,CNC-049,L,,309.8,1345,62.7,153,0,0,0,0,0,0"

    result = parse_csv_event(row, source_uri="u", record_ref="missing:1")

    assert not result.valid
    assert result.issues[0].code == "INVALID_NUMERIC"


def test_kafka_tls_and_sasl_misconfiguration_fails_fast():
    tls_no_ca = kafka_config_from_env(
        {"KAFKA_BOOTSTRAP_SERVERS": "kafka:9092", "KAFKA_SECURITY_PROTOCOL": "SSL"}
    )
    assert any("CA_CERT" in e for e in tls_no_ca["errors"])

    sasl_bare = kafka_config_from_env(
        {
            "KAFKA_BOOTSTRAP_SERVERS": "kafka:9092",
            "KAFKA_SECURITY_PROTOCOL": "SASL_PLAINTEXT",
        }
    )
    assert any("SASL" in e for e in sasl_bare["errors"])


def test_invalid_env_budgets_fall_back_to_safe_defaults(monkeypatch):
    from cg14_validation import max_field_chars, max_line_bytes

    monkeypatch.setenv("CG14_MAX_LINE_BYTES", "not-a-number")
    monkeypatch.setenv("CG14_MAX_FIELD_CHARS", "-5")

    assert max_line_bytes() == 8192
    assert max_field_chars() == 512


def test_canonical_paths_reject_empty_envelope_values():
    event = _valid_canonical()
    event["timestamp"] = None
    event["source"] = {"kind": "", "uri": "", "record_ref": ""}
    event["machine_failure"] = 7

    result = validate_event(event)

    assert not result.valid
    codes = {i.code for i in result.issues}
    assert {"MISSING_REQUIRED_FIELD", "INVALID_SOURCE", "INVALID_LABEL"} <= codes


def test_unknown_event_and_source_fields_are_rejected():
    event = _valid_canonical()
    event["vibration"] = 0.4
    event["source"] = {**event["source"], "secret": "must-not-pass"}

    result = validate_event(event)

    assert not result.valid
    assert {(issue.code, issue.field) for issue in result.issues} >= {
        ("UNEXPECTED_FIELD", "vibration"),
        ("INVALID_SOURCE", "source.secret"),
    }


def test_empty_raw_record_and_garbage_labels_and_mode_are_rejected():
    event = _valid_canonical()
    event["source"] = dict(event["source"])
    event["source"]["raw_record"] = ""
    assert any(i.code == "INVALID_SOURCE" for i in validate_event(event).issues)

    base = "2026-10-15T08:09:06Z,CNC-049,L,300.5,309.8,1345,62.7,153"
    garbage = parse_csv_event(
        f"{base},x,0,0,0,0,0", source_uri="u", record_ref="garbage-label:1"
    )
    assert not garbage.valid
    assert garbage.issues[0].code == "INVALID_LABEL"

    bad_mode = parse_csv_event(
        f"{base},0,0,0,0,0,0", source_uri="u", record_ref="m:1", mode="online"
    )
    assert not bad_mode.valid
    assert bad_mode.issues[0].code == "INVALID_MODE"


def test_fuzz_never_raises_and_always_returns_a_well_formed_verdict():
    """Property: arbitrary hostile input yields a verdict, never an exception."""
    import random

    rng = random.Random(14)
    alphabet = [
        "CNC-049",
        "L",
        "300.5",
        ",",
        '"',
        "\n",
        "nan",
        "inf",
        "-1",
        "0",
        "1",
        "2",
        "X" * 600,
        "\x00",
        "é",
        ";",
        "|",
        "\t",
        " ",
    ]
    for _ in range(1000):
        line = "".join(rng.choice(alphabet) for _ in range(rng.randint(1, 12)))

        result = parse_csv_event(line, source_uri="u", record_ref="fuzz:1")

        assert isinstance(result.valid, bool)
        assert isinstance(result.issues, tuple)
        assert isinstance(result.warnings, tuple)
        if result.valid:
            assert result.normalized_event is not None
            assert result.event_id is not None
        else:
            assert result.normalized_event is None
            assert result.issues


@pytest.mark.parametrize(
    ("line", "code"),
    [
        ("\r\n", "MALFORMED_CSV"),
        (
            "2026-10-15T08:09:06.1234567Z,CNC-049,L,300.5,309.8,1345,62.7,153,0,0,0,0,0,0",
            "INVALID_TIMESTAMP",
        ),
    ],
)
def test_hostile_shape_probes_are_rejected(line, code):
    result = parse_csv_event(line, source_uri="u", record_ref="probe:1")

    assert not result.valid
    assert result.issues[0].code == code


def test_nul_byte_payload_is_rejected_without_exception():
    row = "2026-10-15T08:09:06Z,CNC-049,L,300.5,309.8,1345,62.7,153,0,0,0,0,0,0\x00"

    result = parse_csv_event(row, source_uri="u", record_ref="nul:1")

    assert not result.valid
