"""Aggregate frozen batch results; private row data stays outside the repository."""

import argparse
import csv
from pathlib import Path

import numpy as np

from scripts.ml_study import read_json


def report(output, destination):
    results = read_json(output / "results/metrics.json")
    protocol = read_json(output / "protocol.json")
    lines = [
        "# Evaluación del lote CNC del 23/10/2026",
        "",
        (
            "RF ejecuta la inferencia con las seis entradas permitidas. "
            "No se ajustan modelos, calibradores ni umbrales con el lote."
        ),
        "",
        (
            f"{protocol['files']} CSV, {protocol['events']} eventos y "
            f"{protocol['unique_vectors']} vectores únicos. "
            "Sin coincidencias exactas con las 8.000 filas de la fuente aprobada. "
            "Esto no acredita procedencia industrial ni independencia de generación."
        ),
        "",
        "## RF fijo: entrenado previamente con 5.600 filas",
        "",
        (
            "| Cohorte | Corte | TP | FN | FP | TN | Recall | Precision | "
            "F1 | F2 | AP | €/1.000 |"
        ),
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for population in ("unique", "events"):
        for label, p in results["fixed"]["policies"].items():
            m = p[population]
            lines.append(
                f"| {population} | {label} ≥ {p['threshold']:.8f} | "
                f"{m['tp']} | {m['fn']} | {m['fp']} | {m['tn']} | "
                f"{m['recall']:.2%} | {m['precision']:.2%} | {m['f1']:.4f} | "
                f"{m['f2']:.4f} | {m['average_precision']:.4f} | "
                f"{m['cost_per_1000']:.2f} |"
            )
    lines += [
        "",
        (
            "Las filas research usan cortes aprendidos antes de recibir el lote; "
            "no sustituyen 0,15/0,70. CRITICA se informa aparte, no suprime AVISO."
        ),
        "",
        "## Referencias guardadas: 40 configuraciones × tres refits outer",
        "",
        (
            "Cada modelo se evalúa por separado sobre los mismos 2.000 vectores. "
            "Su entrenamiento previo contiene 3.733/3.734 filas. "
            "Los rangos reflejan esos tres modelos, no intervalos de confianza. "
            "No es un ensemble nuevo ni se triplica el tamaño de la muestra. "
            "RF5600 anterior se mantiene como paquete fijo principal."
        ),
        "",
    ]
    compact = []
    for policy in ("aviso", "business_A", "critica"):
        lines += [
            "### " + policy,
            "",
            (
                "| Configuración | FN rango | FP rango | Recall media | "
                "Precision media | F1 media | F2 media | AP media | "
                "Coste medio €/1.000 |"
            ),
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for name, records in results["outer_models"].items():
            values = [r["policies"][policy]["unique"] for r in records]
            fn = [v["fn"] for v in values]
            fp = [v["fp"] for v in values]
            mean = {
                key: (
                    float(np.mean([v[key] for v in values]))
                    if all(v[key] is not None for v in values)
                    else None
                )
                for key in (
                    "recall",
                    "precision",
                    "f1",
                    "f2",
                    "average_precision",
                    "cost_per_1000",
                )
            }
            # For no-positive predictions, precision is undefined in JSON;
            # render its mean as n/a rather than silently substituting zero.
            precision = (
                f"{mean['precision']:.2%}" if mean["precision"] is not None else "n/a"
            )
            lines.append(
                f"| {name} | {min(fn)}–{max(fn)} | {min(fp)}–{max(fp)} | "
                f"{mean['recall']:.2%} | {precision} | {mean['f1']:.4f} | "
                f"{mean['f2']:.4f} | {mean['average_precision']:.4f} | "
                f"{mean['cost_per_1000']:.2f} |"
            )
            compact.append(
                {
                    "model": name,
                    "policy": policy,
                    "min_fn": min(fn),
                    "max_fn": max(fn),
                    "min_fp": min(fp),
                    "max_fp": max(fp),
                    **mean,
                }
            )
        lines.append("")
    lines += [
        "## Rareza: diagnóstico frente a etiqueta de avería",
        "",
        (
            "Umbrales de normales inner guardados; no son probabilidades. "
            "No existe verdad independiente de anomalías ni se activa un detector."
        ),
        "",
        "| Detector | FN rango | FP rango | AP media frente a avería |",
        "|---|---:|---:|---:|",
    ]
    for name, records in results["anomalies"].items():
        values = [r["policies"]["rarity"]["unique"] for r in records]
        lines.append(
            f"| {name} | {min(v['fn'] for v in values)}–"
            f"{max(v['fn'] for v in values)} | "
            f"{min(v['fp'] for v in values)}–{max(v['fp'] for v in values)} | "
            f"{np.mean([v['average_precision'] for v in values]):.4f} |"
        )
    lines += [
        "",
        "## Condiciones",
        "",
        (
            "Costes docentes: TP300 €, FN5000 €, FP200 €, TN0 €. "
            "Resultados monetarios hipotéticos, no ahorro industrial demostrado. "
            "Las etiquetas suministradas se usan únicamente para evaluar."
        ),
        "",
        (
            "La comparación adicional no elige ganador nuevo ni convierte el lote "
            "en datos de ajuste. Fechas e IDs no se utilizan como predictores "
            "ni prueban una serie temporal física. Sin cambios del modelo servido."
        ),
        "",
    ]
    destination.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    with destination.with_suffix(".csv").open(
        "w", newline="", encoding="utf-8"
    ) as stream:
        writer = csv.DictWriter(
            stream, fieldnames=list(compact[0]), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(compact)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    report(args.output, args.destination)
