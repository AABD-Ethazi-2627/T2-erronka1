"""Commit canonical inference responses before HTTP success, on local SQLite."""

import json
import sqlite3
from contextlib import closing


class InferenceConflict(ValueError):
    """An existing event or archive identity was reused with different inputs."""


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def response(path, event, manifest, infer, validate):
    """Serialize writers across threads/processes; rollback failed inference.

    The directory must already exist on durable local storage. Never use an
    in-memory database: losing this ledger loses the replay guarantee.
    """
    with closing(sqlite3.connect(path, timeout=30)) as connection:
        with connection:
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS scoring_events "
                "(event_id TEXT PRIMARY KEY, payload TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS scoring_responses "
                "(identity TEXT PRIMARY KEY, configuration TEXT NOT NULL, "
                "response TEXT NOT NULL)"
            )
            payload = canonical(event)
            previous = connection.execute(
                "SELECT payload FROM scoring_events WHERE event_id=?",
                (event["event_id"],),
            ).fetchone()
            if previous and previous[0] != payload:
                raise InferenceConflict("Event identity content conflict")
            # Match the existing archive identity; a new anomaly model, version
            # or threshold alone cannot create a second record under that key.
            identity = canonical(
                [event["event_id"], manifest["files"]["rf.pkl"], manifest["policy"]]
            )
            # Bind the complete startup-validated manifest, including both
            # artifacts and runtime/scope metadata. Conservative by design:
            # even a metadata-only manifest edit requires reconciliation.
            configuration = canonical(manifest)
            previous = connection.execute(
                "SELECT configuration, response FROM scoring_responses "
                "WHERE identity=?",
                (identity,),
            ).fetchone()
            if previous:
                if previous[0] != configuration:
                    raise InferenceConflict("Inference identity configuration conflict")
                result = json.loads(previous[1])
                validate(result)
                if any(result.get(key) != value for key, value in event.items()):
                    raise ValueError("Canonical response differs from telemetry")
            else:
                result = infer()
                validate(result)
                connection.execute(
                    "INSERT OR IGNORE INTO scoring_events VALUES (?, ?)",
                    (event["event_id"], payload),
                )
                connection.execute(
                    "INSERT INTO scoring_responses VALUES (?, ?, ?)",
                    (identity, configuration, canonical(result)),
                )
        # The transaction context commits before the caller can return HTTP 200.
        # Match JSON key order on first success and replay, including nested
        # source fields, so a stable downstream delivery can reuse exact bytes.
        return json.loads(canonical(result))
