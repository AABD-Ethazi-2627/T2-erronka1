"""PIT/aggregation contract doubles; not an Elasticsearch performance claim."""

import json
from datetime import timedelta
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from scoring.read_api import create_read_router, utc
from scoring.read_models import ReadScope
from scoring.read_storage import ElasticsearchReader

BASE = json.loads(Path("contracts/examples/valid/prediction.json").read_text())
BASE.update(json.loads(Path("contracts/examples/valid/telemetry.json").read_text()))
BASE["alert_level"] = "OK"
SCOPE = ReadScope(
    source_uri=BASE["source"]["uri"],
    model_artifact_sha256=BASE["model_artifact_sha256"],
    policy=BASE["policy"],
)
END = utc("2026-10-16T00:00:00Z")
START = END - timedelta(days=185)


def client(reader):
    app = FastAPI()
    app.include_router(create_read_router(SCOPE, current=reader))
    return TestClient(app)


class ESFixture:
    def __init__(self, rows):
        self.rows = rows
        self.requests = []
        self.count_requests = 0
        self.failure = None

    def handle(self, request):
        self.requests.append(request)
        if request.url.path.endswith("_pit"):
            return httpx.Response(200, json={"id": "pit-0"})
        query = json.loads(request.content)
        if self.failure:
            return httpx.Response(200, json=self.failure)
        filters = query["query"]["bool"]["filter"]
        assert filters[:3] == ElasticsearchReader._filters(SCOPE, START, END)[:3]
        bounds = filters[3]["range"]["timestamp"]
        rows = [
            r
            for r in self.rows
            if utc(bounds["gte"]) <= utc(r["timestamp"]) < utc(bounds["lt"])
        ]
        response = {
            "pit_id": "pit-updated",
            "timed_out": False,
            "_shards": {"failed": 0},
        }
        if "machines" in query.get("aggs", {}):
            assert query["size"] == 0
            machines = query["aggs"]["machines"]
            assert machines["composite"]["size"] == 51
            assert machines["aggs"]["latest"]["top_hits"]["sort"] == [
                {"timestamp": "desc"},
                {"event_id": "asc"},
            ]
            latest = {}
            for row in sorted(
                rows, key=lambda r: (-utc(r["timestamp"]).timestamp(), r["event_id"])
            ):
                latest.setdefault(row["machine_id"], row)
            response["aggregations"] = {
                "machines": {
                    "buckets": [
                        {
                            "key": {"machine": key},
                            "latest": {"hits": {"hits": [{"_source": row}]}},
                        }
                        for key, row in sorted(latest.items())[:51]
                    ]
                },
                "invalid_identity": {"doc_count": 0},
            }
        elif "events" in query.get("aggs", {}):
            assert query["size"] == 0
            assert utc(bounds["gte"]) == END - timedelta(days=1)
            self.count_requests += 1
            ids = sorted({r["event_id"] for r in rows})
            after = query["aggs"]["events"]["composite"].get("after", {}).get("event")
            if after:
                ids = [key for key in ids if key > after]
            # Small pages deliberately exercise continuation independently of size.
            selected = ids[:2]
            events = {
                "buckets": [
                    {
                        "key": {"event": key},
                        "doc_count": sum(r["event_id"] == key for r in rows),
                    }
                    for key in selected
                ]
            }
            if selected:
                events["after_key"] = {"event": selected[-1]}
            response["aggregations"] = {"events": events}
        else:
            ids = filters[-1]["terms"]["event_id"]
            selected = [r for r in rows if r["event_id"] in ids]
            response["hits"] = {
                "hits": []
                if "search_after" in query
                else [
                    {"_source": row, "sort": [row["event_id"], i]}
                    for i, row in enumerate(selected)
                ]
            }
        return httpx.Response(200, json=response)

    def reader(self, **kwargs):
        return ElasticsearchReader(
            "http://es.local",
            "predictions-alias",
            client=httpx.Client(transport=httpx.MockTransport(self.handle)),
            **kwargs,
        )


def test_latest_ties_exact_replays_and_one_pit_for_kpis():
    lower = {**BASE, "event_id": "0" * 64}
    older = {**BASE, "event_id": "1" * 64, "timestamp": "2026-09-01T00:00:00Z"}
    other = {**BASE, "event_id": "2" * 64, "machine_id": "CNC-002"}
    es = ESFixture([BASE, lower, lower, older, other])
    c = client(es.reader())
    result = c.get("/api/kpis", params={"as_of": END.isoformat()})
    assert result.status_code == 200, result.text
    assert result.json()["gertakariak"] == 3
    assert result.json()["guztira"] == 2
    assert result.json()["metadata"]["coverage_basis"] == "latest_per_machine"
    assert es.count_requests == 3
    assert (
        sum(r.method == "POST" and r.url.path.endswith("_pit") for r in es.requests)
        == 1
    )
    assert json.loads(es.requests[-1].content) == {"id": "pit-updated"}
    assert es.requests[-1].method == "DELETE"
    snapshot = c.get("/api/makinak", params={"as_of": END.isoformat()}).json()
    assert snapshot[1]["event_id"] == lower["event_id"]
    assert es.count_requests == 3  # Machine snapshot never counts events.


def test_conflicting_duplicate_in_recent_non_latest_event_is_rejected():
    old = {**BASE, "event_id": "0" * 64, "timestamp": "2026-10-15T00:00:00Z"}
    conflicting = {**old, "rpm": 1}
    es = ESFixture([BASE, old, conflicting])
    assert (
        client(es.reader())
        .get("/api/kpis", params={"as_of": END.isoformat()})
        .status_code
        == 503
    )
    assert es.requests[-1].method == "DELETE"


def test_selected_snapshot_duplicate_conflict_is_rejected():
    es = ESFixture([BASE, {**BASE, "rpm": 1}])
    assert (
        client(es.reader())
        .get("/api/makinak", params={"as_of": END.isoformat()})
        .status_code
        == 503
    )


@pytest.mark.parametrize("failure", [{"timed_out": True}, {"_shards": {"failed": 1}}])
def test_partial_search_closes_pit_and_returns_503(failure):
    es = ESFixture([BASE])
    es.failure = failure
    assert (
        client(es.reader())
        .get("/api/makinak", params={"as_of": END.isoformat()})
        .status_code
        == 503
    )
    assert es.requests[-1].method == "DELETE"


def test_exact_machine_capacity_and_event_page_budget_fail_closed():
    es = ESFixture(
        [
            {**BASE, "event_id": f"{i:064x}", "machine_id": f"CNC-{i:03}"}
            for i in range(51)
        ]
    )
    assert (
        client(es.reader())
        .get("/api/makinak", params={"as_of": END.isoformat()})
        .status_code
        == 503
    )
    es = ESFixture([BASE])
    assert (
        client(es.reader(max_count_pages=1))
        .get("/api/kpis", params={"as_of": END.isoformat()})
        .status_code
        == 503
    )


def test_large_count_transfers_only_keys_and_ignores_185_day_document_count():
    es = ESFixture([BASE])
    pages = 0

    def handler(request):
        nonlocal pages
        body = json.loads(request.content) if request.content else {}
        if "events" not in body.get("aggs", {}):
            return es.handle(request)
        es.requests.append(request)
        assert body["size"] == 0 and "top_hits" not in json.dumps(body)
        assert "cardinality" not in json.dumps(body)
        first = pages * 10000
        pages += 1
        keys = range(first, first + 10000) if pages <= 11 else range(0)
        buckets = [{"key": {"event": f"{i:064x}"}, "doc_count": 1} for i in keys]
        result = {"buckets": buckets}
        if buckets:
            result["after_key"] = buckets[-1]["key"]
        return httpx.Response(
            200,
            json={
                "hits": {"total": {"value": 10000000, "relation": "eq"}},
                "aggregations": {"events": result},
            },
        )

    reader = ElasticsearchReader(
        "http://es.local",
        "predictions-alias",
        max_events=1,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    result = client(reader).get("/api/kpis", params={"as_of": END.isoformat()})
    assert result.status_code == 200, result.text
    assert result.json()["gertakariak"] == 110000
    assert pages == 12
    assert sum("_source" in r.content.decode() for r in es.requests) == 0


def test_empty_snapshot_and_count():
    result = (
        ESFixture([]).reader().snapshot(SCOPE, START, END, include_event_count=True)
    )
    assert result == {"rows": [], "event_count": 0}


def test_nonadvancing_count_page_is_rejected_and_pit_closed():
    es = ESFixture([])

    def handler(request):
        body = json.loads(request.content) if request.content else {}
        if "events" not in body.get("aggs", {}):
            return es.handle(request)
        es.requests.append(request)
        return httpx.Response(
            200,
            json={
                "aggregations": {
                    "events": {
                        "buckets": [{"key": {"event": "0" * 64}, "doc_count": 1}],
                        "after_key": {"event": "0" * 64},
                    }
                }
            },
        )

    reader = ElasticsearchReader(
        "http://es.local",
        "fixture",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert (
        client(reader).get("/api/kpis", params={"as_of": END.isoformat()}).status_code
        == 503
    )
    assert es.requests[-1].method == "DELETE"
