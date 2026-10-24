"""Verify CPU artifact scores and native CSV decoding; never refit or retune."""

import argparse
from pathlib import Path

import joblib
import numpy as np
from threadpoolctl import threadpool_limits

from scoring.scope import INPUT_FEATURES
from scripts.ml_study import (
    completed_units,
    digest,
    read_json,
    source_train,
    write_json,
)
from scripts.report_ml_study import load_rows


def check(root, destination):
    train, _ = source_train()
    verified = []
    with threadpool_limits(1):
        for task, path in completed_units(root):
            if task.get("device") == "cuda" or not task.get("artifact"):
                continue
            result = read_json(path / "result.json")
            if digest(path / "model.joblib") != result["model_sha256"]:
                raise ValueError("Own artifact hash mismatch")
            native = joblib.load(path / "model.joblib").score(
                train.loc[task["held"], INPUT_FEATURES]
            )
            stored = load_rows([(task, path)]).score.to_numpy()
            delta = float(np.max(np.abs(native - stored)))
            np.testing.assert_array_equal(native.astype(np.float64), stored)
            verified.append(
                {
                    "model": task["model"],
                    "phase": task["phase"],
                    "fold": task["fold"],
                    "calibration": task.get("calibration"),
                    "native_dtype": str(native.dtype),
                    "score_rows": len(native),
                    "max_difference": delta,
                    "unit": path.name,
                }
            )
    write_json(
        destination,
        {
            "status": "pass",
            "verified": verified,
            "scope": (
                "CPU prediction reload only; no fit, selection, "
                "validation or test scoring"
            ),
        },
    )
    print(
        {
            "verified_cpu_artifacts": len(verified),
            "maximum_score_delta": max(v["max_difference"] for v in verified),
        }
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    check(args.root, args.destination)
