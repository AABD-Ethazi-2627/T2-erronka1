"""Fixed classroom alerts and explicitly hypothetical error costs."""

import math


def alert_level(probability):
    if not math.isfinite(probability) or not 0 <= probability <= 1:
        raise ValueError("Probability must be finite in [0,1]")
    return "CRITICA" if probability >= 0.7 else "AVISO" if probability >= 0.15 else "OK"


def cost(fp, fn, inspection_eur, downtime_hours):
    if any(
        not math.isfinite(x) or x < 0 for x in [fp, fn, inspection_eur, downtime_hours]
    ):
        raise ValueError("Nonnegative finite scenario inputs required")
    return fp * inspection_eur + fn * downtime_hours * 1200
