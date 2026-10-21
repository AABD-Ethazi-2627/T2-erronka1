"""Offline reconciliation of the five RESTORE deliveries; no runtime side effects."""

import hashlib
import json

SCENARIOS = ("2xx", "422", "5xx", "timeout", "invalid")
HTTP = "InvokeHTTP — local CG14 mock only"
RETRY = "RouteOnAttribute — max two retries"
COUNT = "UpdateAttribute — count mock retries"
ROUTE = "RouteOnAttribute — accepted or rejected"
ORIGINAL = "Local HTTP original sink — attributes only"
DLQ = "DLQ — durable local file sink"


def content_hash(body):
    return hashlib.sha256(
        json.dumps(
            body,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode()
    ).hexdigest()


def dlq_summary(name, raw):
    """Keep hashes and source references, never private CSV bytes in evidence."""
    body = json.loads(raw)
    source = body.get("source", {})
    original = source.get("raw_record")
    return {
        "name": name,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "body_sha256": content_hash(body),
        "event_id": body.get("event_id"),
        "valid": body.get("valid"),
        "code": body.get("code"),
        "source": {k: source.get(k) for k in ("kind", "uri", "record_ref")},
        "raw_sha256": hashlib.sha256(original.encode()).hexdigest()
        if isinstance(original, str)
        else None,
    }


def reconciled(e, inv):
    """Fail closed on incomplete, misassigned or malformed collected evidence."""
    try:
        return _reconciled(e, inv)
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError, IndexError):
        return False


def _reconciled(e, inv):
    names = {p["name"]: p["instanceIdentifier"] for p in inv["processors"]}
    owned = set(names.values())
    if not owned or set(e["processors"]) != owned:
        return False
    expected = e["expected_deliveries"]
    if len(expected) != 5 or [d["scenario"] for d in expected] != list(SCENARIOS):
        return False
    if (
        e["provenance_complete"] is not True
        or e["original_unchanged"] is not True
        or e["queue"] != 0
    ):
        return False
    if e["service_state"] != "DISABLED" or any(
        p["state"] != "DISABLED" for p in e["processors"].values()
    ):
        return False
    service = inv["controllerServices"][0]["instanceIdentifier"]
    if not any(
        t["component_id"] == service
        and t["state"] == "ENABLED"
        and t["validation"] == "VALID"
        for t in e["transitions"]
    ):
        return False
    active = {
        p["instanceIdentifier"]
        for p in inv["processors"]
        if not p["type"].endswith("GenerateFlowFile")
        and p["name"] != "Unused Groovy API probe — no input"
    }
    if any(
        not any(
            t["component_id"] == cid
            and t["state"] == "RUNNING"
            and t["validation"] == "VALID"
            for t in e["transitions"]
        )
        for cid in active
    ):
        return False
    if len(e["dlq"]) != 4 or len({f["name"] for f in e["dlq"]}) != 4:
        return False
    ids = [d["event_id"] for d in expected[:4]]
    if len(set(ids)) != 4 or any(not isinstance(i, str) or len(i) != 64 for i in ids):
        return False
    matched_files = set()
    seen = set()
    event_ids = [r["event_id"] for r in e["provenance"]]
    if len(event_ids) != len(set(event_ids)):
        return False
    for offset, d in enumerate(expected):
        # Topic is exclusive, one partition, initially empty; producer never retries.
        coordinate = (e["topic"], "0", str(offset))
        if tuple(d[k] for k in ("topic", "partition", "offset")) != coordinate:
            return False
        if d["record_ref"] != "/".join(coordinate):
            return False
        rows = []
        for row in e["provenance"]:
            a = row["attributes"]
            if (
                tuple(
                    a.get(k) for k in ("kafka.topic", "kafka.partition", "kafka.offset")
                )
                == coordinate
            ):
                if row["component_id"] not in owned:
                    return False
                rows.append(row)
                seen.add(coordinate)
                if a.get("cg14.mock.scenario") != (
                    "2xx" if d["scenario"] == "invalid" else d["scenario"]
                ):
                    return False
                if a.get("cg14.event.id") not in (None, "", d["event_id"]):
                    return False
                if int(a.get("cg14.http.attempt") or 0) not in range(4):
                    return False

        rows.sort(key=lambda r: r["event_id"])

        def at(name, event_type, relationship=None, rows=rows):
            return [
                r
                for r in rows
                if r["component_id"] == names[name]
                and r["type"] == event_type
                and (relationship is None or r.get("relationship") == relationship)
            ]

        if d["scenario"] == "invalid":
            if d["event_id"] is not None or at(HTTP, "ROUTE"):
                return False
            invalid = at(ROUTE, "ROUTE", "rejected")
            if not any(
                r["attributes"].get("cg14.valid") == "false"
                and r["attributes"].get("cg14.code") == "MALFORMED_CSV"
                for r in invalid
            ):
                return False
            terminal_after = max(r["event_id"] for r in invalid)
        else:
            http = at(HTTP, "ROUTE")
            relation = {
                "2xx": "Original",
                "422": "No Retry",
                "5xx": "Retry",
                "timeout": "Failure",
            }[d["scenario"]]
            expected_attempts = (
                {0, 1, 2} if d["scenario"] in ("5xx", "timeout") else {0}
            )
            relevant = [r for r in http if r.get("relationship") == relation]
            if [
                int(r["attributes"].get("cg14.http.attempt") or 0) for r in relevant
            ] != sorted(expected_attempts):
                return False
            allowed = {relation, "Response"} if d["scenario"] == "2xx" else {relation}
            if any(r.get("relationship") not in allowed for r in http):
                return False
            # A successful observation for another delivery cannot satisfy this one.
            for r in relevant:
                a = r["attributes"]
                if a.get("cg14.event.id") != d["event_id"]:
                    return False
                if d["scenario"] == "timeout":
                    if "Timeout" not in (
                        a.get("invokehttp.java.exception.class") or ""
                    ):
                        return False
                elif (
                    a.get("invokehttp.status.code")
                    != {"2xx": "200", "422": "422", "5xx": "503"}[d["scenario"]]
                ):
                    return False
            if d["scenario"] in ("5xx", "timeout"):
                if [
                    int(r["attributes"].get("cg14.http.attempt") or 0)
                    for r in at(COUNT, "ATTRIBUTES_MODIFIED")
                ] != [1, 2, 3]:
                    return False
                if not any(
                    r["attributes"].get("cg14.http.attempt") == "3"
                    for r in at(RETRY, "ROUTE", "exhausted")
                ):
                    return False
                counts = at(COUNT, "ATTRIBUTES_MODIFIED")
                if any(
                    not relevant[i]["event_id"] < counts[i]["event_id"]
                    for i in range(3)
                ) or any(
                    not counts[i]["event_id"] < relevant[i + 1]["event_id"]
                    for i in range(2)
                ):
                    return False
                if not any(
                    r["event_id"] > counts[-1]["event_id"]
                    for r in at(RETRY, "ROUTE", "exhausted")
                ):
                    return False
                terminal_after = max(
                    r["event_id"] for r in at(RETRY, "ROUTE", "exhausted")
                )
            else:
                terminal_after = relevant[-1]["event_id"]
            if d["scenario"] == "2xx":
                if not any(
                    r["event_id"] > terminal_after for r in at(ORIGINAL, "DROP")
                ) or at(DLQ, "SEND"):
                    return False
                continue
        sends = at(DLQ, "SEND")
        if not sends or not any(r["event_id"] > terminal_after for r in sends):
            return False
        files = [f for f in e["dlq"] if f["source"]["record_ref"] == d["record_ref"]]
        if len(files) != 1:
            return False
        f = files[0]
        if f["name"] in matched_files or not any(
            r["attributes"].get("filename") == f["name"] for r in sends
        ):
            return False
        matched_files.add(f["name"])
        if (
            f["event_id"] != d["event_id"]
            or f["source"] != d["source"]
            or f["raw_sha256"] != d["raw_sha256"]
        ):
            return False
        if d["scenario"] == "invalid":
            if f["valid"] is not False or f["code"] != "MALFORMED_CSV":
                return False
        elif f["body_sha256"] != d["body_sha256"]:
            return False
    # Reject unrelated deliveries from the same exclusive topic.
    coordinates = {
        tuple(
            r["attributes"].get(k)
            for k in ("kafka.topic", "kafka.partition", "kafka.offset")
        )
        for r in e["provenance"]
    }
    return coordinates == seen and len(seen) == 5 and len(matched_files) == 4
