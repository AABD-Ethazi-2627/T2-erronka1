"""Render complete numerical tables from immutable JSON; no fitting or selection."""

import argparse
from pathlib import Path

import numpy as np

from scripts.ml_study import read_json


def render(summary_path, destination):
    s = read_json(summary_path)
    lines = [
        "# Tablas completas de la exploración ML",
        "",
        (
            "Cohorte: 5.600 filas outer, 190 positivos. Coste primario hipotético: "
            "FP 100 € y FN una hora × 1.200 €/h. "
            "AP agrupada mezcla escalas entre folds; "
            "el JSON conserva AP por fold y su media. "
            "Los recuentos no proceden de validación."
        ),
        "",
    ]
    for title, key in [
        ("A: umbral aprendido en inner", "optimized"),
        ("B: aviso fijo desde 0,15", "aviso"),
        ("CRITICA fija desde 0,70", "critica"),
    ]:
        lines += [
            "## " + title,
            "",
            (
                "| Configuración | TP | FN | FP | TN | Recall | Precision | "
                "F1 | F2 | AP | €/1000 |"
            ),
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for name, r in s["models"].items():
            m = r[key]
            lines.append(
                f"| {name} | {m['tp']} | {m['fn']} | {m['fp']} | {m['tn']} | "
                f"{m['recall']:.2%} | {m['precision']:.2%} | {m['f1']:.4f} | "
                f"{m['f2']:.4f} | {m['average_precision']:.4f} | "
                f"{m['cost_per_1000']:.2f} |"
            )
        lines.append("")
    lines += [
        "## Recursos de los refits outer",
        "",
        (
            "Mediana de fit y tamaño entre tres folds; máximo de sus p95 warm "
            "y de RSS observado. "
            "El p95 procede de 50 repeticiones de una fila en proceso. No es HTTP/E2E; "
            "el tamaño excluye las bibliotecas."
        ),
        "",
        (
            "| Configuración | Fit mediano (s) | Máx p95 (ms) | "
            "Modelo mediano (KiB) | RSS máx (MiB) |"
        ),
        "|---|---:|---:|---:|---:|",
    ]
    for name, r in s["models"].items():
        fs = r["folds"]
        fit = np.median([f["resources"]["fit_seconds"] for f in fs])
        p95 = max(f["resources"]["warm_process_batch1_p95_ms"] for f in fs)
        size = np.median([f["resources"]["model_bytes"] for f in fs]) / 1024
        rss = max(f["accounting"]["peak_rss_bytes"] for f in fs) / 1024**2
        lines.append(f"| {name} | {fit:.4f} | {p95:.3f} | {size:.1f} | {rss:.1f} |")
    lines += [
        "",
        "## Sensibilidad: umbral aprendido de nuevo en inner por escenario",
        "",
        (
            "Comparación descriptiva RF/GB prefijada. "
            "Los nueve escenarios y todos los modelos "
            "están en el JSON. No se selecciona un escenario después de mirar outer."
        ),
        "",
        "| FP (€) | FN (horas × 1.200 €/h) | RF €/1000 | GB depth3 €/1000 |",
        "|---:|---:|---:|---:|",
    ]
    for fp in (25, 100, 300):
        for fn in (600, 1200, 4800):
            costs = [
                sum(
                    r["cost_euros"]
                    for r in s["models"][n]["sensitivity"][f"fp{fp}_fn{fn}"]
                )
                * 1000
                / 5600
                for n in ["rf_reference", "gb_depth3"]
            ]
            lines.append(f"| {fp} | {fn / 1200:g} | {costs[0]:.2f} | {costs[1]:.2f} |")
    lines += [
        "",
        "## Rareza: diagnóstico respecto a avería y RF 0,15",
        "",
        (
            "Failure=0 es proxy de normalidad. "
            "No hay ground truth independiente de anomalías. "
            "El umbral común es el cuantil 0,99 de normales OOF inner; "
            "ningún detector suprime RF."
        ),
        "",
        (
            "| Detector | Avisos /5600 | Fallos avisados /190 | "
            "FN RF recuperados /22 | FP añadidos |"
        ),
        "|---|---:|---:|---:|---:|",
    ]
    for name, r in s["anomalies"].items():
        lines.append(
            f"| {name} | {r['total_flags']} | {r['failure_labels_flagged']} | "
            f"{r['rf_fn_recovered']} | {r['false_alarms_added']} |"
        )
    lines += [
        "",
        "## Calibración: selección interna y evaluación outer",
        "",
        (
            "Reservas 75/25 propias de cada train. Raw75 usa el mismo 75%. "
            "Finalistas y método se eligen dentro de cada outer-train."
        ),
        "",
        "| Outer | Finalistas | Elegido | Umbral | FN | FP | Recall |",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    for outer, r in s["calibration"].items():
        a = r["selected"]
        m = a["outer"]
        finalists = ", ".join(sorted({v["name"] for v in r["variants"]}))
        lines.append(
            f"| {outer} | {finalists} | {a['name']} / {a['method']} | "
            f"{a['threshold']:.8g} | {m['fn']} | {m['fp']} | {m['recall']:.2%} |"
        )
    with destination.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write("\n".join(lines) + "\n")
    print(destination)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    render(args.summary, args.destination)
