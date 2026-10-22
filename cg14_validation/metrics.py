"""In-memory diagnostics for the CG14 validation route (G07).

Pure standard library, thread-safe, no I/O. NiFi mirrors these counters with
its own provenance counters; this module gives the reference semantics and
lets unit tests assert observable behavior (received / valid / rejected by
reason / warnings / publish failures / retries / validation latency).

Only real observations are recorded: there are no simulated or mocked
sources. A fresh :class:`ValidationMetrics` starts at zero.
"""

from __future__ import annotations

import threading
import time
from collections import Counter
from dataclasses import dataclass, field
from math import isfinite
from typing import Self


@dataclass
class ValidationMetrics:
    """Thread-safe counters plus validation-latency statistics (seconds)."""

    received: int = 0
    valid: int = 0
    rejected: int = 0
    rejected_by_code: Counter[str] = field(default_factory=Counter)
    warnings_by_code: Counter[str] = field(default_factory=Counter)
    publish_failures: int = 0
    retries: int = 0
    _latency_total: float = 0.0
    _latency_max: float = 0.0
    _latency_samples: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def observe(self, result) -> None:
        """Record one :class:`ValidationResult` and its warning codes."""
        with self._lock:
            self.received += 1
            if result.valid:
                self.valid += 1
            else:
                self.rejected += 1
                for issue in result.issues:
                    self.rejected_by_code[issue.code or "UNKNOWN"] += 1
            for warning in result.warnings:
                self.warnings_by_code[warning.code or "UNKNOWN"] += 1

    def observe_latency(self, seconds: float) -> None:
        """Record one validation-latency sample (finite, >= 0)."""
        if (
            isinstance(seconds, bool)
            or not isinstance(seconds, float | int)
            or not isfinite(seconds)
            or not (seconds >= 0)
        ):
            raise ValueError("latency sample must be a finite non-negative number")
        sample = float(seconds)
        with self._lock:
            self._latency_total += sample
            self._latency_max = max(self._latency_max, sample)
            self._latency_samples += 1

    def record_publish_failure(self) -> None:
        """Record a failed publish to validated/rejected topics."""
        with self._lock:
            self.publish_failures += 1

    def record_retry(self) -> None:
        """Record one bounded transport retry (transient signals only)."""
        with self._lock:
            self.retries += 1

    def snapshot(self) -> dict[str, object]:
        """Return a point-in-time, JSON-serializable copy of all counters."""
        with self._lock:
            samples = self._latency_samples
            return {
                "received": self.received,
                "valid": self.valid,
                "rejected": self.rejected,
                "rejected_by_code": dict(self.rejected_by_code),
                "warnings_by_code": dict(self.warnings_by_code),
                "publish_failures": self.publish_failures,
                "retries": self.retries,
                "latency_samples": samples,
                "latency_mean_s": (self._latency_total / samples) if samples else 0.0,
                "latency_max_s": self._latency_max,
            }

    def time_validation(self):
        """Context manager measuring one validation for latency stats.

        Usage::

            with metrics.time_validation():
                result = parse_csv_event(line, ...)
            metrics.observe(result)
        """
        return _Timer(self)


class _Timer:
    def __init__(self, metrics: ValidationMetrics) -> None:
        self._metrics = metrics

    def __enter__(self) -> Self:
        self._start = time.perf_counter()
        return self

    def __exit__(self, *exc: object) -> None:
        self._metrics.observe_latency(time.perf_counter() - self._start)
