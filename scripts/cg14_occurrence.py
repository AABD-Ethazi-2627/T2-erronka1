"""Explicit identity migration at the CG14/PR42 boundary, before publication.

Neither legacy parser nor the scoring bridge silently changes persisted IDs.
The caller must durably store the returned sidecar with the original bytes.
This is an offline binding primitive, not a Kafka consumer or an archive ack.
"""

import hashlib
import json
from copy import deepcopy

from scripts.cg14_scoring_bridge import to_telemetry


def bind_occurrence(
    event,
    *,
    namespace,
    topic,
    partition,
    offset,
    delivery_id,
    expected_event_id,
    expected_source_kind=None,
    source_kind=None,
):
    """Bind one *original Kafka record* to a common occurrence and one delivery.

    namespace identifies the source cluster/log generation (not a run alias).
    A transport retry retains its original coordinates, occurrence event_id and
    delivery_id. A new publication of that occurrence may have another delivery
    ID, persisted by its outbox/transport. PR58 owns the IDs of its consumed
    Kafka records; this function never overrides them. Republishing without
    original coordinates is a new occurrence; no raw-content dedup.
    """
    if any(
        not isinstance(v, str) or not v.strip() for v in (namespace, topic, delivery_id)
    ):
        raise ValueError("Namespace, topic and delivery ID are required")
    if any(type(v) is not int or v < 0 for v in (partition, offset)):
        raise ValueError("Partition and offset must be non-negative integers")
    if event.get("event_id") != expected_event_id:
        raise ValueError("Legacy event ID differs from the explicit migration input")
    telemetry = to_telemetry(
        event, expected_source_kind=expected_source_kind, source_kind=source_kind
    )
    coordinate = [namespace, topic, partition, offset]
    material = "cnc.occurrence.v1\n" + json.dumps(
        coordinate, separators=(",", ":"), ensure_ascii=False
    )
    event_id = hashlib.sha256(material.encode()).hexdigest()
    sidecar = {
        "identity_version": "cnc.occurrence.v1",
        "event_id": event_id,
        "delivery_id": delivery_id,
        "legacy_event_id": expected_event_id,
        "legacy_source": deepcopy(event["source"]),
        "origin": {
            "namespace": namespace,
            "topic": topic,
            "partition": partition,
            "offset": offset,
        },
    }
    # Canonical source is independent of parser/run aliases. Keep their original
    # source and ID in the sidecar, never in the strict /predict envelope.
    telemetry["event_id"] = event_id
    telemetry["source"] = {
        "kind": telemetry["source"]["kind"],
        "uri": "kafka://" + namespace + "/" + topic,
        "record_ref": topic + "/" + str(partition) + "/" + str(offset),
    }
    return {"telemetry": to_telemetry(telemetry), "identity": sidecar}
