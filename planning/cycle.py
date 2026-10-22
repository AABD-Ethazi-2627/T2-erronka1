"""Transactional in-memory batch update; caller publishes checkpoints atomically."""

from copy import deepcopy

from planning.maintenance import instant
from planning.online import OnlineForecaster


def update_batch(rows, manifest, *, batch_id, source_hash, checkpoint=None):
    if (
        not isinstance(batch_id, str)
        or not batch_id.strip()
        or not isinstance(source_hash, str)
        or len(source_hash) != 64
        or any(c not in "0123456789abcdef" for c in source_hash)
    ):
        raise ValueError("Batch identity and SHA256 required")
    if checkpoint:
        snapshot = checkpoint.get(
            "state", checkpoint.get("state_after_acceptance", checkpoint)
        )
        model = OnlineForecaster.restore(snapshot, manifest)
        result = {
            "schema_version": 1,
            "state": deepcopy(snapshot),
            "processed_batches": deepcopy(checkpoint.get("processed_batches", {})),
            "last_batch_evaluation": deepcopy(
                checkpoint.get("last_batch_evaluation", [])
            ),
            "last_batch_diagnostics": deepcopy(
                checkpoint.get("last_batch_diagnostics", [])
            ),
            "scope": "LAB_SHADOW_ONLY",
            "runtime_promotion_allowed": False,
        }
        if batch_id in result["processed_batches"]:
            if result["processed_batches"][batch_id] != source_hash:
                raise ValueError("Previously processed batch changed")
            return result
    else:
        model = OnlineForecaster(manifest)
        result = {
            "schema_version": 1,
            "processed_batches": {},
            "state": None,
            "last_batch_evaluation": [],
        }
    columns = manifest["columns"]
    source = sorted(
        rows,
        key=lambda r: (
            instant(r[columns["timestamp"]]),
            r[columns["asset"]],
            r[columns["lifecycle"]],
        ),
    )
    if not source:
        raise ValueError("Empty observation batch")
    observations = [model.observe(row) for row in source]
    result["state"] = model.snapshot()
    result["processed_batches"][batch_id] = source_hash
    result["last_batch_evaluation"] = [
        r["evaluated_forecast"] for r in observations if r["evaluated_forecast"]
    ]
    result["last_batch_diagnostics"] = [
        {
            "asset": row[columns["asset"]],
            "lifecycle": row[columns["lifecycle"]],
            "observed_at": row[columns["timestamp"]],
            "sensors": output.get("diagnostics", {}),
        }
        for row, output in zip(source, observations, strict=True)
        if output.get("diagnostics")
    ]
    result["scope"] = "LAB_SHADOW_ONLY"
    result["runtime_promotion_allowed"] = False
    return result
