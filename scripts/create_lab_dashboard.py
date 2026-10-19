"""Create namespaced local Kibana objects without replacing existing user content."""

import json
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:15601"
INDEX = "cnc-telemetry-lab-v2,cnc-telemetry-smb-v1"


def source(body, prop):
    return {
        "name": "table",
        "url": {
            "%context%": True,
            "%timefield%": "timestamp",
            "index": INDEX,
            "body": body,
        },
        "format": {"property": prop},
    }


def vega(data, marks, scales=None, axes=None):
    return {
        "$schema": "https://vega.github.io/schema/vega/v5.json",
        "autosize": {"type": "fit", "contains": "padding"},
        "padding": 10,
        "data": [data],
        "marks": marks,
        "scales": scales or [],
        "axes": axes or [],
    }


def create():
    client = httpx.Client(base_url=BASE, headers={"kbn-xsrf": "cnc-lab"}, timeout=30)
    dv = {
        "data_view": {
            "id": "cnc-acceptance-v1",
            "name": "CNC Guard · laboratorio y SMB",
            "title": INDEX,
            "timeFieldName": "timestamp",
        }
    }
    existing = client.get("/api/data_views/data_view/cnc-acceptance-v1")
    if existing.status_code == 200:
        view = existing.json()["data_view"]
        if view["title"] != INDEX or view.get("timeFieldName") != "timestamp":
            raise ValueError("Existing data view differs; refusing replacement")
    elif existing.status_code == 404:
        response = client.post("/api/data_views/data_view", json=dv)
        response.raise_for_status()
    else:
        existing.raise_for_status()
    specs = {}
    specs["records"] = (
        "Observaciones conservadas",
        vega(
            source(
                {
                    "size": 0,
                    "aggs": {"summary": {"filters": {"filters": [{"match_all": {}}]}}},
                },
                "aggregations.summary.buckets",
            ),
            [
                {
                    "type": "text",
                    "from": {"data": "table"},
                    "encode": {
                        "update": {
                            "x": {"signal": "width/2"},
                            "y": {"signal": "height/2"},
                            "text": {"field": "doc_count"},
                            "align": {"value": "center"},
                            "baseline": {"value": "middle"},
                            "fontSize": {"value": 56},
                            "fill": {"value": "#3b82f6"},
                        }
                    },
                }
            ],
        ),
    )
    specs["alerts"] = (
        "Eventos con aviso o anomalía",
        vega(
            source(
                {
                    "size": 0,
                    "aggs": {
                        "alerts": {
                            "filter": {
                                "bool": {
                                    "should": [
                                        {
                                            "terms": {
                                                "alert_level": ["AVISO", "CRITICA"]
                                            }
                                        },
                                        {"term": {"anomaly_alert": True}},
                                    ],
                                    "minimum_should_match": 1,
                                }
                            }
                        }
                    },
                },
                "aggregations.alerts",
            ),
            [
                {
                    "type": "text",
                    "from": {"data": "table"},
                    "encode": {
                        "update": {
                            "x": {"signal": "width/2"},
                            "y": {"signal": "height/2"},
                            "text": {"field": "doc_count"},
                            "align": {"value": "center"},
                            "baseline": {"value": "middle"},
                            "fontSize": {"value": 56},
                            "fill": {"value": "#d97706"},
                        }
                    },
                }
            ],
        ),
    )
    for key, title, agg in [
        (
            "volume",
            "Volumen por hora · UTC",
            {
                "date_histogram": {
                    "field": "timestamp",
                    "fixed_interval": "1h",
                    "min_doc_count": 0,
                }
            },
        ),
        (
            "machines",
            "Observaciones por identificador simulado",
            {"terms": {"field": "machine_id", "size": 15}},
        ),
    ]:
        temporal = key == "volume"
        scales = [
            {
                "name": "x",
                "type": "utc" if temporal else "band",
                "domain": {"data": "table", "field": "key"},
                "range": "width",
                "padding": 0.15,
            }
            if not temporal
            else {
                "name": "x",
                "type": "utc",
                "domain": {"data": "table", "field": "key"},
                "range": "width",
            },
            {
                "name": "y",
                "type": "linear",
                "domain": {"data": "table", "field": "doc_count"},
                "range": "height",
                "zero": True,
                "nice": True,
            },
        ]
        marks = [
            {
                "type": "rect",
                "from": {"data": "table"},
                "encode": {
                    "update": {
                        "x": {"scale": "x", "field": "key"},
                        "width": {"value": 5}
                        if temporal
                        else {"scale": "x", "band": 0.85},
                        "y": {"scale": "y", "field": "doc_count"},
                        "y2": {"scale": "y", "value": 0},
                        "fill": {"value": "#3b82f6"},
                        "tooltip": {"signal": "datum"},
                    }
                },
            }
        ]
        specs[key] = (
            title,
            vega(
                source(
                    {"size": 0, "aggs": {"series": agg}}, "aggregations.series.buckets"
                ),
                marks,
                scales,
                [
                    {
                        "orient": "bottom",
                        "scale": "x",
                        "labelAngle": -40,
                        "title": "Fecha UTC" if temporal else "Identificador",
                    },
                    {
                        "orient": "left",
                        "scale": "y",
                        "title": "Registros",
                        "tickMinStep": 1,
                    },
                ],
            ),
        )
    specs["scores"] = (
        "Score experimental por evento · no forecast",
        vega(
            source(
                {
                    "size": 200,
                    "sort": [{"timestamp": "asc"}],
                    "_source": [
                        "timestamp",
                        "failure_score",
                        "machine_id",
                        "source.kind",
                        "alert_level",
                    ],
                },
                "hits.hits",
            ),
            [
                {
                    "type": "symbol",
                    "from": {"data": "table"},
                    "encode": {
                        "update": {
                            "x": {
                                "scale": "x",
                                "signal": "toDate(datum._source.timestamp)",
                            },
                            "y": {"scale": "y", "field": "_source.failure_score"},
                            "size": {"value": 65},
                            "fill": {
                                "signal": "datum._source.source.kind === 'smb_csv' ? '#059669' : '#3b82f6'"
                            },
                            "opacity": {"value": 0.7},
                            "tooltip": {"signal": "datum._source"},
                        }
                    },
                }
            ],
            [
                {
                    "name": "x",
                    "type": "utc",
                    "domain": {"data": "table", "field": "_source.timestamp"},
                    "range": "width",
                },
                {"name": "y", "type": "linear", "domain": [0, 1], "range": "height"},
            ],
            [
                {"orient": "bottom", "scale": "x", "title": "Fecha del evento UTC"},
                {"orient": "left", "scale": "y", "title": "Score RF [0,1]"},
            ],
        ),
    )
    specs["scores"][1]["data"][0]["transform"] = [
        {"type": "formula", "as": "ts", "expr": "toDate(datum._source.timestamp)"}
    ]
    specs["scores"][1]["scales"][0]["domain"]["field"] = "ts"
    prior = (
        {
            o["id"]: o
            for o in map(
                json.loads,
                Path("kibana/acceptance-source.ndjson").read_text().splitlines(),
            )
        }
        if Path("kibana/acceptance-source.ndjson").exists()
        else {}
    )
    panels = []
    references = []
    objects = []
    for i, (key, (title, spec)) in enumerate(specs.items()):
        identifier = "cnc-lab-" + key + "-v1"
        attributes = {
            "title": title,
            "visState": json.dumps(
                {
                    "title": title,
                    "type": "vega",
                    "aggs": [],
                    "params": {"spec": json.dumps(spec)},
                }
            ),
            "uiStateJSON": "{}",
            "description": "Simulación docente. Verde=SMB del simulador; azul=fixture local. Clasificación actual, sin control físico.",
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps(
                    {"query": {"query": "", "language": "kuery"}, "filter": []}
                )
            },
        }
        obj = {
            "type": "visualization",
            "id": identifier,
            "attributes": attributes,
            "references": [],
        }
        response = client.post(
            "/api/saved_objects/visualization/" + identifier,
            json={"attributes": attributes, "references": []},
        )
        if response.status_code == 409:
            old = client.get("/api/saved_objects/visualization/" + identifier).json()
            if old["attributes"].get("visState") != attributes["visState"]:
                if old["attributes"].get("visState") != prior.get(identifier, {}).get(
                    "attributes", {}
                ).get("visState"):
                    raise ValueError(
                        "Existing visualization changed outside this builder; refusing overwrite"
                    )
                update = client.put(
                    "/api/saved_objects/visualization/" + identifier,
                    json={
                        "attributes": attributes,
                        "references": [],
                        "version": old["version"],
                    },
                )
                update.raise_for_status()
        else:
            response.raise_for_status()
        objects.append(obj)
        ref = "panel_" + str(i)
        references.append({"name": ref, "type": "visualization", "id": identifier})
        panels.append(
            {
                "version": "9.5.4",
                "type": "visualization",
                "panelIndex": str(i + 1),
                "panelRefName": ref,
                "embeddableConfig": {},
                "gridData": {
                    "x": (i % 2) * 24,
                    "y": (i // 2) * 12,
                    "w": 24,
                    "h": 12,
                    "i": str(i + 1),
                },
            }
        )
    attributes = {
        "title": "CNC Guard · aceptación de laboratorio",
        "description": "SMB del simulador + fixtures identificadas. Estado actual: sin predicción a24h ni actuación automática. Scores de desarrollo; no probabilidad industrial calibrada.",
        "panelsJSON": json.dumps(panels),
        "optionsJSON": json.dumps({"useMargins": True, "hidePanelTitles": False}),
        "timeRestore": True,
        "timeFrom": "2026-10-15T00:00:00.000Z",
        "timeTo": "2026-10-20T00:00:00.000Z",
        "kibanaSavedObjectMeta": {
            "searchSourceJSON": json.dumps(
                {"query": {"query": "", "language": "kuery"}, "filter": []}
            )
        },
    }
    response = client.post(
        "/api/saved_objects/dashboard/cnc-lab-acceptance-v1",
        json={"attributes": attributes, "references": references},
    )
    if response.status_code != 409:
        response.raise_for_status()
    objects.append(
        {
            "type": "dashboard",
            "id": "cnc-lab-acceptance-v1",
            "attributes": attributes,
            "references": references,
        }
    )
    Path("kibana/acceptance-source.ndjson").write_text(
        "\n".join(json.dumps(o) for o in objects) + "\n"
    )
    export = client.post(
        "/api/saved_objects/_export",
        json={
            "objects": [{"type": "dashboard", "id": "cnc-lab-acceptance-v1"}],
            "includeReferencesDeep": True,
        },
    )
    export.raise_for_status()
    Path("kibana/acceptance-export.ndjson").write_bytes(export.content)
    client.close()
    print("Created local dashboard and exported actual saved objects")


if __name__ == "__main__":
    create()
