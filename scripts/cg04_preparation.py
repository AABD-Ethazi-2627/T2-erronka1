"""Index-only reconciliation of CG04 with the active path. No fit or scoring."""

import hashlib
import json

from sklearn.model_selection import train_test_split

from cnc_guard.data import load_dataset, load_training_partitions
from scoring.preparation import SEED
from scoring.scope import APPROVED_SOURCE_SHA256


def inspect_partitions(path="data/ai4i2020_train.csv"):
    frame = load_dataset(path)
    train, validation, excluded = load_training_partitions(path)
    legacy_fit, legacy_validation = train_test_split(
        frame, test_size=0.2, random_state=SEED, stratify=frame.machine_failure
    )
    sets = [set(part.index) for part in (train, validation, excluded)]
    if any(sets[a] & sets[b] for a, b in [(0, 1), (0, 2), (1, 2)]):
        raise ValueError("Partitions must be disjoint")
    if set.union(*sets) != set(frame.index):
        raise ValueError("Partitions must cover the approved source")

    def membership(part):
        indices = part.index.tolist()
        return {
            "rows": len(indices),
            "ordered_index_sha256": hashlib.sha256(
                json.dumps(indices, separators=(",", ":")).encode("ascii")
            ).hexdigest(),
        }

    return {
        "scope": "Index membership only; no fit, predictions or test metrics",
        "source_sha256": APPROVED_SOURCE_SHA256,
        "active": {
            "fit": membership(train),
            "development_validation": membership(validation),
            "excluded_previously_inspected_test": membership(excluded),
            "pairwise_disjoint": True,
            "complete_coverage": True,
            "excluded_rows_in_fit": len(sets[0] & sets[2]),
        },
        "PR43_exercise_80_20": {
            "fit_rows": len(legacy_fit),
            "development_validation_rows": len(legacy_validation),
            "previously_excluded_rows_in_fit": len(sets[2] & set(legacy_fit.index)),
            "promotion_compatible": False,
        },
    }


if __name__ == "__main__":
    print(json.dumps(inspect_partitions(), indent=2))
