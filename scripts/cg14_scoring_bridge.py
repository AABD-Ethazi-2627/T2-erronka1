"""Prepare a CG14 normalized event for scoring, without network or model I/O."""

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from scoring.score_api import Telemetry

MAX_INPUT_BYTES = 32768


def to_telemetry(event, *, expected_source_kind=None, source_kind=None):
    """Keep identity; separate raw audit data from the strict inference envelope.

    The caller retains the original CG14 envelope in its audit/archive path.
    A source alias is accepted only when both its exact input and target kind
    are explicitly configured. This is serialization, not identity migration.
    Unknown fields and invalid measurements still fail the API's own validator.
    """
    if not isinstance(event, dict) or not isinstance(event.get("source"), dict):
        raise TypeError("Expected a CG14 event with source metadata")
    if (expected_source_kind is None) != (source_kind is None):
        raise ValueError("Source mapping requires both input and target kinds")
    source = dict(event["source"])
    if "raw_record" in source:
        raw = source.pop("raw_record")
        if not isinstance(raw, str) or not raw:
            raise ValueError("CG14 raw_record must be non-empty text")
    if expected_source_kind is not None:
        if not expected_source_kind or source.get("kind") != expected_source_kind:
            raise ValueError("CG14 source kind differs from the configured input")
        source["kind"] = source_kind
    try:
        return Telemetry.model_validate({**event, "source": source}).model_dump()
    except ValidationError:
        # Pydantic's default diagnostic includes rejected values, possibly raw
        # data or labels. Keep the CLI and callers' diagnostics content-free.
        raise ValueError("CG14 event violates the scoring telemetry contract") from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Retained CG14 normalized JSON event")
    parser.add_argument("--expected-source-kind")
    parser.add_argument(
        "--source-kind", choices=("smb_csv", "lab_fixture", "statement_example")
    )
    args = parser.parse_args(argv)
    try:
        with args.input.open("rb") as handle:
            raw = handle.read(MAX_INPUT_BYTES + 1)
        if len(raw) > MAX_INPUT_BYTES:
            raise ValueError("CG14 input exceeds 32768 bytes")
        event = json.loads(raw)
        payload = to_telemetry(
            event,
            expected_source_kind=args.expected_source_kind,
            source_kind=args.source_kind,
        )
    except (OSError, TypeError, ValueError):
        print("CG14 input rejected; no scoring request produced", file=sys.stderr)
        return 1
    print(json.dumps(payload, allow_nan=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
