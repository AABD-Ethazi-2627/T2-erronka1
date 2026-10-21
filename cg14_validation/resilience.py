"""Resilience and security helpers for the CG14 validation route.

Dependency-free so NiFi ``ExecuteScript`` (Jython) and plain Python share the
same policy. Nothing here opens sockets; it only classifies outcomes, bounds
retries, builds Kafka client settings from the environment, and redacts
secrets for logs.
"""

from __future__ import annotations

import os
import re

# Validation rejections are PERMANENT: reprocessing the same bytes yields the
# same verdict, so NiFi must route them to ``cnc.rejected`` WITHOUT retry.
# Retrying them is how poison messages become infinite loops.
PERMANENT_ISSUE_CODES = frozenset(
    {
        "MISSING_REQUIRED_FIELD",
        "MALFORMED_CSV",
        "HEADER_ROW",
        "INVALID_NUMERIC",
        "NON_FINITE_NUMERIC",
        "INVALID_TIMESTAMP",
        "INVALID_MACHINE_TYPE",
        "INVALID_MACHINE_ID",
        "NEGATIVE_PHYSICAL_VALUE",
        "INVALID_EVENT_ID",
        "UNSUPPORTED_SCHEMA_VERSION",
        "INVALID_QUALITY_FLAG",
        "INVALID_SOURCE",
        "UNEXPECTED_FIELD",
        "INVALID_TYPE",
        "INVALID_MODE",
        "INVALID_LABEL",
        "MESSAGE_TOO_LARGE",
        "TRAINING_LABEL_IN_INFERENCE",
    }
)

# Transport/publish signals are TRANSIENT: bounded retries apply, then the
# FlowFile goes to a retry/dead-letter relationship, never dropped silently.
TRANSIENT_SIGNALS = frozenset(
    {
        "KAFKA_UNAVAILABLE",
        "PUBLISH_FAILED",
        "CONSUME_TIMEOUT",
        "SCORING_TIMEOUT",
        "SCORING_5XX",
        "ES_UNAVAILABLE",
    }
)

# Fail-fast ceiling: a retry schedule is a short, bounded list. Anything above
# is a misconfiguration, not a plan (a million-entry list costs ~8 MB).
MAX_RETRY_ATTEMPTS = 10

_REDACT_PATTERNS = (
    re.compile(r"(?i)(password\s*[:=]\s*[\"']?)([^\s;,\"']+)"),
    re.compile(r"(?i)(passwd\s*[:=]\s*[\"']?)([^\s;,\"']+)"),
    re.compile(r"(?i)(api[_-]?key\s*[:=]\s*[\"']?)([^\s;,\"']+)"),
    re.compile(r"(?i)(secret\s*[:=]\s*[\"']?)([^\s;,\"']+)"),
    re.compile(r"(?i)(token\s*[:=]\s*[\"']?)([^\s;,\"']+)"),
    re.compile(r"(?i)(authorization\s*[:=]\s*[\"']?(?:bearer\s+)?)([^\s;,\"']+)"),
    re.compile(r"(?i)(bearer\s+)([A-Za-z0-9._~+/=-]+)"),
    re.compile(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
        re.DOTALL,
    ),
)


def should_retry(code: str) -> bool:
    """Return True only for transient transport signals, never for rejections."""
    return code in TRANSIENT_SIGNALS


def is_permanent_rejection(code: str) -> bool:
    """Return True when the code must go straight to the rejected route."""
    return code in PERMANENT_ISSUE_CODES


def retry_delays(
    attempts: int, *, base_seconds: float = 2.0, cap_seconds: float = 60.0
) -> list[float]:
    """Bounded exponential backoff delays (pure function, no sleeping).

    Raises ``ValueError`` for non-positive budgets so misconfiguration fails
    fast instead of producing an unbounded or silent schedule.
    """
    if attempts < 0:
        raise ValueError("attempts must be >= 0")
    if attempts > MAX_RETRY_ATTEMPTS:
        raise ValueError(f"attempts capped at {MAX_RETRY_ATTEMPTS} to bound memory")
    if base_seconds <= 0 or cap_seconds <= 0:
        raise ValueError("backoff budgets must be positive")
    delays: list[float] = []
    delay = base_seconds
    for _ in range(attempts):
        delays.append(min(delay, cap_seconds))
        delay *= 2.0
    return delays


def redact_for_log(text: str) -> str:
    """Mask credentials and key material before logging or error envelopes."""
    if not isinstance(text, str):
        return "<non-text-redacted>"
    redacted = text
    for pattern in _REDACT_PATTERNS:
        if pattern.groups >= 1:
            redacted = pattern.sub(lambda m: m.group(1) + "***REDACTED***", redacted)
        else:
            redacted = pattern.sub("***REDACTED***", redacted)
    return redacted


def kafka_config_from_env(env: dict[str, str] | None = None) -> dict[str, object]:
    """Build Kafka client settings exclusively from the environment.

    Required: ``KAFKA_BOOTSTRAP_SERVERS``. Everything else has safe,
    non-privileged defaults; credentials only come from
    ``KAFKA_SASL_USERNAME`` / ``KAFKA_SASL_PASSWORD`` and are never logged
    (use :func:`redacted_config_for_log`). Returns
    ``{"config": {...}, "errors": [...]}``; ``errors`` is non-empty when the
    client must NOT start.
    """
    source = dict(os.environ) if env is None else dict(env)
    errors: list[str] = []
    bootstrap = (source.get("KAFKA_BOOTSTRAP_SERVERS") or "").strip()
    if not bootstrap:
        errors.append("KAFKA_BOOTSTRAP_SERVERS is required")
    protocol = (source.get("KAFKA_SECURITY_PROTOCOL") or "PLAINTEXT").strip()
    if protocol not in {"PLAINTEXT", "SSL", "SASL_PLAINTEXT", "SASL_SSL"}:
        errors.append(f"unsupported KAFKA_SECURITY_PROTOCOL: {protocol}")
    config: dict[str, object] = {
        "bootstrap.servers": bootstrap,
        "security.protocol": protocol,
        "group.id": (source.get("KAFKA_CONSUMER_GROUP") or "cnc-nifi").strip(),
        "enable.auto.commit": False,
        "auto.offset.reset": (
            source.get("KAFKA_AUTO_OFFSET_RESET") or "earliest"
        ).strip(),
    }
    ca_path = (source.get("KAFKA_CA_CERT_PATH") or "").strip()
    if protocol in {"SSL", "SASL_SSL"} and not ca_path:
        errors.append("KAFKA_CA_CERT_PATH is required for TLS protocols")
    if ca_path:
        config["ssl.ca.location"] = ca_path
    mechanism = (source.get("KAFKA_SASL_MECHANISM") or "").strip()
    username = source.get("KAFKA_SASL_USERNAME") or ""
    password = source.get("KAFKA_SASL_PASSWORD") or ""
    if protocol.startswith("SASL_"):
        if not mechanism:
            errors.append("KAFKA_SASL_MECHANISM is required for SASL protocols")
        else:
            config["sasl.mechanism"] = mechanism
        if not username or not password:
            errors.append("KAFKA_SASL_USERNAME/PASSWORD are required for SASL")
        else:
            config["sasl.username"] = username
            config["sasl.password"] = password
    return {"config": config, "errors": errors}


def redacted_config_for_log(config: dict[str, object]) -> dict[str, object]:
    """Return a log-safe copy of a Kafka config with secrets masked."""
    safe = dict(config)
    for key in ("sasl.password", "sasl.oauthbearer.token", "ssl.key.password"):
        if key in safe:
            safe[key] = "***REDACTED***"
    return safe
