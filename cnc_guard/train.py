from pathlib import Path

import joblib
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from cnc_guard.features import FEATURE_COLUMNS, load_training_data

RANDOM_STATE = 42
TEST_SIZE = 0.2


def train_model(
    data_path: str | Path,
    model_path: str | Path = "models/cnc_failure_model.pkl",
    *,
    overwrite: bool = False,
) -> dict[str, float | int | str]:
    """Entrena el modelo; no reemplaza artefactos existentes salvo petición explícita."""
    destination = Path(model_path)
    if destination.exists() and not overwrite:
        raise FileExistsError(
            f"El modelo ya existe: {destination}. "
            "Usa overwrite=True para autorizar su sustitución."
        )

    X, y = load_training_data(data_path)

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
        stratify=y,
    )

    categorical = ["machine_type"]
    numeric = [column for column in FEATURE_COLUMNS if column not in categorical]

    preprocessing = ColumnTransformer(
        transformers=[
            ("categorical", OneHotEncoder(handle_unknown="ignore"), categorical),
            ("numeric", "passthrough", numeric),
        ]
    )

    model = Pipeline(
        steps=[
            ("preprocessing", preprocessing),
            (
                "classifier",
                RandomForestClassifier(
                    n_estimators=200,
                    random_state=RANDOM_STATE,
                    class_weight="balanced",
                    n_jobs=-1,
                ),
            ),
        ]
    )

    model.fit(X_train, y_train)
    accuracy = float(model.score(X_test, y_test))

    destination.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, destination)

    return {
        "train_rows": len(X_train),
        "test_rows": len(X_test),
        "accuracy": accuracy,
        "random_state": RANDOM_STATE,
        "model_path": str(destination),
    }
