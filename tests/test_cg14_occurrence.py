"""Identity migration is explicit and preserves legacy audit data."""

import hashlib
from copy import deepcopy
from pathlib import Path

import pytest

from cg14_validation.validator import parse_csv_event
from scripts.cg14_occurrence import bind_occurrence
from scripts.cg14_scoring_bridge import to_telemetry


def legacy():
    raw = (Path(__file__).parent / "fixtures/cg14/valid_event.csv").read_text().strip()
    return parse_csv_event(
        raw,
        source_uri="kafka://old/topic",
        record_ref="topic/0/12",
        source_kind="cg14-lab-kafka",
    ).normalized_event


def bind(event, *, offset=12, delivery="delivery-a", source="cg14-lab-kafka"):
    return bind_occurrence(
        event,
        namespace="lab-cluster-generation1",
        topic="topic",
        partition=0,
        offset=offset,
        delivery_id=delivery,
        expected_event_id=event["event_id"],
        expected_source_kind=source,
        source_kind="lab_fixture",
    )


def test_two_legacy_routes_bind_same_occurrence_without_mutation():
    cg14 = legacy()
    before = deepcopy(cg14)
    pr42 = to_telemetry(
        cg14, expected_source_kind="cg14-lab-kafka", source_kind="lab_fixture"
    )
    # PR42 uses sha256(Filebeat key). This emulates that documented legacy input,
    # not a claim to have run Filebeat or either Groovy script.
    pr42["event_id"] = hashlib.sha256(b"filebeat-fingerprint:offset").hexdigest()
    pr42["source"]["record_ref"] = "filebeat-fingerprint:offset"
    a = bind(cg14)
    b = bind(pr42, source="lab_fixture")
    assert a["telemetry"] == b["telemetry"]
    assert a["identity"]["legacy_event_id"] == cg14["event_id"]
    assert b["identity"]["legacy_event_id"] == pr42["event_id"]
    assert cg14 == before
    a["identity"]["legacy_source"]["raw_record"] = "changed"
    assert cg14 == before


def test_transport_replay_and_two_equal_occurrences():
    event = legacy()
    a, replay = bind(event), bind(event)
    assert a["telemetry"] == replay["telemetry"]
    assert a["identity"] == replay["identity"]
    republished = bind(event, delivery="new-publication")
    assert republished["telemetry"] == a["telemetry"]
    assert republished["identity"]["delivery_id"] != a["identity"]["delivery_id"]
    assert bind(event, offset=13)["telemetry"]["event_id"] != a["telemetry"]["event_id"]
    assert event["event_id"] != a["telemetry"]["event_id"]


@pytest.mark.parametrize(
    "changes",
    [
        {"namespace": ""},
        {"topic": ""},
        {"partition": True},
        {"offset": -1},
        {"delivery_id": ""},
        {"expected_event_id": "unexpected"},
    ],
)
def test_missing_or_inconsistent_identity_is_rejected(changes):
    event = legacy()
    args = {
        "namespace": "lab",
        "topic": "topic",
        "partition": 0,
        "offset": 12,
        "delivery_id": "a",
        "expected_event_id": event["event_id"],
        "expected_source_kind": "cg14-lab-kafka",
        "source_kind": "lab_fixture",
    }
    args.update(changes)
    with pytest.raises(ValueError):
        bind_occurrence(event, **args)
