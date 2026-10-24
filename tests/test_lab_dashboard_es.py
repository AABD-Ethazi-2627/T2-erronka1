"""Opt-in queries on a disposable ES with an explicitly verified cluster UUID."""

import copy
import json
import os
import unittest

import httpx

from scripts.create_lab_dashboard import (
    INDEX,
    ROOT,
    recent_search,
    summary_spec,
    temperature_spec,
)


@unittest.skipUnless(
    os.getenv("CG19_ES_URL") and os.getenv("CG19_ES_UUID"),
    "Disposable CG19 ES not configured",
)
class DashboardESQueries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = httpx.Client(base_url=os.environ["CG19_ES_URL"], timeout=30)
        cls.addClassCleanup(cls.client.close)
        cluster = cls.client.get("/")
        cluster.raise_for_status()
        if cluster.json()["cluster_uuid"] != os.environ["CG19_ES_UUID"]:
            raise ValueError("Refusing writes: disposable cluster UUID mismatch")
        mapping = json.loads((ROOT / "elasticsearch/index-template.json").read_text())[
            "template"
        ]["mappings"]
        for index in INDEX.split(","):
            if cls.client.head("/" + index).status_code != 404:
                raise ValueError("Refusing to reuse an existing fixture index")
            response = cls.client.put("/" + index, json={"mappings": mapping})
            response.raise_for_status()
        cls.events = []
        for i in range(60):
            event = {
                "event_id": f"{i:064x}",
                "machine_id": f"CNC-{i % 2:03d}",
                "timestamp": f"2026-10-21T{0 if i < 30 else 2:02d}:00:00Z",
                "source": {"kind": "lab_fixture" if i % 2 == 0 else "smb_csv"},
                "air_temp_K": 300.0 + i,
                "process_temp_K": 310.0 + i,
                "alert_level": ["OK", "AVISO", "CRITICA"][i % 3],
            }
            if i == 59:
                del event["alert_level"]
            cls.events.append(event)
        bulk = []
        for event in cls.events:
            index = INDEX.split(",")[event["source"]["kind"] == "smb_csv"]
            bulk.extend(
                [
                    json.dumps({"index": {"_index": index, "_id": event["event_id"]}}),
                    json.dumps(event),
                ]
            )
        result = cls.client.post(
            "/_bulk?refresh=true",
            content="\n".join(bulk) + "\n",
            headers={"Content-Type": "application/x-ndjson"},
        )
        result.raise_for_status()
        if result.json()["errors"]:
            raise ValueError(result.json())

    def query(self, body, filters=None):
        body = copy.deepcopy(body)
        body["query"] = {
            "bool": {
                "filter": [
                    {
                        "range": {
                            "timestamp": {
                                "gte": "2026-10-21T00:00:00Z",
                                "lte": "2026-10-21T03:00:00Z",
                            }
                        }
                    },
                    *(filters or []),
                ]
            }
        }
        response = self.client.post("/" + INDEX + "/_search", json=body)
        response.raise_for_status()
        return response.json()

    def test_summary_denominators_filter_and_empty_window(self):
        body = summary_spec()["data"][0]["url"]["body"]
        for filters, count, classified, alerts, machines in [
            ([], 60, 59, 39, 2),
            ([{"term": {"machine_id": "CNC-000"}}], 30, 30, 20, 1),
            ([{"term": {"alert_level": "AVISO"}}], 20, 20, 20, 2),
            ([{"term": {"machine_id": "CNC-999"}}], 0, 0, 0, 0),
        ]:
            bucket = self.query(body, filters)["aggregations"]["summary"]["buckets"][0]
            self.assertEqual(bucket["doc_count"], count)
            self.assertEqual(bucket["classified"]["doc_count"], classified)
            self.assertEqual(bucket["alerts"]["doc_count"], alerts)
            self.assertEqual(bucket["machines"]["value"], machines)
            self.assertEqual(bucket["latest"]["value"] is None, count == 0)

    def test_temperature_hour_gap_sensor_means_and_sources(self):
        result = self.query(temperature_spec()["data"][0]["url"]["body"])
        groups = result["aggregations"]["groups"]
        self.assertEqual(groups["sum_other_doc_count"], 0)
        self.assertEqual(len(groups["buckets"]), 2)
        for group in groups["buckets"]:
            buckets = group["series"]["buckets"]
            self.assertEqual([b["doc_count"] for b in buckets], [15, 0, 15])
            self.assertIsNone(buckets[1]["air"]["value"])
            expected = 314.0 if group["key"][0] == "CNC-000" else 315.0
            self.assertEqual(buckets[0]["air"]["value"], expected)
            self.assertEqual(buckets[0]["process"]["value"], expected + 10)

    def test_recent_query_returns_50_with_stable_ties_and_filter(self):
        attrs = recent_search()["attributes"]
        # This executes the intended ES sort/limit, not Kibana's Discover renderer.
        body = {"size": 50, "sort": [{key: value} for key, value in attrs["sort"]]}
        hits = self.query(body)["hits"]["hits"]
        expected = sorted(
            self.events, key=lambda e: (-int(e["timestamp"][11:13]), e["event_id"])
        )[:50]
        self.assertEqual(
            [h["_source"]["event_id"] for h in hits], [e["event_id"] for e in expected]
        )
        filtered = self.query(body, [{"term": {"machine_id": "CNC-001"}}])["hits"][
            "hits"
        ]
        self.assertEqual(len(filtered), 30)
        self.assertTrue(all(h["_source"]["machine_id"] == "CNC-001" for h in filtered))
