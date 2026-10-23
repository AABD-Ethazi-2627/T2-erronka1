"""Export fitted research components to a six-input sklearn probability pipeline."""

import argparse
from pathlib import Path

import joblib
import numpy as np
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer

from scoring.preparation import features
from scoring.scope import INPUT_FEATURES, SCOPE
from scripts.ml_study import (
    completed_units,
    digest,
    read_json,
    source_train,
    write_json,
)
from scripts.report_ml_study import verify_evidence


def export(root, destination):
    manifest = verify_evidence(root)
    destination.mkdir(parents=True, exist_ok=False)
    train, _ = source_train()
    probe = train[INPUT_FEATURES].iloc[:32]
    packages = []
    for task, path in completed_units(root):
        if task["phase"] != "package":
            continue
        result = read_json(path / "result.json")
        if digest(path / "model.joblib") != result["model_sha256"]:
            raise ValueError("Own fitted model hash mismatch")
        fitted = joblib.load(path / "model.joblib")
        name = task["model"]
        if fitted.spec["family"] == "cat":
            packages.append(
                {
                    "model": name,
                    "status": "not_exported",
                    "reason": (
                        "Native categorical preprocessing requires a separately "
                        "reviewed production adapter"
                    ),
                }
            )
            continue
        steps = [
            ("physics", FunctionTransformer(features, validate=False)),
            ("preprocess", fitted.prep_),
        ]
        if hasattr(fitted, "rank_"):
            steps.append(("independent_columns", fitted.rank_))
        steps.append(("model", fitted.model_))
        pipeline = Pipeline(steps)
        filename = name + ".joblib"
        artifact = destination / filename
        joblib.dump(pipeline, artifact)
        scores = joblib.load(artifact).predict_proba(probe)[:, 1]
        difference = float(np.max(np.abs(scores - fitted.score(probe))))
        np.testing.assert_allclose(
            scores, fitted.score(probe), rtol=0, atol=manifest["reload_atol"]
        )
        family = fitted.spec["family"]
        additional = {
            "ebm": "interpret-core==0.6.10",
            "xgb": "xgboost==3.1.3",
            "lgb": "lightgbm==4.6.0",
        }.get(family)
        packages.append(
            {
                "model": name,
                "status": "exported_research_only",
                "file": filename,
                "artifact_sha256": digest(artifact),
                "bytes": artifact.stat().st_size,
                "config": fitted.spec,
                "scope": SCOPE,
                "versions": manifest["environment"],
                "threshold_from_5600_train_oof": (
                    float(np.float32(task["threshold"]))
                    if family == "xgb"
                    else task["threshold"]
                ),
                "threshold_encoded_in_raw_csv": task["threshold"],
                "alert_contract": {
                    "OK": "score<0.15",
                    "AVISO": "0.15<=score<0.70",
                    "CRITICA": "score>=0.70",
                },
                "fit_source_rows_sha256": result["fit_rows_sha256"],
                "input_features": INPUT_FEATURES,
                "method": "predict_proba",
                "reload_and_conversion_max_score_difference": difference,
                "verification": "32 training probes; no new performance evaluation",
                "additional_runtime_dependency": additional,
                "existing_api_libraries_sufficient": (
                    additional is None and not hasattr(fitted, "rank_")
                ),
                "extra_research_module": (
                    "scripts.ml_study_models.IndependentColumns"
                    if hasattr(fitted, "rank_")
                    else None
                ),
                "api_runtime_executed": False,
                "operational_bundle_ready": False,
                "remaining": [
                    "Review candidate and unchanged/changed score semantics",
                    (
                        "Combine with authorised IF and exact package_model "
                        "provenance/manifest"
                    ),
                    "Decision PM and separate integration/deployment task",
                ],
            }
        )
    write_json(
        destination / "packages.json",
        {"packages": packages, "manifest_sha256": digest(root / "manifest.json")},
    )
    print(destination / "packages.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    export(args.root, args.destination)
