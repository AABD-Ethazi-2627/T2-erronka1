
"""Reference validation utilities for the CG14 ingestion contract."""

from .metrics import ValidationMetrics
from .resilience import (
    PERMANENT_ISSUE_CODES,
    TRANSIENT_SIGNALS,
    is_permanent_rejection,
    kafka_config_from_env,
    redact_for_log,
    redacted_config_for_log,
    retry_delays,
    should_retry,
)
from .validator import (
    HISTORICAL_FIELDS,
    TELEMETRY_FIELDS,
    ValidationIssue,
    ValidationResult,
    max_field_chars,
    max_line_bytes,
    parse_csv_event,
    stable_event_id,
    validate_event,
)

__all__ = [
    "HISTORICAL_FIELDS",
    "PERMANENT_ISSUE_CODES",
    "TELEMETRY_FIELDS",
    "TRANSIENT_SIGNALS",
    "ValidationIssue",
    "ValidationMetrics",
    "ValidationResult",
    "is_permanent_rejection",
    "kafka_config_from_env",
    "max_field_chars",
    "max_line_bytes",
    "parse_csv_event",
    "redact_for_log",
    "redacted_config_for_log",
    "retry_delays",
    "should_retry",
    "stable_event_id",
    "validate_event",
]
