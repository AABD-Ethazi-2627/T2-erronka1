"Assert raw → canonical HTTP/ledger → worker → Parquet → ES identity."

import hashlib
import json
import sqlite3
from contextlib import closing

import lab
import pyarrow.parquet as pq

E, ROOT, S = lab.E, lab.ROOT, lab.S
result = lab.snapshot("cg20-completed")
assert result["accounting"] == {
    "observed": 5,
    "saved": 4,
    "rejected": 1,
    "pending": 0,
}, result["accounting"]
assert result["offset"] == 5
calls = [
    json.loads(line) for line in (ROOT / "api-calls.jsonl").read_text().splitlines()
]
responses = [
    row for row in calls if row.get("status") == 200 and row["path"] == "/predict"
]
assert len(responses) >= 4
hits = result["es"]["hits"]["hits"]
assert len(hits) == 4
for hit in hits:
    assert any(json.loads(row["body"]) == hit["_source"] for row in responses)
hit = min(hits, key=lambda x: x["_source"]["source"]["record_ref"])
canonical = hit["_source"]
identity = canonical["event_id"]
http = next(row for row in responses if json.loads(row["body"]) == canonical)
with closing(
    sqlite3.connect((ROOT / "api.sqlite3").as_uri() + "?mode=ro", uri=True)
) as con:
    ledger = next(
        json.loads(row[0])
        for row in con.execute("SELECT response FROM scoring_responses")
        if json.loads(row[0])["event_id"] == identity
    )
    event = json.loads(
        con.execute(
            "SELECT payload FROM scoring_events WHERE event_id=?", (identity,)
        ).fetchone()[0]
    )
with closing(
    sqlite3.connect((ROOT / "worker/pipeline.sqlite3").as_uri() + "?mode=ro", uri=True)
) as con:
    job = next(
        row
        for row in con.execute(
            "SELECT id,fingerprint,response,outcome F"
            "ROM jobs WHERE response IS NOT NULL"
        )
        if json.loads(row[2])["event_id"] == identity
    )
    attempts = con.execute(
        "SELECT * FROM attempts WHERE delivery=?",
        (hashlib.sha256(job[0].encode()).hexdigest(),),
    ).fetchall()
key = hashlib.sha256(job[0].encode()).hexdigest()
raw = (ROOT / "worker/raw" / f"{key}.bin").read_bytes()
bound = json.loads((ROOT / "worker/identity" / f"{key}.json").read_bytes())
origin = json.loads((ROOT / "worker/origin" / f"{key}.json").read_bytes())
assert hashlib.sha256(raw).hexdigest() == job[1]
assert raw in (ROOT / "input/normal.csv").read_bytes().splitlines()
assert canonical == ledger == json.loads(job[2]) == json.loads(http["body"])
assert bound["telemetry"] == event
parquet = []
for path in (ROOT / "worker").rglob("*.parquet"):
    rows = pq.read_table(path).to_pylist()
    if any(row.get("event_id") == identity for row in rows):
        parquet.append(
            {
                "path": str(path.relative_to(ROOT)),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "rows": rows,
            }
        )
assert len(parquet) == 2
filtered = lab.es(
    "POST",
    "/" + S["index"] + "/_search",
    json={"query": {"term": {"event_id": identity}}, "size": 10},
).json()
assert (
    filtered["hits"]["total"]["value"] == 1
    and filtered["hits"]["hits"][0]["_source"] == canonical
)
save = {
    "canonical": canonical,
    "http_response": http,
    "canonical_ledger": ledger,
    "worker_response": json.loads(job[2]),
    "es_hit": hit,
    "es_exact_id_query": filtered,
    "source_event": event,
    "identity_binding": bound,
    "origin": origin,
    "raw_utf8": raw.decode(),
    "raw_sha256": job[1],
    "worker_delivery_id": job[0],
    "worker_outcome": job[3],
    "attempts": attempts,
    "parquet": parquet,
    "index": S["index"],
    "accounting": result["accounting"],
    "committed_offset": result["offset"],
    "equality": {
        "http_ledger_worker_es": True,
        "source_identity": True,
        "es_exact_id_count": 1,
    },
    "model_scope": (
        "RiskDouble/AnomalyDouble synthetic stubs only; no real model inference"
    ),
}
(E / "same-event.json").write_text(
    json.dumps(save, indent=2, ensure_ascii=False) + "\n"
)
(E / "api-response.json").write_bytes(http["body"].encode())
(E / "es-source.json").write_text(json.dumps(canonical, indent=2) + "\n")
(E / "raw.csv").write_bytes(raw + b"\n")
(E / "es-query.json").write_text(json.dumps(filtered, indent=2) + "\n")
print(identity, json.dumps(canonical), len(parquet))
