"""Verify the captured CG20 raw/API/ES/Kibana evidence without live services."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/evidence/CG20_SAME_EVENT_20261022"


def read(name):
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    evidence = read("same-event.json")
    canonical = evidence["canonical"]
    require(
        canonical
        == read("api-response.json")
        == read("es-source.json")
        == evidence["canonical_ledger"]
        == evidence["worker_response"]
        == evidence["es_hit"]["_source"],
        "Canonical HTTP/ledger/worker/ES responses differ",
    )
    query = read("es-query.json")
    require(query["hits"]["total"]["value"] == 1, "ES identity is not unique")
    for field in ("_index", "_id", "_source"):
        require(
            query["hits"]["hits"][0][field] == evidence["es_hit"][field],
            f"ES exact identity query differs: {field}",
        )
    raw = (EVIDENCE / "raw.csv").read_bytes().removesuffix(b"\n")
    require(
        hashlib.sha256(raw).hexdigest() == evidence["raw_sha256"],
        "Raw input fingerprint differs",
    )
    require(
        raw in (EVIDENCE / "lab-01/input/normal.csv").read_bytes().splitlines(),
        "Raw occurrence absent from source file",
    )
    require(
        evidence["identity_binding"]["telemetry"] == evidence["source_event"],
        "Occurrence binding differs from API event",
    )
    require(
        evidence["accounting"]
        == {"observed": 5, "saved": 4, "rejected": 1, "pending": 0}
        and evidence["committed_offset"] == 5,
        "Automatic source accounting differs",
    )
    require(len(evidence["parquet"]) == 2, "Expected both archived streams")
    values = read("dashboard-verified-values.json")
    for field in (
        "event_id",
        "source.kind",
        "source.uri",
        "source.record_ref",
        "machine_id",
        "model_version",
        "failure_score",
        "risk_alert",
        "anomaly_score",
        "anomaly_alert",
        "alert_level",
        "timestamp",
        "scored_at",
        "_index",
        "_id",
    ):
        value = evidence["es_hit"] if field.startswith("_") else canonical
        for component in field.split("."):
            value = value[component]
        displayed = str(value).lower() if isinstance(value, bool) else str(value)
        require(f"{field} = {displayed}" in values, f"Kibana mismatch: {field}")
    row = read("discover-visible-row.json")
    require(len(row["rows"]) == 1, "Discover must display exactly one row")
    for value in (
        canonical["event_id"],
        canonical["source"]["uri"],
        canonical["source"]["record_ref"],
        canonical["model_version"],
        str(canonical["failure_score"]),
        str(canonical["anomaly_score"]),
        canonical["alert_level"],
        evidence["es_hit"]["_index"],
    ):
        require(value in row["rows"][0], f"Discover value missing: {value}")
    negative = (EVIDENCE / "discover-negative.ax.txt").read_text(encoding="utf-8")
    require("No results match your search" in negative, "Negative filter not empty")
    require(
        "0" * 64 in negative
        and "text mark event_id ="
        not in (EVIDENCE / "dashboard-negative.ax.txt").read_text(encoding="utf-8"),
        "Negative identity filter evidence differs",
    )
    print(
        "CG20 same-event evidence verified:",
        canonical["event_id"],
        "HTTP=ledger=worker=ES; Kibana panel/Discover; negative filter; 5=4+1+0",
    )


if __name__ == "__main__":
    main()
