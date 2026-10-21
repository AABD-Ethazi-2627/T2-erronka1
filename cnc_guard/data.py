"""Use the approved source and exact partitions of the active scoring path."""

from pathlib import Path

from scoring.preparation import split_development
from scoring.scope import load_training_source


def load_dataset(path: str | Path):
    return load_training_source(path)


def load_training_partitions(path: str | Path):
    """Return fit, development validation and the previously inspected exclusion."""
    return split_development(load_dataset(path))
