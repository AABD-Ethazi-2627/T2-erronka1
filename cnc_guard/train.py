"""Optional in-memory CG04 demonstration. Never writes a delivery artifact."""

from cnc_guard.data import load_training_partitions
from cnc_guard.features import prepare_features
from scripts.experiment_rf import pipeline


def train_model(data_path):
    """Fit only the canonical 70%, score development validation, never the exclusion.

    This does not reproduce CG08 model selection or threshold tuning. Its return
    value cannot replace the RF + anomaly bundle consumed by the API.
    """
    train, validation, excluded = load_training_partitions(data_path)
    X_train, y_train = prepare_features(train)
    X_validation, y_validation = prepare_features(validation)
    model = pipeline("rf", physical=True, weight="balanced")
    model.fit(X_train, y_train)
    accuracy = float(model.score(X_validation, y_validation))
    return model, {
        "artifact_role": "CG04_DEVELOPMENT_ONLY",
        "train_rows": len(train),
        "validation_rows": len(validation),
        "excluded_rows": len(excluded),
        "development_accuracy": accuracy,
        "splits": {
            "train": train.index.tolist(),
            "validation": validation.index.tolist(),
            "excluded_previously_inspected_test": excluded.index.tolist(),
        },
    }
