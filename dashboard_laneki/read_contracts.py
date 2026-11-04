"""Pure validation of read responses. No network, synthesis, or inference."""

import math

import pandas as pd

COLUMNS = [
    "Ordua",
    "Prozesu-tenperatura (°C)",
    "Bihurdura-momentua (Nm)",
    "Erremintaren higadura (min)",
]


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def history(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get("metadata"), dict):
        raise TypeError("Missing history metadata")
    data = payload.get("datuak")
    if not isinstance(data, dict) or not set(COLUMNS) <= data.keys():
        raise ValueError("Missing history columns")
    if (
        any(not isinstance(values, list) for values in data.values())
        or len({len(v) for v in data.values()}) != 1
    ):
        raise ValueError("Unequal history columns")
    for name in COLUMNS[1:]:
        if any(v is not None and not finite(v) for v in data[name]):
            raise ValueError("Invalid sensor")
    for value in data["Ordua"]:
        if not isinstance(value, str):
            raise TypeError("Invalid UTC timestamp")
        ts = pd.Timestamp(value)
        if pd.isna(ts) or ts.tzinfo is None or ts.utcoffset().total_seconds() != 0:
            raise ValueError("Expected full UTC timestamp")
    cursor = payload.get("next_cursor")
    if cursor is not None and (not isinstance(cursor, str) or not cursor):
        raise ValueError("Invalid cursor")
    frame = pd.DataFrame(data)
    # Preserve original timestamp strings, identity columns, nulls and metadata.
    frame.attrs.update(metadata=payload["metadata"], next_cursor=cursor)
    return frame


def evaluation(payload, machine):
    if not isinstance(payload, dict) or payload.get("available") is not True:
        raise ValueError("Ebaluazioa ez dago eskuragarri")
    for key in ("model_version", "model_artifact_sha256"):
        if not machine.get(key) or payload.get(key) != machine[key]:
            raise ValueError("Ereduaren identitatea ez dator bat")
    if (
        not payload.get("partition")
        or not payload.get("scope")
        or payload.get("labels") != [0, 1]
    ):
        raise ValueError("Ebaluazioaren jatorria osatu gabe")
    if not isinstance(payload.get("provenance"), dict) or not payload["provenance"]:
        raise ValueError("Ebaluazioaren jatorria falta da")
    if (
        not isinstance(payload.get("decision_rule"), str)
        or not payload["decision_rule"]
    ):
        raise ValueError("Erabaki-araua falta da")
    threshold = payload.get("threshold")
    if not finite(threshold) or not 0 <= threshold <= 1:
        raise ValueError("Atalase baliogabea")
    if (
        not finite(machine.get("risk_threshold"))
        or threshold != machine["risk_threshold"]
    ):
        raise ValueError("Ebaluazioaren eta inferentziaren atalaseak ez datoz bat")
    matrix = payload.get("confusion_matrix")
    if (
        not isinstance(matrix, list)
        or len(matrix) != 2
        or any(not isinstance(row, list) or len(row) != 2 for row in matrix)
    ):
        raise ValueError("2×2 matrizea behar da")
    if any(type(v) is not int or v < 0 for row in matrix for v in row):
        raise ValueError("Matrize baliogabea")
    tn, fp = matrix[0]
    fn, tp = matrix[1]
    divide = lambda a, b: a / b if b else None
    return {
        "TN": tn,
        "FP": fp,
        "FN": fn,
        "TP": tp,
        "n": tn + fp + fn + tp,
        "positibo_errealak": fn + tp,
        "negatibo_errealak": tn + fp,
        "accuracy": divide(tn + tp, tn + fp + fn + tp),
        "precision": divide(tp, tp + fp),
        "recall": divide(tp, tp + fn),
        "f1": divide(2 * tp, 2 * tp + fp + fn),
    }


def scenario(inspection, hours, hourly):
    if any(not finite(v) or v < 0 for v in (inspection, hours, hourly)):
        raise ValueError("Invalid scenario inputs")
    total = inspection + hours * hourly
    if not math.isfinite(total):
        raise ValueError("Scenario overflow")
    return total
