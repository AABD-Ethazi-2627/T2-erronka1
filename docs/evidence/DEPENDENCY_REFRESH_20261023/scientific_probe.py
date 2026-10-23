import hashlib
import importlib.metadata as md
import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path.cwd()))
import numpy as np
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from threadpoolctl import threadpool_limits

from scoring.preparation import SEED, split_development
from scoring.scope import INPUT_FEATURES, load_training_source
from scripts.experiment_rf import evaluate, pipeline

out = pathlib.Path(sys.argv[1])
out.mkdir(exist_ok=False)
source = pathlib.Path("data/ai4i2020_train.csv")
train, _, _ = split_development(load_training_source(source))
folds = list(
    StratifiedKFold(n_splits=3, shuffle=True, random_state=SEED).split(
        train, train.machine_failure
    )
)
model = pipeline("rf", True, trees=120, depth=12)
with threadpool_limits(limits=1):
    started = time.perf_counter()
    scores = cross_val_predict(
        model,
        train[INPUT_FEATURES],
        train.machine_failure,
        cv=folds,
        method="predict_proba",
        n_jobs=1,
    )[:, 1]
    elapsed = time.perf_counter() - started
    model.fit(train[INPUT_FEATURES], train.machine_failure)
    events = train[INPUT_FEATURES].iloc[:30]
    timings = []
    for i in range(35):
        started = time.perf_counter()
        model.predict_proba(events.iloc[[i % 30]])
        duration = time.perf_counter() - started
        if i >= 5:
            timings.append(duration * 1000)
np.save(out / "scores.npy", scores)
report = {
    "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
    "train_rows": len(train),
    "train_index_sha256": hashlib.sha256(
        np.asarray(train.index, dtype="<i8").tobytes()
    ).hexdigest(),
    "folds": 3,
    "policy": "fixed RF physical 120 trees depth12 min_leaf2, seed42; no tuning, train only",
    "versions": {
        p: md.version(p)
        for p in [
            "numpy",
            "pandas",
            "scikit-learn",
            "scipy",
            "joblib",
            "pyarrow",
            "matplotlib",
            "imbalanced-learn",
        ]
    },
    "oof_seconds": elapsed,
    "in_process_single_row_p95_ms": float(np.percentile(timings, 95)),
    "at_015": evaluate(train.machine_failure, scores, 0.15),
    "at_070": evaluate(train.machine_failure, scores, 0.70),
    "score_sha256": hashlib.sha256(scores.tobytes()).hexdigest(),
    "limitations": [
        "development compatibility probe, not independent model selection or HTTP capacity",
        "same folds and fixed cutoffs; reused validation and old test not evaluated",
    ],
}
(out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report))
