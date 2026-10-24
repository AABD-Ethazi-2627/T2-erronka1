"Own Kibana attached only to this run's ES; raw exports are retained."

import json
import sys

import lab

E, ROOT, S, C = lab.E, lab.ROOT, lab.S, lab.C
stage = sys.argv[1]


def kb(method, path, **kwargs):
    response = lab.client.request(
        method,
        "http://127.0.0.1:" + str(S["kibana_port"]) + path,
        headers={"kbn-xsrf": S["tag"]},
        **kwargs,
    )
    with (E / "kibana-operations.jsonl").open("a") as f:
        f.write(
            json.dumps(
                {
                    "method": method,
                    "path": path,
                    "status": response.status_code,
                    "body": response.text,
                }
            )
            + "\n"
        )
    response.raise_for_status()
    return response


if stage == "kb-start":
    assert "kibana" not in S["ids"]
    S["kibana_port"] = lab.random_port()
    lab.save("state.json", S)
    for name in ("kibana-data", "kibana-runtime"):
        (ROOT / name).mkdir()
    identity = lab.create(
        "kibana",
        "docker.elastic.co/kibana/kibana:9.5.4",
        [
            "--memory=1536m",
            "--publish",
            "127.0.0.1:" + str(S["kibana_port"]) + ":5601",
            "--env",
            "ELASTICSEARCH_HOSTS=http://es:9200",
            "--env",
            "SERVER_HOST=0.0.0.0",
            "--env",
            "TELEMETRY_ENABLED=false",
            "--env",
            "XPACK_SECURITY_ENABLED=false",
            "--env",
            "NODE_OPTIONS=--max-old-space-size=768",
            "--env",
            "TMPDIR=/lab/runtime",
            *lab.bind(ROOT / "kibana-data", "/usr/share/kibana/data"),
            *lab.bind(ROOT / "kibana-runtime", "/lab/runtime"),
        ],
    )
    lab.docker("start", identity)
    lab.wait(
        lambda: (
            lab.client.get(
                "http://127.0.0.1:" + str(S["kibana_port"]) + "/api/status"
            ).status_code
            == 200
        ),
        "Kibana",
        seconds=240,
    )
    lab.save("kibana-status.json", kb("GET", "/api/status").json())
    print("Kibana ready", S["kibana_port"])

elif stage == "kb-search":
    identity = json.loads((E / "same-event.json").read_text())["canonical"]["event_id"]
    obj = {
        "type": "search",
        "id": "cg20-own-discover",
        "attributes": {
            "title": "CG20 · mismo evento canónico · stubs sintéticos",
            "columns": [
                "event_id",
                "source.kind",
                "source.uri",
                "source.record_ref",
                "model_version",
                "failure_score",
                "anomaly_score",
                "alert_level",
                "timestamp",
                "scored_at",
                "_index",
            ],
            "sort": [["timestamp", "desc"]],
            "rowsPerPage": 10,
            "sampleSize": 10,
            "hideChart": True,
            "hideTable": False,
            "isTextBasedQuery": False,
            "grid": {},
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps(
                    {
                        "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index",
                        "query": {
                            "language": "kuery",
                            "query": 'event_id: "' + identity + '"',
                        },
                        "filter": [],
                        "size": 10,
                    }
                )
            },
        },
        "references": [
            {
                "type": "index-pattern",
                "id": "cg20-own-events",
                "name": "kibanaSavedObjectMeta.searchSourceJSON.index",
            }
        ],
    }
    raw = (json.dumps(obj) + "\n").encode()
    (E / "discover-source.ndjson").write_bytes(raw)
    result = kb(
        "POST",
        "/api/saved_objects/_import?overwrite=true",
        files={"file": ("search.ndjson", raw, "application/ndjson")},
    ).json()
    assert result["success"] and result["successCount"] == 1, result
    exported = kb(
        "POST",
        "/api/saved_objects/_export",
        json={
            "objects": [
                {"type": "dashboard", "id": "cg20-own-dashboard"},
                {"type": "search", "id": "cg20-own-discover"},
            ],
            "includeReferencesDeep": True,
            "excludeExportDetails": False,
        },
    ).content
    (E / "kibana-final-runtime-export.ndjson").write_bytes(exported)
    print("Saved Discover and final runtime export")

elif stage == "kb-configure":
    response = json.loads((E / "same-event.json").read_text())["canonical"]
    event_id = response["event_id"]
    query = 'event_id: "' + event_id + '"'
    fields = [
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
    ]
    # ES data, dashboard context and timefilter drive every displayed value.
    marks = []
    for i, field in enumerate(fields):
        expression = (
            json.dumps(field + " = ")
            + " + datum"
            + ("" if field.startswith("_") else "._source")
            + "".join("[" + json.dumps(part) + "]" for part in field.split("."))
        )
        marks.append(
            {
                "type": "text",
                "from": {"data": "event"},
                "encode": {
                    "update": {
                        "x": {"value": 8},
                        "y": {"value": 30 + i * 28},
                        "text": {"signal": expression},
                        "fontSize": {"value": 14},
                        "fill": {"value": "#172b4d"},
                        "description": {"signal": expression},
                    }
                },
            }
        )
    spec = {
        "$schema": "https://vega.github.io/schema/vega/v5.json",
        "width": 1100,
        "height": 450,
        "autosize": "none",
        "background": "#ffffff",
        "config": {"kibana": {"renderer": "svg"}},
        "data": [
            {
                "name": "event",
                "url": {
                    "%context%": True,
                    "%timefield%": "timestamp",
                    "index": S["index"],
                    "body": {"size": 10},
                },
                "format": {"property": "hits.hits"},
            }
        ],
        "marks": marks,
    }
    objects = [
        {
            "type": "index-pattern",
            "id": "cg20-own-events",
            "attributes": {
                "title": S["index"],
                "name": "CG20 mismo evento (stubs sintéticos)",
                "timeFieldName": "timestamp",
            },
            "references": [],
        },
        {
            "type": "visualization",
            "id": "cg20-own-values",
            "attributes": {
                "title": "CG20 · respuesta canónica en ES · modelos stub",
                "description": (
                    "Consulta real del índice propio, mismo e"
                    "vent_id. Sin modelo real ni SLA."
                ),
                "visState": json.dumps(
                    {
                        "title": "CG20 mismo evento",
                        "type": "vega",
                        "aggs": [],
                        "params": {"spec": json.dumps(spec)},
                    }
                ),
                "uiStateJSON": "{}",
                "kibanaSavedObjectMeta": {
                    "searchSourceJSON": json.dumps(
                        {"query": {"query": "", "language": "kuery"}, "filter": []}
                    )
                },
            },
            "references": [],
        },
        {
            "type": "dashboard",
            "id": "cg20-own-dashboard",
            "attributes": {
                "title": "CG20 · API → ES → Kibana · mismo evento",
                "description": (
                    "Ensayo local aislado, datos y modelos si"
                    "ntéticos. Identidad única filtrada; sin "
                    "aceptación académica."
                ),
                "panelsJSON": json.dumps(
                    [
                        {
                            "version": "9.5.4",
                            "type": "visualization",
                            "panelIndex": "1",
                            "panelRefName": "panel_0",
                            "embeddableConfig": {},
                            "gridData": {"x": 0, "y": 0, "w": 48, "h": 20, "i": "1"},
                        }
                    ]
                ),
                "optionsJSON": json.dumps(
                    {"useMargins": True, "syncColors": False, "hidePanelTitles": False}
                ),
                "timeRestore": True,
                "timeFrom": "2026-10-21T00:00:00.000Z",
                "timeTo": "2026-10-23T00:00:00.000Z",
                "kibanaSavedObjectMeta": {
                    "searchSourceJSON": json.dumps(
                        {"query": {"query": query, "language": "kuery"}, "filter": []}
                    )
                },
            },
            "references": [
                {"name": "panel_0", "type": "visualization", "id": "cg20-own-values"}
            ],
        },
    ]
    raw = "".join(
        json.dumps(obj, ensure_ascii=False) + "\n" for obj in objects
    ).encode()
    (E / "kibana-source.ndjson").write_bytes(raw)
    result = kb(
        "POST",
        "/api/saved_objects/_import?overwrite=true",
        files={"file": ("cg20.ndjson", raw, "application/ndjson")},
    ).json()
    assert result["success"] and result["successCount"] == 3, result
    (E / "kibana-import.json").write_text(json.dumps(result, indent=2) + "\n")
    exported = kb(
        "POST",
        "/api/saved_objects/_export",
        json={
            "objects": [
                {"type": "dashboard", "id": "cg20-own-dashboard"},
                {"type": "index-pattern", "id": "cg20-own-events"},
            ],
            "includeReferencesDeep": True,
            "excludeExportDetails": False,
        },
    ).content
    (E / "kibana-runtime-export.ndjson").write_bytes(exported)
    print("Imported/exported", query)
