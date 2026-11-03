"""Bounded synthetic model/ES doubles; real ASGI canonical ledger, CG15 and GET."""

import argparse
import asyncio
import hashlib
import json
import shutil
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import numpy as np

from scoring.read_models import ReadScope
from scoring.read_storage import ArchiveReader
from scoring.scope import SCOPE
from scoring.score_api import create_app
from scripts.archive_consumer import consume, event_key
from scripts.integration_verify import resources, same_event
from scripts.validate_contracts import contract_hashes


class RiskDouble:
    def predict_proba(self, frame):
        return np.array([[0.2, 0.8]])


class AnomalyDouble:
    def score_samples(self, frame):
        return np.array([-0.5])


class ESDouble:
    data = ()
    down = False

    def rows(self, *args):
        if self.down:
            raise RuntimeError("fixture ES unavailable")
        return self.data


def source_identity():
    source = Path(__file__).resolve().parents[1]
    bundled = source / "BUNDLE_SOURCE.json"
    if bundled.is_file():
        manifest = json.loads((source / "SHA256.json").read_text())
        if "BUNDLE_SOURCE.json" not in manifest:
            raise ValueError("Bundle source metadata is not hash-listed")
        for name, expected in manifest.items():
            path = source / name
            if (
                Path(name).is_absolute()
                or ".." in Path(name).parts
                or path.is_symlink()
                or not path.resolve().is_relative_to(source)
                or not path.is_file()
                or hashlib.sha256(path.read_bytes()).hexdigest() != expected
            ):
                raise ValueError("Extracted bundle hash mismatch: " + name)
        return {
            **json.loads(bundled.read_text()),
            "origin": "bundle_metadata",
            "member_hashes": "verified_not_authenticated",
        }
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=source,
        capture_output=True,
        text=True,
        check=False,
    )
    if revision.returncode:
        return {"revision": None, "dirty": None, "origin": "unversioned_source"}
    dirty = subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=source, text=True
    )
    return {"revision": revision.stdout.strip(), "dirty": bool(dirty), "origin": "git"}


async def run(root):
    identity = source_identity()
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=False)
    manifest = {
        **SCOPE,
        "model_version": "synthetic-integration-only",
        "policy": "f2",
        "versions": {"sklearn": "synthetic"},
        "files": {"rf.pkl": "a" * 64, "if.pkl": "b" * 64},
        "risk_threshold": 0.5,
        "anomaly_threshold": 0.4,
    }
    event = json.loads(Path("contracts/examples/valid/telemetry.json").read_text())
    event.update(
        machine_id="CNC-004",
        process_temp_K=294.15,
        rpm=1801,
        torque_Nm=5.0,
        tool_wear_min=7,
        source={
            "kind": "lab_fixture",
            "uri": "fixture://integration",
            "record_ref": "row-1",
        },
    )
    (root / "fixture.json").write_text(json.dumps(event, indent=2))
    current = ESDouble()
    scope = ReadScope(
        source_uri=event["source"]["uri"],
        model_artifact_sha256="a" * 64,
        policy="f2",
        risk_threshold=0.5,
    )
    archive = root / "archive"
    app = create_app(
        root / "absent.json",
        ledger_path=root / "canonical.sqlite3",
        read_config={
            "scope": scope,
            "current": current,
            "archive": ArchiveReader(archive),
        },
    )
    app.state.models = {"rf.pkl": RiskDouble(), "if.pkl": AnomalyDouble()}
    app.state.manifest = manifest
    end = (
        datetime.fromisoformat(event["timestamp"]) + timedelta(seconds=1)
    ).isoformat()
    statuses = {}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://fixture"
    ) as client:
        response = await client.post("/predict", json=event)
        assert response.status_code == 200, response.text
        raw = response.content
        (root / "canonical.json").write_bytes(raw)
        prediction = response.json()
        # Treat response as lost before persistence, then repeat the identical request.
        replay = await client.post("/predict", json=event)
        assert replay.content == raw
        ack = []
        consume(archive, [("normal", "prediction", raw)], lambda: ack.append(True))
        consume(
            archive,
            [("normal", "prediction", replay.content)],
            lambda: ack.append(True),
        )
        assert len(ack) == 2
        statuses["normal"] = statuses["replay_uncertain_http"] = "passed_ASGI"
        invalid = await client.post("/predict", json={**event, "rpm": -1})
        assert invalid.status_code == 422
        rejected = consume(
            root / "invalid-archive", [("bad", "prediction", b"{}")], lambda: None
        )
        assert rejected["rejected"] == 1
        statuses["invalid"] = "passed_contract_rejection; CSV worker covered separately"
        current.data = [prediction]
        snap = await client.get("/api/makinak", params={"as_of": end})
        hist = await client.get("/api/historikoa/CNC-004", params={"hasta": end})
        assert snap.status_code == hist.status_code == 200, hist.text
        es = {"_id": event_key("prediction", prediction), "_source": prediction}
        (root / "es-double.json").write_text(json.dumps(es, indent=2))
        (root / "get-snapshot.json").write_bytes(snap.content)
        (root / "get-history.json").write_bytes(hist.content)
        reconciled = same_event(
            raw, archive, es, snap.json()[0], hist.json()["metadata"]["events"][0]
        )
        current.down = True
        assert (
            await client.get("/api/makinak", params={"as_of": end})
        ).status_code == 503
        current.down = False
        statuses["es_down"] = "passed_reader_double_503"
        app.state.models = None
        assert (await client.post("/predict", json=event)).status_code == 503
        statuses["api_down"] = (
            "passed_model_unready_503; transport outage covered separately"
        )
        shutil.copytree(archive, root / "pristine-archive")
        target = next(archive.glob("prediction/**/*.parquet"))
        target.write_bytes(b"controlled corruption of own fixture")
        before = len(ack)
        try:
            consume(archive, [("normal", "prediction", raw)], lambda: ack.append(True))
        except ValueError:
            pass
        else:
            raise AssertionError("Corruption accepted")
        assert len(ack) == before
        assert (
            await client.get("/api/historikoa/CNC-004", params={"hasta": end})
        ).status_code == 503
        statuses["corruption"] = "passed_no_ACK_and_GET_503"
    result = {
        "created_utc": datetime.now(UTC).isoformat(),
        "code_sha": identity["revision"],
        "source_identity": identity,
        "tool_hashes": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in Path("scripts").glob("integration_*.py")
        },
        "contracts": contract_hashes(),
        "model": manifest,
        "resources": resources(root),
        "scenarios": statuses,
        "reconciliation_before_corruption": reconciled,
        "boundaries": {
            "prediction_requests": {
                "sent": 4,
                "accepted": 2,
                "rejected": 1,
                "pending": 1,
            },
            "definition": "replay counted as a request; unready request pending; not Kafka offsets",
        },
        "doubles": ["model", "ES reader", "ASGI transport"],
        "not_run": ["Filebeat", "Kafka", "NiFi", "Docker images", "browser", "SMB"],
        "archive_final_state": "intentionally_corrupt_own_fixture",
    }
    (root / "result.json").write_text(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--output", type=Path, required=True)
    print(json.dumps(asyncio.run(run(cli.parse_args().output)), indent=2))
