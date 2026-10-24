"""CG21 local journal driving the CG15 durable sink; no network services."""

import hashlib
import json
import multiprocessing
import os
import sqlite3
from contextlib import closing
from pathlib import Path

from scripts.archive_consumer import consume


class InterruptedDelivery(RuntimeError):
    """The sink committed, but the local source has not acknowledged it."""


class Harness:
    def __init__(self, path):
        self.path = Path(path)
        self.archive = self.path.with_suffix(".archive")
        self.db = sqlite3.connect(self.path)
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS journal (
          offset INTEGER PRIMARY KEY, payload TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'pending', reason TEXT);
        """)

    def send(self, payloads):
        with self.db:
            for payload in payloads:
                self.db.execute("INSERT INTO journal(payload) VALUES (?)", (payload,))

    def drain(
        self,
        *,
        available=True,
        limit=100,
        crash_after_store=False,
        checkpoint=lambda stage: None,
    ):
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("positive integer batch limit required")
        if not available:
            return  # simulated downstream outage: no acknowledgement
        rows = self.db.execute(
            "SELECT offset,payload FROM journal WHERE status='pending' "
            "ORDER BY offset LIMIT ?",
            (limit,),
        ).fetchall()
        for offset, raw in rows:
            delivery = f"cg21/telemetry/{offset}"

            def ack(offset=offset, delivery=delivery):
                # CG15 calls this only after durable files and ledger commit.
                with closing(sqlite3.connect(self.archive / "ledger.sqlite")) as ledger:
                    outcome = ledger.execute(
                        "SELECT outcome FROM deliveries WHERE id=?", (delivery,)
                    ).fetchone()[0]
                with self.db:
                    self.db.execute(
                        "UPDATE journal SET status=?,reason=? WHERE offset=?",
                        (
                            "rejected" if outcome == "rejected" else "accepted",
                            "archive_rejected" if outcome == "rejected" else None,
                            offset,
                        ),
                    )

            def interrupt(stage):
                checkpoint(stage)
                if crash_after_store and stage == "after_commit":
                    raise InterruptedDelivery("committed before source ack")

            try:
                consume(
                    self.archive,
                    [
                        (
                            delivery,
                            "telemetry",
                            raw.encode() if isinstance(raw, str) else raw,
                        )
                    ],
                    ack,
                    interrupt,
                )
            except InterruptedDelivery:
                return

    def report(self):
        counts = dict(
            self.db.execute("SELECT status,count(*) FROM journal GROUP BY status")
        )
        result = {
            key: counts.get(key, 0) for key in ("accepted", "rejected", "pending")
        }
        result["sent"] = self.db.execute("SELECT count(*) FROM journal").fetchone()[0]
        result["stored_unique"] = 0
        result["duplicates"] = 0
        if (self.archive / "ledger.sqlite").is_file():
            with closing(sqlite3.connect(self.archive / "ledger.sqlite")) as ledger:
                result["stored_unique"] = ledger.execute(
                    "SELECT count(*) FROM events"
                ).fetchone()[0]
                result["duplicates"] = ledger.execute(
                    "SELECT count(*) FROM deliveries WHERE outcome='duplicate'"
                ).fetchone()[0]
        result["offset_acknowledged"] = self.db.execute(
            "SELECT coalesce(min(offset)-1,(SELECT count(*) FROM journal)) "
            "FROM journal WHERE status='pending'"
        ).fetchone()[0]
        assert (
            result["sent"]
            == result["accepted"] + result["rejected"] + result["pending"]
        )
        return result

    def close(self):
        self.db.close()


def _interrupt_process(path, stage):
    h = Harness(path)

    def checkpoint(current):
        if current == stage:
            os._exit(73)  # Deliberate process death: no finally/connection cleanup.

    h.drain(checkpoint=checkpoint)
    h.close()


def process_crash_probe(root, stage, raw):
    root.mkdir()
    path = root / "journal.sqlite"
    h = Harness(path)
    h.send([raw])
    h.close()
    child = multiprocessing.get_context("spawn").Process(
        target=_interrupt_process, args=(path, stage)
    )
    child.start()
    child.join(30)
    if child.is_alive():
        child.terminate()
        child.join()
        child.close()
        raise RuntimeError("CG21 crash probe timed out")
    exitcode = child.exitcode
    child.close()
    if exitcode != 73:
        raise RuntimeError(f"CG21 checkpoint not reached: {exitcode}")
    h = Harness(path)
    try:
        before = h.report()
        hashes = {
            str(p.relative_to(h.archive)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in h.archive.rglob("*.parquet")
        }
        h.drain()
        after = h.report()
        preserved = all(
            hashlib.sha256((h.archive / name).read_bytes()).hexdigest() == digest
            for name, digest in hashes.items()
        )
        if (
            not hashes
            or not preserved
            or after["accepted"] != 1
            or before["pending"] != 1
        ):
            raise RuntimeError("CG21 crash/replay reconciliation failed")
        return {
            "checkpoint": stage,
            "child_exitcode": exitcode,
            "before_replay": before,
            "after_replay": after,
            "parquet_sha256_before_replay": hashes,
            "parquet_bytes_preserved": preserved,
        }
    finally:
        h.close()


def run(root):
    root = Path(root)
    path = root / "journal.sqlite"
    if root.exists() and any(root.iterdir()):
        raise ValueError(
            "Use a fresh output directory; existing evidence is never overwritten"
        )
    root.mkdir(parents=True, exist_ok=True)
    event = json.loads(Path("contracts/examples/valid/telemetry.json").read_text())
    missing = dict(event)
    del missing["rpm"]
    second = dict(event, event_id=hashlib.sha256(b"cg21-second").hexdigest())
    h = Harness(path)
    h.send(
        [
            json.dumps(event),
            json.dumps(missing),
            "{bad json",
            json.dumps(event),
            json.dumps(second),
        ]
    )
    snapshots = {"sent": h.report()}
    h.drain(available=False)
    snapshots["outage"] = h.report()
    h.drain(limit=1, crash_after_store=True)
    snapshots["stored_before_ack"] = h.report()
    h.close()
    h = Harness(path)
    snapshots["restart"] = h.report()
    h.drain(limit=2)
    snapshots["backpressure_batch"] = h.report()
    h.drain()
    snapshots["recovered"] = h.report()
    h.drain()
    snapshots["replay_noop"] = h.report()
    h.close()
    crashes = [
        process_crash_probe(root / stage, stage, json.dumps(event))
        for stage in ("after_write", "before_commit", "after_commit")
    ]
    result = {
        "scope": (
            "local SQLite source and real CG15 durable archive; "
            "no NiFi/Kafka/ES acceptance"
        ),
        "snapshots": snapshots,
        "process_crashes": crashes,
    }
    (root / "report.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    print(json.dumps(run(parser.parse_args().output), indent=2))
