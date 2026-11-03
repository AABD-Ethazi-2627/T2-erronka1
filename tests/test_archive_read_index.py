"""Actual local CG15/index/ASGI regressions; no services, model or network."""

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from scoring.read_models import ReadScope
from scoring.read_storage import ArchiveReader
from scoring.score_api import create_app
from scripts import archive_read_index as index
from scripts.archive_consumer import consume, durable, parquet

BASE = json.loads(Path("contracts/examples/valid/prediction.json").read_text())
BASE.update(json.loads(Path("contracts/examples/valid/telemetry.json").read_text()))
BASE.update(
    alert_level="OK",
    source={"kind": "lab_fixture", "uri": "fixture://indexed", "record_ref": "row"},
)
SCOPE = ReadScope(
    source_uri=BASE["source"]["uri"],
    model_artifact_sha256=BASE["model_artifact_sha256"],
    policy=BASE["policy"],
    risk_threshold=BASE["risk_threshold"],
)
END = "2026-10-16T00:00:00Z"


def prediction(number=0, **changes):
    return {**BASE, "event_id": f"{number:064x}", **changes}


def append(root, number=0, **changes):
    obj = prediction(number, **changes)
    consume(
        root,
        [(f"delivery-{number}", "prediction", json.dumps(obj, indent=2).encode())],
        lambda: None,
    )
    return obj


def get(
    root,
    path="historikoa/CNC-049",
    *,
    max_objects=20000,
    max_bytes=64 * 1024 * 1024,
    **params,
):
    app = create_app(
        read_config={
            "scope": SCOPE,
            "archive": ArchiveReader(
                root, max_objects=max_objects, max_bytes=max_bytes
            ),
        }
    )
    return TestClient(app).get("/api/" + path, params={"as_of": END, **params})


def existing_bytes(root):
    with sqlite3.connect(root / "ledger.sqlite") as con:
        tables = {
            name: con.execute("SELECT * FROM " + name + " ORDER BY 1").fetchall()
            for name in ("objects", "events", "deliveries")
        }
    return tables, {name: (root / name).read_bytes() for name, _ in tables["objects"]}


def drop_index(root):
    """Emulate a legacy archive by removing only the new derived metadata."""
    with sqlite3.connect(root / "ledger.sqlite") as con:
        for name in index.TRIGGERS:
            con.execute("DROP TRIGGER " + name)
        con.execute("DROP TABLE " + index.TABLE)
        con.execute("DROP TABLE " + index.META)


def test_unrelated_retention_does_not_consume_query_budget(tmp_path, monkeypatch):
    append(tmp_path)
    append(tmp_path, 1, timestamp="2020-01-01T00:00:00Z")
    append(tmp_path, 2, source={**BASE["source"], "uri": "fixture://other"})
    append(tmp_path, 3, machine_id="CNC-048")
    append(tmp_path, 4, risk_threshold=0.7)
    telemetry = json.loads(Path("contracts/examples/valid/telemetry.json").read_text())
    consume(
        tmp_path,
        [
            ("telemetry", "telemetry", json.dumps(telemetry).encode()),
            ("rejected", "telemetry", b"bad"),
        ],
        lambda: None,
    )
    # Corrupt an unselected old prediction, after all writes (the writer keeps its
    # separate global integrity gate). The query may use only its two objects.
    old = index.index_values(
        "delivery-1", prediction(1, timestamp="2020-01-01T00:00:00Z")
    )
    (tmp_path / old[1]).write_bytes(b"unrelated old corruption")
    read = index.ObjectBudget.read
    used = []

    def observe(self, root, name, expected):
        used.append(name)
        return read(self, root, name, expected)

    monkeypatch.setattr(index.ObjectBudget, "read", observe)
    result = get(tmp_path, max_objects=2)
    assert result.status_code == 200 and result.json()["metadata"]["count"] == 1
    assert len(used) == 2 and old[1] not in used
    assert (
        get(tmp_path, "historikoa/CNC-049/periodoak", max_objects=2).json()[
            "sei_hilabete"
        ]["metadata"]["count"]
        == 1
    )


def test_selected_capacity_is_still_enforced(tmp_path):
    append(tmp_path)
    assert get(tmp_path, max_objects=2, max_bytes=1).status_code == 503
    append(tmp_path, 1)
    assert get(tmp_path, max_objects=2).status_code == 503


@pytest.mark.parametrize(
    "fault",
    [
        "parquet",
        "bronze",
        "object_receipt",
        "bronze_receipt",
        "event_receipt",
        "delivery_missing",
        "delivery_rejected",
        "delivery_hash",
        "index_scope",
        "index_time",
    ],
)
def test_selected_integrity_and_index_tamper_fail_closed(tmp_path, fault):
    obj = append(tmp_path)
    values = index.index_values("delivery-0", obj)
    if fault in {"parquet", "bronze"}:
        name = values[1] if fault == "parquet" else index.bronze_path("delivery-0")
        (tmp_path / name).write_bytes(b"corrupt")
    else:
        with sqlite3.connect(tmp_path / "ledger.sqlite") as con:
            if fault == "object_receipt":
                con.execute("DELETE FROM objects WHERE path=?", (values[1],))
            elif fault == "bronze_receipt":
                con.execute(
                    "DELETE FROM objects WHERE path=?",
                    (index.bronze_path("delivery-0"),),
                )
            elif fault == "event_receipt":
                con.execute("DELETE FROM events")
            elif fault == "delivery_missing":
                con.execute("DELETE FROM deliveries")
            elif fault == "delivery_rejected":
                con.execute("UPDATE deliveries SET outcome='rejected'")
            elif fault == "delivery_hash":
                con.execute("UPDATE deliveries SET hash='wrong'")
            elif fault == "index_scope":
                con.execute(
                    "UPDATE prediction_read_index SET source_uri='fixture://hidden'"
                )
            elif fault == "index_time":
                con.execute("UPDATE prediction_read_index SET timestamp_us=0")
    assert get(tmp_path).status_code == 503


def test_legacy_and_partial_new_writer_index_require_explicit_backfill(tmp_path):
    append(tmp_path)
    drop_index(tmp_path)
    before = existing_bytes(tmp_path)
    assert get(tmp_path).status_code == 503
    assert existing_bytes(tmp_path) == before  # GET created/changed nothing.
    append(tmp_path, 1)
    assert get(tmp_path).status_code == 503  # New rows cannot hide legacy rows.
    before = existing_bytes(tmp_path)
    assert index.backfill(tmp_path)["predictions"] == 2
    assert existing_bytes(tmp_path) == before
    assert get(tmp_path).json()["metadata"]["count"] == 2
    assert index.backfill(tmp_path)["predictions"] == 2
    assert existing_bytes(tmp_path) == before


def test_orphan_and_rejected_duplicate_are_not_receipt_fallbacks(tmp_path):
    obj = append(tmp_path)
    orphan = tmp_path / "prediction/date=2026-10-15/orphan.parquet"
    orphan.write_bytes(b"not a committed object")
    consume(
        tmp_path,
        [("rejected-copy", "telemetry", json.dumps(obj).encode())],
        lambda: None,
    )
    assert get(tmp_path).json()["metadata"]["count"] == 1
    with sqlite3.connect(tmp_path / "ledger.sqlite") as con:
        con.execute("UPDATE prediction_read_index SET delivery_id='rejected-copy'")
        # Deliberately bypass the dirty tripwire to exercise receipt validation.
        con.execute("UPDATE prediction_read_meta SET dirty=0")
    assert get(tmp_path).status_code == 503


def test_duplicate_keeps_one_noncanonical_accepted_receipt(tmp_path):
    obj = append(tmp_path)
    result = consume(
        tmp_path,
        [("second-copy", "prediction", index.canonical(obj))],
        lambda: None,
    )
    assert result["duplicate"] == 1
    with sqlite3.connect(tmp_path / "ledger.sqlite") as con:
        assert con.execute(
            "SELECT delivery_id FROM prediction_read_index"
        ).fetchall() == [("delivery-0",)]
    assert get(tmp_path, max_objects=2).json()["metadata"]["count"] == 1
    drop_index(tmp_path)
    before = existing_bytes(tmp_path)
    assert index.backfill(tmp_path)["predictions"] == 1
    assert existing_bytes(tmp_path) == before
    assert get(tmp_path, max_objects=2).json()["metadata"]["count"] == 1


@pytest.mark.parametrize("checkpoint", ["before_commit", "after_commit"])
def test_index_rollback_and_replay_follow_archive_commit(tmp_path, checkpoint):
    obj = prediction()
    messages = [("delivery-0", "prediction", json.dumps(obj, indent=2).encode())]

    def crash(stage):
        if stage == checkpoint:
            raise RuntimeError("injected crash boundary")

    with pytest.raises(RuntimeError, match="crash"):
        consume(tmp_path, messages, lambda: None, checkpoint=crash)
    with sqlite3.connect(tmp_path / "ledger.sqlite") as con:
        count = con.execute("SELECT count(*) FROM prediction_read_index").fetchone()[0]
        assert count == (checkpoint == "after_commit")
        state = con.execute(
            "SELECT objects_count, entries_count FROM prediction_read_meta"
        ).fetchone()
        assert state == (count, count)
    result = consume(tmp_path, messages, lambda: None)
    assert result["replay"] == (checkpoint == "after_commit")
    assert get(tmp_path).json()["metadata"]["count"] == 1
    before = existing_bytes(tmp_path)
    consume(tmp_path, messages, lambda: None)
    assert existing_bytes(tmp_path) == before


def test_old_writer_append_is_detected_and_can_be_backfilled(tmp_path):
    append(tmp_path)
    obj = prediction(1)
    raw = json.dumps(obj, indent=4).encode()
    values = index.index_values("older-writer", obj)
    body = {key: obj[key] for key in ("event_id", "machine_id", "timestamp")}
    body["payload_json"] = index.canonical(obj).decode()
    data = {index.bronze_path("older-writer"): raw, values[1]: parquet(body)}
    for name, payload in data.items():
        durable(tmp_path / name, payload)
    with sqlite3.connect(tmp_path / "ledger.sqlite") as con:
        # Original writer's three-table commit, without the additive read index.
        con.executemany(
            "INSERT INTO objects VALUES (?,?)",
            [(name, index.digest(payload)) for name, payload in data.items()],
        )
        con.execute("INSERT INTO events VALUES (?,?)", (values[0], values[3]))
        con.execute(
            "INSERT INTO deliveries VALUES (?,?,?)",
            ("older-writer", index.digest(b"prediction\0" + raw), "stored"),
        )
    assert get(tmp_path).status_code == 503
    assert index.backfill(tmp_path)["predictions"] == 2
    assert get(tmp_path).json()["metadata"]["count"] == 2


def test_missing_trigger_is_not_silently_restored_as_complete(tmp_path):
    append(tmp_path)
    with sqlite3.connect(tmp_path / "ledger.sqlite") as con:
        con.execute("DROP TRIGGER cg15_read_object_insert")
    assert get(tmp_path).status_code == 503
    append(tmp_path, 1)
    assert get(tmp_path).status_code == 503
    assert index.backfill(tmp_path)["predictions"] == 2
    assert get(tmp_path).status_code == 200


def test_object_replacement_cannot_cancel_coverage_counter_mismatch(tmp_path):
    obj = append(tmp_path, timestamp="2020-01-01T00:00:00Z")
    path = index.index_values("delivery-0", obj)[1]
    with sqlite3.connect(tmp_path / "ledger.sqlite") as con:
        con.execute("DELETE FROM objects WHERE path=?", (path,))
        con.execute(
            "INSERT INTO objects VALUES (?,?)",
            ("prediction/date=2026-10-15/unindexed.parquet", "a" * 64),
        )
        assert con.execute(
            "SELECT objects_count, entries_count FROM prediction_read_meta"
        ).fetchone() == (1, 1)
    # Equal totals cannot conceal an unindexed new prediction after a deletion.
    assert get(tmp_path).status_code == 503


def test_backfill_requires_writer_lock_and_preserves_failed_input(tmp_path):
    append(tmp_path)
    drop_index(tmp_path)
    con = sqlite3.connect(tmp_path / "ledger.sqlite")
    try:
        con.execute("BEGIN IMMEDIATE")
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            index.backfill(tmp_path)
    finally:
        con.close()
    (tmp_path / index.bronze_path("delivery-0")).write_bytes(b"corrupt")
    before = existing_bytes(tmp_path)
    with pytest.raises(ValueError, match="corruption"):
        index.backfill(tmp_path)
    assert existing_bytes(tmp_path) == before
    assert get(tmp_path).status_code == 503


def test_microsecond_windows_and_known_empty_machine(tmp_path):
    append(tmp_path, timestamp="2026-10-15T00:00:00Z")
    append(tmp_path, 1, timestamp="2026-10-15T00:00:00.000001Z")
    reply = get(
        tmp_path,
        desde="2026-10-15T00:00:00.000001Z",
        hasta="2026-10-15T00:00:00.000002Z",
    )
    assert reply.status_code == 200 and reply.json()["metadata"]["count"] == 1
    assert reply.json()["metadata"]["events"][0]["event_id"] == f"{1:064x}"
    empty = get(tmp_path, as_of="2026-11-01T00:00:00Z", max_objects=2)
    assert empty.status_code == 200 and empty.json()["metadata"]["count"] == 0
    assert get(tmp_path, "historikoa/CNC-048").status_code == 404
    first = index.instant_us("9999-12-31T23:59:59.999998Z")
    assert index.instant_us("9999-12-31T23:59:59.999999Z") - first == 1
    assert index.instant_us(datetime(1970, 1, 1, tzinfo=UTC)) == 0


def test_cursor_changes_only_with_selected_population(tmp_path):
    append(tmp_path)
    append(tmp_path, 1)
    first = get(tmp_path, limit=1).json()
    cursor = first["next_cursor"]
    append(tmp_path, 2, timestamp="2020-01-01T00:00:00Z")
    assert get(tmp_path, cursor=cursor).status_code == 200
    append(tmp_path, 3)
    assert get(tmp_path, cursor=cursor).status_code == 409
