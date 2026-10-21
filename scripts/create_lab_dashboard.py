"""Generate CG19 Kibana saved objects offline. No service writes or model execution."""

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = "cnc-telemetry-lab-v2,cnc-telemetry-smb-v1"
DASHBOARD_ID = "cnc-cg19-review-v2"
DATA_VIEW_ID = "cnc-cg19-review-data-v2"
OUTPUT = ROOT / "kibana/cg19-review-source.ndjson"
TEMPERATURE_GROUP_LIMIT = 100
TEMPERATURE_PAGE_SIZE = 5


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


def vega(data, marks, **extra):
    return {
        "$schema": "https://vega.github.io/schema/vega/v5.json",
        "autosize": {"type": "fit", "contains": "padding"},
        "padding": 10,
        "data": data if isinstance(data, list) else [data],
        "marks": marks,
        **extra,
    }


def text_mark(expr, y, size=16, data=None):
    mark = {
        "type": "text",
        "encode": {
            "update": {
                "x": {"value": 4},
                "y": {"value": y},
                "text": {"signal": expr},
                "fontSize": {"value": size},
                "fill": {"value": "#333333"},
                "align": {"value": "left"},
                "baseline": {"value": "top"},
            }
        },
    }
    if data:
        mark["from"] = {"data": data}
    return mark


def summary_spec():
    data = source(
        {
            "size": 0,
            "aggs": {
                "summary": {
                    "filters": {"filters": [{"match_all": {}}]},
                    "aggs": {
                        "alerts": {
                            "filter": {"terms": {"alert_level": ["AVISO", "CRITICA"]}}
                        },
                        "classified": {
                            "filter": {
                                "terms": {"alert_level": ["OK", "AVISO", "CRITICA"]}
                            }
                        },
                        "machines": {
                            "cardinality": {
                                "field": "machine_id",
                                "precision_threshold": 40000,
                            }
                        },
                        "latest": {"max": {"field": "timestamp"}},
                        "oldest": {"min": {"field": "timestamp"}},
                    },
                }
            },
        },
        "aggregations.summary.buckets",
    )
    return vega(
        data,
        [
            text_mark(
                "'Observaciones en el filtro: ' + datum.doc_count", 10, data="table"
            ),
            text_mark(
                "'Avisos de nivel: ' + datum.alerts.doc_count + ' / ' + datum.classified.doc_count + ' clasificados = ' + (datum.classified.doc_count ? format(datum.alerts.doc_count / datum.classified.doc_count, '.2%') : 'N/D')",
                40,
                data="table",
            ),
            text_mark(
                "'Sin nivel reconocido: ' + (datum.doc_count - datum.classified.doc_count)",
                70,
                data="table",
            ),
            text_mark(
                "'IDs con eventos en la ventana (aprox.): ' + datum.machines.value",
                100,
                data="table",
            ),
            text_mark(
                "'Edad del último evento filtrado: ' + (isValid(datum.latest.value) ? (clock < datum.latest.value ? 'fecha futura; revisar reloj' : format((clock-datum.latest.value)/60000, '.1f') + ' min') : 'N/D: sin eventos')",
                130,
                data="table",
            ),
            text_mark(
                "'Último UTC: ' + (isValid(datum.latest.value) ? utcFormat(datum.latest.value, '%Y-%m-%d %H:%M:%S') : 'N/D')",
                160,
                data="table",
            ),
            text_mark("'Tasa de fallo real: N/D · sin etiquetas online'", 190),
            text_mark(
                "'Activos = IDs observados; no acredita máquinas encendidas.'", 220, 13
            ),
            text_mark(
                "'Edad desde timestamp de evento; no latencia de ingestión.'", 245, 13
            ),
        ],
        signals=[
            {
                "name": "clock",
                "init": "now()",
                "on": [
                    {"events": {"type": "timer", "throttle": 60000}, "update": "now()"}
                ],
            }
        ],
    )


def temperature_spec():
    data = source(
        {
            "size": 0,
            "aggs": {
                "groups": {
                    "multi_terms": {
                        "terms": [{"field": "machine_id"}, {"field": "source.kind"}],
                        "size": TEMPERATURE_GROUP_LIMIT,
                    },
                    "aggs": {
                        "series": {
                            "date_histogram": {
                                "field": "timestamp",
                                "fixed_interval": "1h",
                                "min_doc_count": 0,
                            },
                            "aggs": {
                                "air": {"avg": {"field": "air_temp_K"}},
                                "process": {"avg": {"field": "process_temp_K"}},
                            },
                        }
                    },
                }
            },
        },
        "aggregations.groups",
    )
    # Keep the aggregation envelope: sum_other_doc_count must remain visible.
    data["name"] = "response"
    groups = {
        "name": "groups",
        "source": "response",
        "transform": [
            {"type": "flatten", "fields": ["buckets"], "as": ["identity"]},
            {"type": "filter", "expr": "isValid(datum.identity)"},
            {
                "type": "formula",
                "as": "group",
                "expr": "join(datum.identity.key, ' / ')",
            },
            {"type": "collect", "sort": {"field": "group"}},
            {"type": "window", "ops": ["row_number"], "as": ["rank"]},
        ],
    }
    page = {
        "name": "page_groups",
        "source": "groups",
        "transform": [
            {
                "type": "filter",
                "expr": "datum.rank > (page-1)*pageSize && datum.rank <= page*pageSize",
            }
        ],
    }
    table = {
        "name": "table",
        "source": "page_groups",
        "transform": [
            {
                "type": "flatten",
                "fields": ["identity.series.buckets"],
                "as": ["bucket"],
            },
            {
                "type": "fold",
                "fields": ["bucket.air.value", "bucket.process.value"],
                "as": ["sensor", "temperature"],
            },
            {"type": "formula", "as": "time", "expr": "datum.bucket.key"},
        ],
    }
    points = {
        "name": "points",
        "source": "table",
        "transform": [
            {
                "type": "filter",
                "expr": "isValid(datum.temperature) && isFinite(datum.temperature) && isValid(datum.time) && isFinite(datum.time) && datum.bucket.doc_count > 0",
            }
        ],
    }
    x_domain = "extent(pluck(data('points'), 'time'))"
    y_domain = "extent(pluck(data('points'), 'temperature'))"
    description = "datum.group + '; ' + (datum.sensor === 'bucket.air.value' ? 'aire' : 'proceso') + '; UTC ' + utcFormat(datum.time, '%Y-%m-%d %H:%M') + '; ' + format(datum.temperature, '.2f') + ' K; n hora ' + datum.bucket.doc_count"
    return vega(
        [data, groups, page, table, points],
        [
            {
                "type": "group",
                "from": {
                    "facet": {
                        "name": "series",
                        "data": "table",
                        "groupby": ["group", "sensor"],
                    }
                },
                "marks": [
                    {
                        "type": "line",
                        "aria": False,
                        "from": {"data": "series"},
                        "sort": {"field": "datum.bucket.key"},
                        "encode": {
                            "update": {
                                "x": {"scale": "x", "field": "time"},
                                "y": {"scale": "y", "field": "temperature"},
                                "defined": {
                                    "signal": "isValid(datum.temperature) && datum.bucket.doc_count > 0"
                                },
                                "stroke": {"scale": "color", "field": "group"},
                                "strokeDash": {
                                    "signal": "datum.sensor === 'bucket.air.value' ? [2,3] : [8,0]"
                                },
                                "tooltip": {
                                    "signal": "{'ID / fuente': datum.group, 'sensor': datum.sensor, 'UTC': utcFormat(datum.bucket.key, '%Y-%m-%d %H:%M'), 'media K': datum.temperature, 'n hora': datum.bucket.doc_count}"
                                },
                            }
                        },
                    },
                    {
                        "type": "symbol",
                        "from": {"data": "series_points"},
                        "encode": {
                            "update": {
                                "x": {"scale": "x", "field": "time"},
                                "y": {"scale": "y", "field": "temperature"},
                                "opacity": {
                                    "signal": "isValid(datum.temperature) ? 1 : 0"
                                },
                                "size": {"value": 35},
                                "shape": {"scale": "shape", "field": "group"},
                                "fill": {"scale": "color", "field": "group"},
                                "description": {"signal": description},
                                "tooltip": {"signal": description},
                            }
                        },
                    },
                ],
                "data": [
                    {
                        "name": "series_points",
                        "source": "series",
                        "transform": points["transform"],
                    }
                ],
            },
            {
                "type": "text",
                "encode": {
                    "update": {
                        "x": {"signal": "width/2"},
                        "y": {"signal": "height/2"},
                        "align": {"value": "center"},
                        "fontSize": {"value": 14},
                        "text": {
                            "signal": "length(data('points')) ? '' : (length(data('page_groups')) ? 'Sin temperaturas en esta página / ventana' : (length(data('groups')) ? 'Página vacía: seleccione una página con IDs' : 'Sin datos en el filtro / ventana'))"
                        },
                        "description": {
                            "signal": "length(data('points')) ? '' : 'Sin datos de temperatura; compruebe página, filtro y ventana'"
                        },
                    }
                },
            },
        ],
        background="#ffffff",
        title={
            "text": {
                "signal": "'IDs: ' + length(data('page_groups')) + '/' + length(data('groups')) + ' recuperados · página ' + page + '/' + max(1, ceil(length(data('groups'))/pageSize))"
            },
            "subtitle": {
                "signal": "['Hasta 100 ID/fuente; eventos fuera del top: ' + (length(data('response')) ? data('response')[0].sum_other_doc_count : 0), 'Selector 1–20: use páginas con IDs o filtre.', 'Aire punteado; proceso continuo. Forma/color por ID.']"
            },
            "anchor": "start",
            "fontSize": 13,
            "subtitleFontSize": 11,
        },
        signals=[
            {"name": "pageSize", "value": TEMPERATURE_PAGE_SIZE},
            {
                "name": "page",
                "value": 1,
                "bind": {
                    "input": "select",
                    "name": "Página de IDs (5 por página): ",
                    "options": list(
                        range(1, TEMPERATURE_GROUP_LIMIT // TEMPERATURE_PAGE_SIZE + 1)
                    ),
                },
            },
            {
                "name": "xDomain",
                "update": f"!length(data('points')) ? [0, 3600000] : ({x_domain}[0] === {x_domain}[1] ? [{x_domain}[0]-1800000, {x_domain}[1]+1800000] : {x_domain})",
            },
            {
                "name": "yDomain",
                "update": f"!length(data('points')) ? [0, 1] : ({y_domain}[0] === {y_domain}[1] ? [{y_domain}[0]-1, {y_domain}[1]+1] : {y_domain})",
            },
        ],
        scales=[
            {
                "name": "x",
                "type": "utc",
                "domain": {"signal": "xDomain"},
                "range": "width",
            },
            {
                "name": "y",
                "type": "linear",
                "domain": {"signal": "yDomain"},
                "range": "height",
                "zero": False,
            },
            {
                "name": "color",
                "type": "ordinal",
                "domain": {"data": "page_groups", "field": "group"},
                # Five identities per page; each color exceeds 3:1 on white
                # for essential lines/symbols (WCAG 2.2 SC 1.4.11).
                "range": ["#1f77b4", "#b35400", "#2ca02c", "#d62728", "#9467bd"],
            },
            {
                "name": "shape",
                "type": "ordinal",
                "domain": {"data": "page_groups", "field": "group"},
                "range": ["circle", "square", "triangle-up", "diamond", "cross"],
            },
        ],
        axes=[
            {
                "orient": "bottom",
                "scale": "x",
                "title": "UTC · media horaria; huecos sin datos",
                "description": "UTC; media horaria. Sin graduaciones cuando no hay temperaturas válidas.",
                "tickCount": {"signal": "max(2, floor(width/140))"},
                "values": {"signal": "length(data('points')) ? null : []"},
            },
            {
                "orient": "left",
                "scale": "y",
                "title": "Temperatura media (K)",
                "description": "Temperatura media en kelvin. Sin graduaciones cuando no hay temperaturas válidas.",
                "values": {"signal": "length(data('points')) ? null : []"},
            },
        ],
        legends=[
            {
                "fill": "color",
                "shape": "shape",
                "title": "ID / fuente · página actual",
                "titleLimit": 1000,
                "labelLimit": 1000,
                "orient": "bottom",
                "columns": 1,
            }
        ],
    )


def heatmap_spec(offline):
    return vega(
        {"name": "table", "values": offline["wear_bins"]},
        [
            {
                "type": "rect",
                "from": {"data": "table"},
                "encode": {
                    "update": {
                        "x": {"scale": "x", "field": "wear_bin"},
                        "width": {"scale": "x", "band": 0.95},
                        "y": {"scale": "y", "field": "machine_type"},
                        "height": {"scale": "y", "band": 0.95},
                        "fill": {"scale": "color", "field": "failure_rate"},
                        "tooltip": {"signal": "datum"},
                    }
                },
            },
            {
                "type": "text",
                "from": {"data": "table"},
                "encode": {
                    "update": {
                        "x": {"scale": "x", "field": "wear_bin", "band": 0.5},
                        "y": {"scale": "y", "field": "machine_type", "band": 0.5},
                        "text": {
                            "signal": "datum.positives + '/' + datum.rows + ' (' + format(datum.failure_rate, '.1%') + ')'"
                        },
                        "align": {"value": "center"},
                        "baseline": {"value": "middle"},
                        "fontSize": {"value": 12},
                        "fill": {"value": "#111111"},
                    }
                },
            },
        ],
        scales=[
            {
                "name": "x",
                "type": "band",
                "domain": ["0–49", "50–99", "100–149", "150–199", "200–249", "250+"],
                "range": "width",
            },
            {"name": "y", "type": "band", "domain": ["H", "L", "M"], "range": "height"},
            {
                "name": "color",
                "type": "linear",
                "domain": [0, 1],
                "range": ["#f7fbff", "#6baed6"],
            },
        ],
        axes=[
            {
                "orient": "bottom",
                "scale": "x",
                "title": "Desgaste (min), bandas de 50 min · muestra fija offline",
            },
            {"orient": "left", "scale": "y", "title": "Tipo sintético"},
        ],
        legends=[
            {
                "fill": "color",
                "title": "Fallos etiquetados / filas",
                "titleLimit": 1000,
                "direction": "horizontal",
                "gradientLength": 240,
                "format": ".0%",
                "orient": "bottom",
            }
        ],
    )


def recent_search():
    return {
        "type": "search",
        "id": "cnc-cg19-recent-v2",
        "attributes": {
            "title": "Últimos 50 eventos · timestamp DESC, event_id ASC",
            "description": "Eventos filtrados; ID completo y fuente. No se deducen FP/FN sin etiquetas.",
            "columns": [
                "timestamp",
                "event_id",
                "machine_id",
                "source.kind",
                "alert_level",
                "failure_score",
                "risk_alert",
                "anomaly_alert",
            ],
            "sort": [["timestamp", "desc"], ["event_id", "asc"]],
            "rowsPerPage": 50,
            "sampleSize": 50,
            "hideChart": True,
            "hideTable": False,
            "isTextBasedQuery": False,
            "grid": {},
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps(
                    {
                        "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index",
                        "query": {"language": "kuery", "query": ""},
                        "filter": [],
                        "size": 50,
                    }
                )
            },
        },
        "references": [
            {
                "type": "index-pattern",
                "id": DATA_VIEW_ID,
                "name": "kibanaSavedObjectMeta.searchSourceJSON.index",
            }
        ],
    }


def build_objects(offline):
    objects = [
        {
            "type": "index-pattern",
            "id": DATA_VIEW_ID,
            "attributes": {
                "title": INDEX,
                "name": "CG19 · telemetría de laboratorio",
                "timeFieldName": "timestamp",
            },
            "references": [],
        }
    ]
    specs = {
        "summary": ("Ventana filtrada · avisos, IDs y edad", summary_spec()),
        "temperature": (
            "Temperaturas por ID / fuente · media horaria; aire punteado, proceso continuo",
            temperature_spec(),
        ),
        "wear": (
            "OFFLINE FIJO · desgaste vs frecuencia de fallo etiquetado · no responde a filtros",
            heatmap_spec(offline),
        ),
    }
    for key, (title, spec) in specs.items():
        objects.append(
            {
                "type": "visualization",
                "id": "cnc-cg19-" + key + "-v2",
                "attributes": {
                    "title": title,
                    "description": "Simulación docente; sin ETA, RUL ni control físico.",
                    "visState": json.dumps(
                        {
                            "title": title,
                            "type": "vega",
                            "aggs": [],
                            "params": {"spec": json.dumps(spec, ensure_ascii=False)},
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
            }
        )
    objects.append(recent_search())
    overall = offline["overall"]
    cases = offline["cases"]
    decision = (
        "## Interpretación y decisión propuesta\n"
        'Telemetría: KQL `machine_id : "CNC-024"`, `alert_level : "AVISO"` y selector de fecha UTC. '
        "Los filtros afectan KPI, temperaturas y tabla. Separar `source.kind`. "
        "Temperaturas: media por hora, no trayectoria física validada; consulta hasta 100 combinaciones ID/fuente, "
        "páginas de cinco con selector de teclado. El título indica IDs recuperados, página y eventos fuera del top; "
        "recorrer páginas o filtrar máquina/fuente. Color y forma distinguen IDs dentro de cada página, se reutilizan al cambiarla. "
        "Las líneas se cortan en horas vacías. Los IDs son simulados.\n\n"
        "### Evaluación OFFLINE FIJA (no responde a filtros)\n"
        f"Validación reutilizada para ajustar umbral; **no test independiente**. RF `score >= {offline['threshold']}`. "
        f"TP {overall['tp']}; FN {overall['fn']}; FP {overall['fp']}; TN {overall['tn']}. "
        f"FNR = FN/positivos = {overall['fn']}/{overall['positives']}; "
        f"FPR = FP/negativos = {overall['fp']}/{overall['negatives']}. "
        "Estas alertas RF no equivalen a los niveles docentes ni a IF. "
        "Heatmap: cada celda muestra fallos etiquetados/filas de su tipo y banda de desgaste; celda ausente = sin muestra, no 0%. "
        "No mide fallos por hora, causalidad ni disponibilidad.\n\n"
        + "\n\n".join(
            f"**{kind} offline**, fila de fuente {case['source_row_index']}, tipo {case['machine_type']}: "
            f"label={case['label']}, RF={case['rf_score']}, desgaste={case['tool_wear_min']} min. "
            + (
                "Una inspección podría ser innecesaria: contrastar sensores y procedencia antes de proponer una intervención."
                if kind == "FP"
                else "Un fallo etiquetado queda sin alerta RF: la ausencia de aviso no acredita seguridad; requiere revisión contextual."
            )
            for kind, case in cases.items()
        )
        + "\n\n**Propuesta humana:** revisar fila, temperatura, desgaste y procedencia; registrar decisión y responsable. "
        "No se ha validado utilidad con un operador, ejecutado mantenimiento ni observado ahorro. "
        "Online no hay ground truth: tasa real, FP y FN = N/D. "
        "[Procedencia y reproducción](https://github.com/AABD-Ethazi-2627/T2-erronka1/blob/codex/cg19-required-views/docs/evidence/CG19_2026-10-21.md)."
    )
    objects.append(
        {
            "type": "visualization",
            "id": "cnc-cg19-decision-v2",
            "attributes": {
                "title": "Decisión humana propuesta · límites y FP/FN offline",
                "visState": json.dumps(
                    {
                        "title": "Decisión y límites",
                        "type": "markdown",
                        "aggs": [],
                        "params": {"markdown": decision, "openLinksInNewTab": False},
                    }
                ),
                "uiStateJSON": "{}",
            },
            "references": [],
        }
    )
    panels, references = [], []
    positions = [
        (0, 0, 48, 11),
        (0, 11, 48, 18),
        (0, 29, 48, 15),
        (0, 44, 48, 22),
        (0, 66, 48, 24),
    ]
    for i, (obj, position) in enumerate(zip(objects[1:], positions, strict=True)):
        name = f"panel_{i}"
        references.append({"name": name, "type": obj["type"], "id": obj["id"]})
        x, y, w, h = position
        panels.append(
            {
                "version": "9.5.4",
                "type": obj["type"],
                "panelIndex": str(i),
                "panelRefName": name,
                "embeddableConfig": {},
                "gridData": {"x": x, "y": y, "w": w, "h": h, "i": str(i)},
            }
        )
    objects.append(
        {
            "type": "dashboard",
            "id": DASHBOARD_ID,
            "attributes": {
                "title": "CNC Guard · CG19 revisión v2 (online sin etiquetas + offline fijo)",
                "description": "Candidato generado offline. Filtros máquina/fecha/alerta en telemetría; heatmap y casos offline fijos. Importación, consulta/render Kibana y revisión humana pendientes.",
                "panelsJSON": json.dumps(panels),
                "optionsJSON": json.dumps(
                    {"useMargins": True, "hidePanelTitles": False}
                ),
                "timeRestore": False,
                "kibanaSavedObjectMeta": {
                    "searchSourceJSON": json.dumps(
                        {"query": {"query": "", "language": "kuery"}, "filter": []}
                    )
                },
            },
            "references": references,
        }
    )
    return objects


def generate(offline_path, output=OUTPUT, check=False):
    offline = json.loads(Path(offline_path).read_text(encoding="utf-8"))
    content = (
        "\n".join(
            json.dumps(o, ensure_ascii=False, allow_nan=False)
            for o in build_objects(offline)
        )
        + "\n"
    )
    output = Path(output)
    if check:
        if output.read_text(encoding="utf-8") != content:
            raise ValueError("Generated CG19 objects differ from committed source")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8", newline="\n")
    return content


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--offline", type=Path, default=ROOT / "kibana/cg19-offline.json"
    )
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    generate(args.offline, args.output, args.check)
    print(
        "CG19 source verified"
        if args.check
        else "Generated offline CG19 source; no Kibana import or export performed"
    )
