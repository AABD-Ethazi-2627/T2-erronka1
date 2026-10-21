"""CG21 deterministic local fixture: SQLite journal, never contacts lab services."""

import hashlib
import json
import sqlite3
from pathlib import Path

from scoring.score_api import Telemetry


class Harness:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS journal (
          offset INTEGER PRIMARY KEY, payload TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'pending', reason TEXT);
        CREATE TABLE IF NOT EXISTS stored (event_id TEXT PRIMARY KEY, payload TEXT);
        """)

    def send(self, payloads):
        with self.db:
            for payload in payloads:
                self.db.execute("INSERT INTO journal(payload) VALUES (?)", (payload,))

    def drain(self, *, available=True, limit=100, crash_after_store=False):
        if not available:
            return  # simulated downstream outage: no acknowledgement
        rows = self.db.execute(
            "SELECT offset,payload FROM journal WHERE status='pending' "
            "ORDER BY offset LIMIT ?",
            (limit,),
        ).fetchall()
        for offset, raw in rows:
            try:
                event = Telemetry.model_validate(json.loads(raw)).model_dump()
            except (ValueError, TypeError):
                with self.db:
                    self.db.execute(
                        "UPDATE journal SET status='rejected',reason='invalid' "
                        "WHERE offset=?",
                        (offset,),
                    )
                continue
            # Separate durable write and acknowledgement expose the replay window.
            with self.db:
                self.db.execute(
                    "INSERT OR IGNORE INTO stored VALUES (?,?)",
                    (event["event_id"], json.dumps(event, sort_keys=True)),
                )
            if crash_after_store:
                return
            with self.db:
                self.db.execute(
                    "UPDATE journal SET status='accepted' WHERE offset=?", (offset,)
                )

    def report(self):
        counts = dict(
            self.db.execute("SELECT status,count(*) FROM journal GROUP BY status")
        )
        result = {
            key: counts.get(key, 0) for key in ("accepted", "rejected", "pending")
        }
        result["sent"] = self.db.execute("SELECT count(*) FROM journal").fetchone()[0]
        result["stored_unique"] = self.db.execute(
            "SELECT count(*) FROM stored"
        ).fetchone()[0]
        result["offset_acknowledged"] = self.db.execute(
            "SELECT coalesce(min(offset)-1,(SELECT count(*) FROM journal)) "
            "FROM journal WHERE status='pending'"
        ).fetchone()[0]
        result["duplicates"] = max(0, result["accepted"] - result["stored_unique"])
        assert (
            result["sent"]
            == result["accepted"] + result["rejected"] + result["pending"]
        )
        return result

    def close(self):
        self.db.close()


def run(root):
    path = root / "journal.sqlite"
    if path.exists() or (root / "report.json").exists():
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
    result = {
        "scope": "local SQLite fixture; no NiFi/Kafka/ES acceptance",
        "snapshots": snapshots,
    }
    (root / "report.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    print(json.dumps(run(parser.parse_args().output), indent=2))
