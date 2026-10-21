"""Small, dependency-free reference validator for the proposed CG14 contract."""

from __future__ import annotations

import csv
import hashlib
import io
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

HISTORICAL_FIELDS = (
    "machine_id",
    "machine_type",
    "air_temp_K",
    "process_temp_K",
    "rpm",
    "torque_Nm",
    "tool_wear_min",
    "machine_failure",
    "failure_TWF",
    "failure_HDF",
    "failure_PWF",
    "failure_OSF",
    "failure_RNF",
)
TELEMETRY_FIELDS = HISTORICAL_FIELDS[:7]
LABEL_FIELDS = HISTORICAL_FIELDS[7:]
_MACHINE_ID = re.compile(r"^CNC-[0-9]{3}$")
_EVENT_ID = re.compile(r"^[0-9a-f]{64}$")
_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$")
_SCHEMA_VERSION = "0.1.0"
_EVENT_METADATA_FIELDS = {
    "event_id",
    "machine_id",
    "timestamp",
    "schema_version",
    "quality_flag",
    "source",
}
_SOURCE_FIELDS = {"kind", "uri", "record_ref", "raw_record"}

# DoS resistance: never attempt to parse an unbounded line. Overridable via
# environment so NiFi/CI can tighten the budget without touching code.
# CG14_MAX_LINE_BYTES: raw UTF-8 bytes per CSV line (default 8192).
# CG14_MAX_FIELD_CHARS: characters per CSV field (default 512).
_DEFAULT_MAX_LINE_BYTES = 8192
_DEFAULT_MAX_FIELD_CHARS = 512


def _limit_from_env(name: str, default: int) -> int:
    import os

    try:
        value = int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def max_line_bytes() -> int:
    """Configurable raw-line budget (bytes) for the CSV adapter."""
    return _limit_from_env("CG14_MAX_LINE_BYTES", _DEFAULT_MAX_LINE_BYTES)


def max_field_chars() -> int:
    """Configurable per-field budget (characters) for the CSV adapter."""
    return _limit_from_env("CG14_MAX_FIELD_CHARS", _DEFAULT_MAX_FIELD_CHARS)


@dataclass(frozen=True)
class ValidationIssue:
    """Stable, machine-readable reason for a rejected record."""

    code: str
    field: str | None
    message: str


@dataclass(frozen=True)
class ValidationResult:
    """Validation outcome retaining the original input for audit purposes."""

    valid: bool
    normalized_event: dict[str, object] | None
    original_record: Mapping[str, object] | str
    event_id: str | None
    issues: tuple[ValidationIssue, ...] = ()
    warnings: tuple[ValidationIssue, ...] = ()


def stable_event_id(raw_record: str, source_kind: str = "cnc-simulator-v1") -> str:
    """Create the replay-stable identity proposed for events without an ID."""
    if not isinstance(raw_record, str) or not isinstance(source_kind, str):
        raise TypeError("raw_record and source_kind must be text")

    material = f"cnc.telemetry.v{_SCHEMA_VERSION}\n{source_kind}\n{raw_record}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def validate_event(
    record: Mapping[str, object],
    *,
    original_record: Mapping[str, object] | None = None,
    mode: str = "inference",
) -> ValidationResult:
    """Validate one canonical event without silently repairing invalid values."""

    if not isinstance(record, Mapping):
        return ValidationResult(
            False,
            None,
            str(record),
            None,
            (ValidationIssue("INVALID_TYPE", None, "event must be a mapping"),),
        )
    original = original_record if original_record is not None else record
    issues: list[ValidationIssue] = []
    if mode not in {"inference", "training"}:
        issues.append(
            ValidationIssue("INVALID_MODE", "mode", "unknown validation mode")
        )

    required = (
        "event_id",
        "machine_id",
        "timestamp",
        "schema_version",
        "quality_flag",
        "source",
        *TELEMETRY_FIELDS[1:],
    )
    allowed_fields = _EVENT_METADATA_FIELDS | set(TELEMETRY_FIELDS[1:])
    if mode == "training":
        allowed_fields |= set(LABEL_FIELDS)
    for field in record:
        if field not in allowed_fields:
            issues.append(
                ValidationIssue(
                    "UNEXPECTED_FIELD",
                    str(field),
                    "field is not allowed by the contract",
                )
            )
    for field in required:
        if field not in record or record[field] in (None, ""):
            issues.append(
                ValidationIssue("MISSING_REQUIRED_FIELD", field, "field is required")
            )

    event_id = record.get("event_id")
    if event_id is not None and (
        not isinstance(event_id, str) or not _EVENT_ID.fullmatch(event_id)
    ):
        issues.append(
            ValidationIssue(
                "INVALID_EVENT_ID", "event_id", "must be a lowercase SHA-256 hex string"
            )
        )

    machine_id = record.get("machine_id")
    if machine_id is not None and (
        not isinstance(machine_id, str) or not _MACHINE_ID.fullmatch(machine_id)
    ):
        issues.append(
            ValidationIssue(
                "INVALID_MACHINE_ID", "machine_id", "expected CNC-000 format"
            )
        )

    timestamp = record.get("timestamp")
    if timestamp is not None:
        if not isinstance(timestamp, str) or not _TIMESTAMP.fullmatch(timestamp):
            issues.append(
                ValidationIssue(
                    "INVALID_TIMESTAMP",
                    "timestamp",
                    "expected UTC ISO-8601 ending in Z",
                )
            )
        else:
            try:
                datetime.fromisoformat(timestamp)
            except ValueError:
                issues.append(
                    ValidationIssue(
                        "INVALID_TIMESTAMP", "timestamp", "timestamp is not a real date"
                    )
                )

    if record.get("schema_version") != _SCHEMA_VERSION:
        issues.append(
            ValidationIssue(
                "UNSUPPORTED_SCHEMA_VERSION",
                "schema_version",
                "proposed version is 0.1.0",
            )
        )
    if record.get("quality_flag") != "OK":
        issues.append(
            ValidationIssue(
                "INVALID_QUALITY_FLAG",
                "quality_flag",
                "only OK is accepted on the valid route",
            )
        )

    source = record.get("source")
    if not isinstance(source, Mapping):
        issues.append(
            ValidationIssue(
                "INVALID_SOURCE", "source", "source metadata object is required"
            )
        )
    else:
        for field in source:
            if field not in _SOURCE_FIELDS:
                issues.append(
                    ValidationIssue(
                        "INVALID_SOURCE",
                        f"source.{field}",
                        "source field is not allowed by the contract",
                    )
                )
        for field in ("kind", "uri", "record_ref"):
            if not isinstance(source.get(field), str) or not source[field]:
                issues.append(
                    ValidationIssue(
                        "INVALID_SOURCE",
                        f"source.{field}",
                        "non-empty string is required",
                    )
                )
        if "raw_record" in source and (
            not isinstance(source["raw_record"], str) or not source["raw_record"]
        ):
            issues.append(
                ValidationIssue(
                    "INVALID_SOURCE",
                    "source.raw_record",
                    "must preserve the raw record",
                )
            )

    if record.get("machine_type") not in {"H", "M", "L"}:
        issues.append(
            ValidationIssue(
                "INVALID_MACHINE_TYPE", "machine_type", "expected H, M or L"
            )
        )

    for field in TELEMETRY_FIELDS[2:]:
        value = record.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            issues.append(
                ValidationIssue(
                    "INVALID_NUMERIC", field, "must be a numeric JSON value"
                )
            )
        elif not math.isfinite(value):
            issues.append(
                ValidationIssue(
                    "NON_FINITE_NUMERIC", field, "NaN and infinity are forbidden"
                )
            )
        elif value < 0:
            issues.append(
                ValidationIssue(
                    "NEGATIVE_PHYSICAL_VALUE",
                    field,
                    "physical measurements cannot be negative",
                )
            )

    present_labels = [field for field in LABEL_FIELDS if field in record]
    if mode == "inference" and present_labels:
        issues.append(
            ValidationIssue(
                "TRAINING_LABEL_IN_INFERENCE",
                present_labels[0],
                "training labels are not accepted on inference input",
            )
        )
    for field in present_labels:
        if record[field] not in (0, 1):
            issues.append(
                ValidationIssue(
                    "INVALID_LABEL", field, "historical labels must be 0 or 1"
                )
            )

    normalized = dict(record) if not issues else None
    return ValidationResult(
        valid=not issues,
        normalized_event=normalized,
        original_record=original,
        event_id=event_id if isinstance(event_id, str) else None,
        issues=tuple(issues),
    )


def parse_csv_event(
    line: str,
    *,
    source_uri: str,
    record_ref: str,
    source_kind: str = "lab_fixture",
    mode: str = "inference",
) -> ValidationResult:
    """Parse one simulator CSV line (UTC timestamp plus the 13 historical fields).

    The simulator keeps the 6 trailing label columns for compatibility. They
    are ground truth for training/evaluation, never model features: in
    ``inference`` mode they are validated as ``0/1``, stripped from the
    normalized event, and reported as a ``TRAINING_LABEL_STRIPPED`` warning
    when active, so a real failure row never loses its telemetry. In
    ``training`` mode the labels are preserved for offline replay.
    """

    if not isinstance(line, str):
        return ValidationResult(
            False,
            None,
            str(line),
            None,
            (ValidationIssue("INVALID_TYPE", None, "CSV line must be text"),),
        )
    if len(line.encode("utf-8")) > max_line_bytes():
        return ValidationResult(
            False,
            None,
            line[:256],
            None,
            (
                ValidationIssue(
                    "MESSAGE_TOO_LARGE",
                    None,
                    f"line exceeds {max_line_bytes()} bytes",
                ),
            ),
        )
    original = line.rstrip("\r\n")
    try:
        rows = list(csv.reader(io.StringIO(original), strict=True))
    except csv.Error as exc:
        return ValidationResult(
            False,
            None,
            original,
            None,
            (ValidationIssue("MALFORMED_CSV", None, str(exc)),),
        )
    if len(rows) != 1 or len(rows[0]) != len(HISTORICAL_FIELDS) + 1:
        code = (
            "HEADER_ROW"
            if rows and rows[0] and rows[0][0].lower() in {"timestamp", "machine_id"}
            else "MALFORMED_CSV"
        )
        return ValidationResult(
            False,
            None,
            original,
            None,
            (ValidationIssue(code, None, "expected timestamp plus 13 CSV fields"),),
        )

    values = rows[0]
    fields = ("timestamp", *HISTORICAL_FIELDS)
    raw = dict(zip(fields, values, strict=True))
    field_budget = max_field_chars()
    too_long = next(
        (name for name, value in raw.items() if len(value) > field_budget), None
    )
    if too_long is not None:
        return ValidationResult(
            False,
            None,
            raw,
            None,
            (
                ValidationIssue(
                    "MESSAGE_TOO_LARGE",
                    too_long,
                    f"field exceeds {field_budget} characters",
                ),
            ),
        )
    if (
        raw.get("timestamp", "").strip().lower() == "timestamp"
        or raw.get("machine_id", "").strip().lower() == "machine_id"
        or raw.get("machine_type", "").strip().lower() == "machine_type"
    ):
        return ValidationResult(
            False,
            None,
            original,
            None,
            (ValidationIssue("HEADER_ROW", None, "header row received as data"),),
        )
    try:
        converted: dict[str, object] = {
            "timestamp": raw["timestamp"],
            "machine_id": raw["machine_id"],
            "machine_type": raw["machine_type"],
            **{field: float(raw[field]) for field in TELEMETRY_FIELDS[2:]},
        }
    except (TypeError, ValueError):
        return ValidationResult(
            False,
            None,
            raw,
            None,
            (
                ValidationIssue(
                    "INVALID_NUMERIC", None, "CSV contains a non-numeric value"
                ),
            ),
        )
    try:
        labels: dict[str, int] = {field: int(raw[field]) for field in LABEL_FIELDS}
    except (TypeError, ValueError):
        return ValidationResult(
            False,
            None,
            raw,
            None,
            (
                ValidationIssue(
                    "INVALID_LABEL", None, "CSV label columns must be 0 or 1"
                ),
            ),
        )
    if any(value not in (0, 1) for value in labels.values()):
        bad = next(field for field in LABEL_FIELDS if labels[field] not in (0, 1))
        return ValidationResult(
            False,
            None,
            raw,
            None,
            (
                ValidationIssue(
                    "INVALID_LABEL", bad, "historical labels must be 0 or 1"
                ),
            ),
        )
    if mode not in {"inference", "training"}:
        return ValidationResult(
            False,
            None,
            raw,
            None,
            (ValidationIssue("INVALID_MODE", "mode", "unknown validation mode"),),
        )

    event = {
        "event_id": stable_event_id(original, source_kind),
        "machine_id": converted["machine_id"],
        "timestamp": converted["timestamp"],
        "schema_version": _SCHEMA_VERSION,
        "quality_flag": "OK",
        "source": {
            "kind": source_kind,
            "uri": source_uri,
            "record_ref": record_ref,
            "raw_record": original,
        },
        **{field: converted[field] for field in TELEMETRY_FIELDS[1:]},
    }
    warnings: tuple[ValidationIssue, ...] = ()
    if mode == "training":
        event.update(labels)
    elif any(value != 0 for value in labels.values()):
        stripped = next(field for field in LABEL_FIELDS if labels[field] != 0)
        warnings = (
            ValidationIssue(
                "TRAINING_LABEL_STRIPPED",
                stripped,
                "ground-truth labels stripped from inference telemetry",
            ),
        )
    result = validate_event(event, original_record=raw, mode=mode)
    if not result.valid or not warnings:
        return result
    return ValidationResult(
        True, result.normalized_event, raw, result.event_id, (), warnings
    )
