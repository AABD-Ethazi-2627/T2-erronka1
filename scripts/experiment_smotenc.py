"""Supplementary train-fold-only SMOTENC comparison, no automatic promotion."""

import json
from pathlib import Path

import imblearn
import pandas as pd
from imblearn.over_sampling import SMOTENC
from imblearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.model_selection import StratifiedKFold, cross_val_predict

from scoring.preparation import SEED, SENSORS, split_development
from scripts.experiment_rf import evaluate, pipeline, threshold


def make_smotenc(trees=120):
    impute = ColumnTransformer(
        [
            ("sensors", SimpleImputer(strategy="median"), SENSORS),
            ("type", SimpleImputer(strategy="most_frequent"), ["machine_type"]),
        ],
        verbose_feature_names_out=False,
    ).set_output(transform="pandas")
    # Sample original sensors/type, then recompute nonlinear physical features.
    # No fractional one-hot categories or interpolation of labels/IDs.
    return Pipeline(
        [
            ("impute", impute),
            (
                "sampler",
                SMOTENC(
                    categorical_features=["machine_type"],
                    sampling_strategy=0.2,
                    k_neighbors=3,
                    random_state=SEED,
                ),
            ),
            *pipeline("rf", True, None, trees=trees, depth=12).steps,
        ]
    )


def run():
    frame = pd.read_csv("data/ai4i2020_train.csv")
    train, validation, _ = split_development(frame)
    cv = list(
        StratifiedKFold(n_splits=4, shuffle=True, random_state=SEED).split(
            train, train.machine_failure
        )
    )
    prior = json.loads(Path("outputs/cg08/report.json").read_text())
    assert prior["splits"]["train"] == train.index.tolist()
    assert prior["folds"] == [
        {"fit": train.index[a].tolist(), "held": train.index[b].tolist()} for a, b in cv
    ]
    model = make_smotenc()
    oof = cross_val_predict(
        model, train, train.machine_failure, cv=cv, method="predict_proba", n_jobs=2
    )[:, 1]
    cutoff = threshold(train.machine_failure, oof)
    model.fit(train, train.machine_failure)
    scores = model.predict_proba(validation)[:, 1]
    result = {
        "imbalanced_learn": imblearn.__version__,
        "seed": SEED,
        "sampling_strategy": 0.2,
        "k_neighbors": 3,
        "same_train_folds_as_CG08": True,
        "oof_development": evaluate(train.machine_failure, oof, cutoff),
        "validation_diagnostic": evaluate(
            validation.machine_failure,
            scores,
            threshold(validation.machine_failure, scores),
        ),
        "previous_winner_oof": prior["search"][prior["winner"]][
            "oof_selection_metrics"
        ],
        "limitations": [
            "Supplementary exploratory experiment; selection/tuning scores optimistic.",
            (
                "No new independent final test. Existing API model is "
                + "not changed by this experiment."
            ),
            (
                "SMOTENC samples original sensors and true categorical "
                + "types; derived physics recomputed afterward."
            ),
            (
                "Synthetic interpolated sensors need physical "
                + "plausibility scrutiny; not new observed failures."
            ),
        ],
    }
    Path("docs/evidence/CG08_smotenc.json").write_text(
        json.dumps(result, indent=2) + "\n"
    )
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    run()
