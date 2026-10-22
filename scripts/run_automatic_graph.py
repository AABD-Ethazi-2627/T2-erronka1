"""One NiFi-scheduled Kafka cycle; reuse the canonical durable worker unchanged."""

import argparse
import json
import math
import sqlite3
import uuid
from contextlib import closing
from pathlib import Path
from urllib.parse import quote

import httpx

from scripts.archive_consumer import durable, mkdir
from scripts.build_es_ingest_pipeline import EXPORT, PIPELINE_ID
from scripts.durable_pipeline import encoded
from scripts.platform_io import exclusive_lock
from scripts.run_durable_pipeline import main as run_worker

FIELDS = {
    "root",
    "manifest",
    "source_namespace",
    "source_kind",
    "legacy_source_kind",
    "scoring_url",
    "es_url",
    "es_index",
    "bootstrap_servers",
    "group_id",
    "topic",
    "offset_reset",
    "max_records",
    "max_polls",
    "max_poll_interval_ms",
    "attempts",
    "timeout",
}


def load_config(path):
    config = json.loads(Path(path).read_bytes())
    if not isinstance(config, dict) or set(config) != FIELDS:
        raise ValueError(
            "Automatic graph requires exactly the documented config fields"
        )
    for key in FIELDS - {
        "max_records",
        "max_polls",
        "max_poll_interval_ms",
        "attempts",
        "timeout",
    }:
        if not isinstance(config[key], str) or not config[key].strip():
            raise ValueError(f"Nonempty string required: {key}")
    for key in ("root", "manifest"):
        if not Path(config[key]).is_absolute():
            raise ValueError(f"Absolute path required: {key}")
    if not Path(config["manifest"]).is_file():
        raise ValueError("Pinned manifest must exist; no model generation")
    if config["source_kind"] not in ("lab_fixture", "smb_csv"):
        raise ValueError("Explicit canonical source_kind required")
    if config["offset_reset"] not in ("none", "earliest"):
        raise ValueError("offset_reset must be none or explicitly earliest")
    for key in ("max_records", "max_polls", "max_poll_interval_ms", "attempts"):
        if type(config[key]) is not int or config[key] < 1:
            raise ValueError(f"Positive integer required: {key}")
    timeout = config["timeout"]
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("Positive finite timeout required")
    budget = config["max_records"] * config["attempts"] * timeout * 3
    if config["max_poll_interval_ms"] <= (budget + 60) * 1000:
        raise ValueError("Poll interval must exceed HTTP budget plus 60s disk margin")
    return config


def worker_arguments(config):
    args = []
    for key in (
        "root",
        "manifest",
        "source_namespace",
        "source_kind",
        "legacy_source_kind",
        "scoring_url",
        "es_url",
        "es_index",
        "attempts",
        "timeout",
    ):
        args.extend(("--" + key.replace("_", "-"), str(config[key])))
    args.append("kafka")
    for key in (
        "bootstrap_servers",
        "group_id",
        "topic",
        "offset_reset",
        "max_records",
        "max_polls",
        "max_poll_interval_ms",
    ):
        args.extend(("--" + key.replace("_", "-"), str(config[key])))
    return args


def accounting(root):
    """Observed deliveries, not producer totals or a claim about broker commits."""
    counts = {"observed": 0, "saved": 0, "rejected": 0, "pending": 0}
    database = Path(root) / "pipeline.sqlite3"
    if not database.exists():
        return counts
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as con:
        for outcome, count in con.execute(
            "SELECT outcome, count(*) FROM jobs GROUP BY outcome"
        ):
            name = {None: "pending", "completed": "saved", "rejected": "rejected"}[
                outcome
            ]
            counts[name] += count
            counts["observed"] += count
    return counts


def check_es(config):
    """Require PR74's installed final guard and a pre-created strict index."""
    base = config["es_url"].rstrip("/")
    index = quote(config["es_index"], safe="")
    with httpx.Client(trust_env=False, timeout=config["timeout"]) as client:
        settings = client.get(f"{base}/{index}/_settings")
        settings.raise_for_status()
        actual = settings.json()
        if (
            set(actual) != {config["es_index"]}
            or actual[config["es_index"]]["settings"]["index"].get("final_pipeline")
            != PIPELINE_ID
        ):
            raise ValueError("ES concrete index must require the PR74 final pipeline")
        pipeline = client.get(f"{base}/_ingest/pipeline/{PIPELINE_ID}")
        pipeline.raise_for_status()
        installed = pipeline.json()
        guard = installed.get(PIPELINE_ID)
        if set(installed) != {PIPELINE_ID} or not isinstance(guard, dict):
            raise ValueError("Expected the single pinned ES guard")
        # ES9.5 adds lifecycle timestamps to GET, outside the authored export.
        # Validate their type and remove only these two server-managed fields.
        for key in ("created_date_millis", "modified_date_millis"):
            if key in guard and type(guard.pop(key)) is not int:
                raise ValueError("Invalid ES guard lifecycle metadata")
        if guard != json.loads(EXPORT.read_bytes()):
            raise ValueError("Installed ES guard differs from the pinned export")
        mapping = client.get(f"{base}/{index}/_mapping")
        mapping.raise_for_status()
        if mapping.json()[config["es_index"]]["mappings"].get("dynamic") != "strict":
            raise ValueError("ES mapping must be strict, separately from the guard")


def cycle(config):
    root = Path(config["root"])
    mkdir(root)
    # Held BEFORE constructing/subscribing the Kafka client until after close.
    # This is additional to Pipeline's per-poll worker.lock. Never unlink locks.
    with exclusive_lock(root / "automatic-owner.lock", blocking=False):
        # Freeze transport/group/topic as well as the existing Pipeline config.
        # durable() rejects changed bytes; no reset/reconfiguration command.
        durable(root / "automatic-config.json", encoded(config))
        report = {
            "cycle_id": uuid.uuid4().hex,
            "status": "blocked",
            "source_ack": "worker-only",
        }
        try:
            check_es(config)  # no client joins Kafka if destination setup is wrong
            result = run_worker(worker_arguments(config))
            if result != 0:
                raise RuntimeError(f"Worker exited {result}")
            report["status"] = "completed"
        except Exception as exc:
            # CLI boundary: retain a failed cycle and let NiFi schedule recovery.
            # No status, exception, or FlowFile receipt can commit Kafka here.
            report["error_type"] = type(exc).__name__
            raise
        finally:
            report["accounting"] = accounting(root)
            durable(
                root / "automatic-cycles" / (report["cycle_id"] + ".json"),
                encoded(report),
            )
            print(json.dumps(report), flush=True)
    return 0


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--config", required=True, type=Path)
    args = cli.parse_args(argv)
    return cycle(load_config(args.config))


if __name__ == "__main__":
    raise SystemExit(main())
