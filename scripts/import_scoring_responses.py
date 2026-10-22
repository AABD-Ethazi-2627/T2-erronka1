"""Validate historical responses by default; explicitly import an offline copy.

No model loading, identity reassignment, inference, or downstream acknowledgement.
All inputs are bounded snapshots; a batch is committed in one SQLite transaction.
"""

import argparse
import hashlib
import json
import math
import os
import re
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

from fastapi.responses import JSONResponse
from jsonschema import ValidationError

from scoring.alert_policy import alert_level
from scoring.response_ledger import InferenceConflict, canonical
from scoring.scope import validate_bundle_scope
from scoring.score_api import Telemetry, json_too_deep
from scripts.validate_contracts import contract_hashes, validators

VERSION = "scoring-response-import.v1"
ROOT = Path(__file__).resolve().parents[1]
SCHEMA = {
    "scoring_events": "event_id TEXT PRIMARY KEY, payload TEXT NOT NULL",
    "scoring_responses": (
        "identity TEXT PRIMARY KEY, configuration TEXT NOT NULL, response TEXT NOT NULL"
    ),
    "scoring_imports": (
        "identity TEXT PRIMARY KEY, body BLOB NOT NULL, evidence TEXT NOT NULL"
    ),
}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    if json_too_deep(raw):
        raise ValueError("JSON nesting exceeds 64")
    result = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs)
    canonical(result)  # Reject NaN/Infinity, including numeric overflow.
    return result


def read(path, limit):
    with path.open("rb") as handle:
        raw = handle.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("Input exceeds size limit")
    return raw


def fields(value, expected):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ValueError("Missing or unknown manifest fields")


def text(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 2048:
        raise ValueError("Explicit nonempty evidence reference required")


def configuration(value):
    validate_bundle_scope(value)
    for key in ("risk_threshold", "anomaly_threshold"):
        if type(value.get(key)) not in (int, float) or not math.isfinite(value[key]):
            raise ValueError("Finite configuration thresholds required")
    if not 0 <= value["risk_threshold"] <= 1 or value.get("policy") not in ("f1", "f2"):
        raise ValueError("Unsupported configuration policy or risk threshold")
    text(value.get("model_version"))
    versions = value.get("versions")
    if not isinstance(versions, dict) or not versions.get("sklearn"):
        raise ValueError("Complete historical runtime versions required")
    for name, version in versions.items():
        text(name)
        text(version)
    files = value.get("files")
    if not isinstance(files, dict) or not {"rf.pkl", "if.pkl"} <= files.keys():
        raise ValueError("Both historical artifact hashes required")
    for fingerprint in files.values():
        if not isinstance(fingerprint, str) or not re.fullmatch(
            "[0-9a-f]{64}", fingerprint
        ):
            raise ValueError("Invalid artifact SHA256")
    return canonical(value)


def snapshot(root, reference):
    fields(reference, ("file", "sha256"))
    text(reference["file"])
    path = (root / reference["file"]).resolve()
    if Path(reference["file"]).is_absolute() or not path.is_relative_to(root):
        raise ValueError("Snapshot must stay inside the bundle directory")
    raw = read(path, 32768)
    if digest(raw) != reference["sha256"]:
        raise ValueError("Snapshot SHA256 mismatch")
    return raw, strict_json(raw)


def prepare(bundle_path, expected_hash, target_configuration):
    raw = read(bundle_path, 4 * 1024 * 1024)
    if digest(raw) != expected_hash:
        raise ValueError("Bundle SHA256 mismatch")
    bundle = strict_json(raw)
    fields(
        bundle,
        ("version", "contracts", "configuration", "configuration_evidence", "entries"),
    )
    if bundle["version"] != VERSION or bundle["contracts"] != contract_hashes():
        raise ValueError("Import version or contract fingerprints differ")
    text(bundle["configuration_evidence"])
    config = configuration(bundle["configuration"])
    if config != configuration(strict_json(read(target_configuration, 32768))):
        raise InferenceConflict(
            "Target configuration differs from historical configuration"
        )
    entries = bundle["entries"]
    if not isinstance(entries, list) or not 1 <= len(entries) <= 1000:
        raise ValueError("Import requires 1..1000 entries")
    schemas = validators(ROOT / "contracts")
    result = []
    for entry in entries:
        fields(entry, ("telemetry", "response", "identity_evidence"))
        _, event = snapshot(bundle_path.resolve().parent, entry["telemetry"])
        body, prediction = snapshot(bundle_path.resolve().parent, entry["response"])
        event = Telemetry.model_validate(event).model_dump()
        schemas["telemetry"].validate(event)
        schemas["prediction"].validate(prediction)
        if any(canonical(prediction.get(k)) != canonical(v) for k, v in event.items()):
            raise InferenceConflict(
                "Historical response differs from normalized telemetry"
            )
        manifest = bundle["configuration"]
        for key in ("model_version", "policy", "risk_threshold", "anomaly_threshold"):
            if canonical(prediction[key]) != canonical(manifest[key]):
                raise InferenceConflict("Historical response configuration differs")
        if prediction["model_artifact_sha256"] != manifest["files"]["rf.pkl"]:
            raise InferenceConflict("Historical response artifact differs")
        if (
            prediction["risk_alert"]
            != (prediction["failure_score"] >= manifest["risk_threshold"])
            or prediction["anomaly_alert"]
            != (prediction["anomaly_score"] >= manifest["anomaly_threshold"])
            or (
                "alert_level" in prediction
                and prediction["alert_level"]
                != alert_level(prediction["failure_score"])
            )
        ):
            raise ValueError("Historical response alert semantics differ")
        evidence = entry["identity_evidence"]
        if not isinstance(evidence, list) or not evidence:
            raise ValueError("Explicit identity evidence required")
        for witness in evidence:
            fields(witness, ("system", "event_id", "reference"))
            text(witness["system"])
            text(witness["reference"])
            if witness["event_id"] != event["event_id"]:
                raise InferenceConflict(
                    "Identity reconciliation requires the same event_id; no retargeting"
                )
        identity = canonical(
            [event["event_id"], manifest["files"]["rf.pkl"], manifest["policy"]]
        )
        record = canonical(
            {
                "bundle_sha256": expected_hash,
                "configuration_evidence": bundle["configuration_evidence"],
                "contracts": bundle["contracts"],
                **entry,
            }
        )
        result.append(
            (
                event["event_id"],
                canonical(event),
                identity,
                config,
                canonical(prediction),
                body,
                record,
            )
        )
    # Detect batch-internal conflicts without relying on insertion order.
    events, responses = {}, {}
    for row in result:
        if row[0] in events and events[row[0]] != row[1]:
            raise InferenceConflict("Batch event identity conflict")
        if row[2] in responses and responses[row[2]] != row:
            raise InferenceConflict("Batch response identity conflict")
        events[row[0]], responses[row[2]] = row[1], row
    return list(responses.values())


def inspect(connection, rows):
    if connection.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
        raise ValueError("Ledger integrity check failed")
    present = {
        r[0]
        for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    if present and not {"scoring_events", "scoring_responses"} <= present:
        raise ValueError("Incomplete or unrelated ledger schema")
    for name in present & SCHEMA.keys():
        expected = [
            (
                part.split()[0],
                part.split()[1],
                "NOT NULL" in part,
                "PRIMARY KEY" in part,
            )
            for part in SCHEMA[name].split(", ")
        ]
        actual = [
            (r[1], r[2], bool(r[3]), bool(r[5]))
            for r in connection.execute(f"PRAGMA table_info({name})")
        ]
        if actual != expected:
            raise ValueError("Incompatible ledger schema")
    pending = []
    for row in rows:
        event_id, payload, identity, config, prediction, body, evidence = row
        old_event = (
            connection.execute(
                "SELECT payload FROM scoring_events WHERE event_id=?", (event_id,)
            ).fetchone()
            if "scoring_events" in present
            else None
        )
        old = (
            connection.execute(
                "SELECT configuration,response FROM scoring_responses WHERE identity=?",
                (identity,),
            ).fetchone()
            if "scoring_responses" in present
            else None
        )
        imported = (
            connection.execute(
                "SELECT body,evidence FROM scoring_imports WHERE identity=?",
                (identity,),
            ).fetchone()
            if "scoring_imports" in present
            else None
        )
        if old_event and old_event != (payload,):
            raise InferenceConflict("Ledger event identity conflict")
        if old and (old != (config, prediction) or not old_event):
            raise InferenceConflict("Ledger response identity conflict")
        if imported:
            if not old or imported != (body, evidence):
                raise InferenceConflict("Ledger imported bytes or evidence conflict")
        else:
            # Never replace bytes already served by the normal API serializer.
            if old and JSONResponse(json.loads(prediction)).body != body:
                raise InferenceConflict("Existing response wire bytes differ")
            pending.append(row)
    return pending


def connect(path, mode):
    return sqlite3.connect(
        path.resolve().as_uri() + "?mode=" + mode, uri=True, timeout=30
    )


def backup_ledger(path, backup):
    if backup.resolve() == path.resolve():
        raise ValueError("Backup must be a separate new file")
    with backup.open("xb"):
        pass
    with (
        closing(connect(path, "ro")) as source,
        closing(sqlite3.connect(backup)) as target,
    ):
        source.backup(target)
        if target.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
            raise ValueError("Backup integrity check failed")
    with backup.open("r+b") as handle:
        os.fsync(handle.fileno())
    # SQLite FULL protects the database transaction; directory sync is POSIX-only.
    if os.name == "posix":
        descriptor = os.open(backup.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def migrate(
    ledger,
    rows,
    *,
    apply=False,
    create=False,
    backup=None,
    checkpoint=lambda stage: None,
):
    ledger = Path(ledger)
    if str(ledger) == ":memory:":
        raise ValueError("Persistent local ledger required")
    suffixes = ("-wal", "-shm") if apply else ("-wal", "-shm", "-journal")
    if any(Path(str(ledger) + suffix).exists() for suffix in suffixes):
        raise ValueError("Offline checkpointed ledger copy required; sidecar present")
    existed = ledger.exists()
    if existed:
        with ledger.open("rb") as handle:
            header = handle.read(100)
        if header.startswith(b"SQLite format 3\x00") and header[18:20] == b"\x02\x02":
            raise ValueError("Offline rollback-journal ledger copy required; WAL mode")
    if apply and not existed:
        if not create:
            raise ValueError("New ledger requires --create-ledger")
        with ledger.open("xb"):
            pass
    with closing(
        connect(ledger, "rw" if apply else "ro")
        if ledger.exists()
        else sqlite3.connect(":memory:")
    ) as con:
        if apply:
            con.execute("PRAGMA synchronous=FULL")
            con.execute("BEGIN IMMEDIATE")
        else:
            con.execute("BEGIN")
        try:
            pending = inspect(con, rows)
            if apply and pending:
                if existed:
                    if backup is None:
                        raise ValueError(
                            "Existing ledger import requires a new --backup"
                        )
                    backup_ledger(ledger, Path(backup))
                for name, columns in SCHEMA.items():
                    con.execute(f"CREATE TABLE IF NOT EXISTS {name} ({columns})")
                for (
                    event_id,
                    payload,
                    identity,
                    config,
                    prediction,
                    body,
                    evidence,
                ) in pending:
                    con.execute(
                        "INSERT OR IGNORE INTO scoring_events VALUES (?,?)",
                        (event_id, payload),
                    )
                    con.execute(
                        "INSERT OR IGNORE INTO scoring_responses VALUES (?,?,?)",
                        (identity, config, prediction),
                    )
                    con.execute(
                        "INSERT INTO scoring_imports VALUES (?,?,?)",
                        (identity, body, evidence),
                    )
                    checkpoint("after_insert")
                checkpoint("before_commit")
                con.commit()
            else:
                con.rollback()
        except BaseException:
            con.rollback()
            raise
    return {
        "mode": "import" if apply else "validate",
        "entries": len(rows),
        "importable": len(pending),
        "duplicate": len(rows) - len(pending),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--bundle-sha256", required=True)
    parser.add_argument(
        "--configuration",
        type=Path,
        required=True,
        help="Explicit target manifest; no artifact loading",
    )
    parser.add_argument(
        "--ledger", type=Path, required=True, help="Offline local ledger copy"
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--validate", "--dry-run", action="store_true", help="Default: no target writes"
    )
    mode.add_argument(
        "--import", dest="apply", action="store_true", help="Explicit atomic import"
    )
    parser.add_argument("--create-ledger", action="store_true")
    parser.add_argument(
        "--backup",
        type=Path,
        help="New SQLite backup required before modifying an existing ledger",
    )
    args = parser.parse_args(argv)
    stage = "bundle snapshots/configuration/identity validation"
    try:
        rows = prepare(args.bundle, args.bundle_sha256, args.configuration)
        stage = "offline ledger conflicts/integrity or backup/transaction"
        result = migrate(
            args.ledger,
            rows,
            apply=args.apply,
            create=args.create_ledger,
            backup=args.backup,
        )
    except (OSError, ValueError, TypeError, sqlite3.Error, ValidationError):
        print(
            f"Import rejected during {stage}; check explicit inputs and permissions",
            file=sys.stderr,
        )
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
