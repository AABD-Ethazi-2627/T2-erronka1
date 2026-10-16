"""Local integration boundary: risk and anomaly are independent signals.

Importable from the repository root. Load only locally generated trusted joblib files.
"""

import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn


def load_bundle(directory):
    directory = Path(directory)
    report = json.loads((directory / "report.json").read_text())
    path = directory / "bundle.pkl"
    if (
        hashlib.sha256(path.read_bytes()).hexdigest()
        != report["artifacts"]["bundle.pkl"]
    ):
        raise ValueError("Bundle hash does not match report")
    versions = {
        "sklearn": sklearn.__version__,
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "joblib": joblib.__version__,
    }
    for name, actual in versions.items():
        if report.get("versions", {}).get(name) != actual:
            raise ValueError(
                f"Incompatible version for {name}: expected "
                f"{report.get('versions', {}).get(name)}, got {actual}"
            )
    return joblib.load(path)


def predict_signals(bundle, frame, policy="f1"):
    if policy not in ("f1", "f2"):
        raise ValueError("Policy must be f1 or f2")
    risk = bundle["rf_models"][policy].predict_proba(frame)[:, 1]
    anomaly = -bundle["isolation_forest"].score_samples(frame)
    if not np.isfinite(risk).all() or not np.isfinite(anomaly).all():
        raise ValueError("Non-finite model scores")
    return [
        {
            "failure_score": float(r),
            "risk_alert": bool(r >= bundle["risk_thresholds"][policy]),
            "anomaly_score": float(a),
            "anomaly_alert": bool(a >= bundle["anomaly_threshold"]),
            "policy": policy,
            "model_version": bundle["model_version"],
        }
        for r, a in zip(risk, anomaly)
    ]
