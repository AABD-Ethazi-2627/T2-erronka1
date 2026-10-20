from pathlib import Path

import joblib
import pytest

from cnc_guard.data import load_dataset
from cnc_guard.features import FEATURE_COLUMNS, load_training_data
from cnc_guard.train import train_model

DATA_PATH = Path("data/ai4i2020_train.csv")


def test_dataset_loads_with_expected_columns():
    data = load_dataset(DATA_PATH)
    assert len(data) == 8000
    assert len(data.columns) == 13


def test_features_exclude_failure_result_columns():
    X, y = load_training_data(str(DATA_PATH))
    assert list(X.columns) == FEATURE_COLUMNS
    assert len(X) == len(y)
    assert "machine_failure" not in X.columns
    assert not any(column.startswith("failure_") for column in X.columns)


def test_training_saves_loadable_model(tmp_path):
    model_path = tmp_path / "test_model.pkl"
    result = train_model(DATA_PATH, model_path)

    assert result["train_rows"] == 6400
    assert result["test_rows"] == 1600
    assert 0.0 <= result["accuracy"] <= 1.0
    assert model_path.is_file()

    model = joblib.load(model_path)
    X, _ = load_training_data(str(DATA_PATH))
    assert len(model.predict(X.iloc[[0]])) == 1


def test_training_refuses_to_overwrite_existing_model(tmp_path):
    model_path = tmp_path / "existing_model.pkl"
    original_bytes = b"existing model must remain unchanged"
    model_path.write_bytes(original_bytes)

    with pytest.raises(FileExistsError, match="overwrite=True"):
        train_model(DATA_PATH, model_path)

    assert model_path.read_bytes() == original_bytes


def test_package_imports_from_notebooks_directory():
    import os
    import subprocess
    import sys

    repo_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from cnc_guard.data import load_dataset; "
            "from cnc_guard.features import load_training_data",
        ],
        cwd=repo_root / "notebooks",
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
