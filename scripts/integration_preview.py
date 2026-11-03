"""Loopback-only browser rehearsal: real GET/CG15, frozen synthetic ES fixture."""

import argparse
import json
from pathlib import Path

from fastapi import FastAPI

from scoring.read_api import create_read_router
from scoring.read_models import ReadScope
from scoring.read_storage import ArchiveReader
from scripts.integration_fixture import ESDouble


def create_preview(root):
    root = Path(root).resolve()
    result = json.loads((root / "result.json").read_text())
    if result.get("doubles") != ["model", "ES reader", "ASGI transport"]:
        raise ValueError("Expected bounded synthetic integration fixture")
    row = json.loads((root / "canonical.json").read_text())
    if row["source"]["uri"] != "fixture://integration":
        raise ValueError("Preview accepts only the owned synthetic source")
    current = ESDouble()
    current.data = [row]
    app = FastAPI(title="Synthetic CNC integration browser rehearsal")
    app.include_router(
        create_read_router(
            ReadScope(
                source_uri=row["source"]["uri"],
                model_artifact_sha256=row["model_artifact_sha256"],
                policy=row["policy"],
            ),
            current=current,
            archive=ArchiveReader(root / "pristine-archive"),
        )
    )
    return app


if __name__ == "__main__":
    import uvicorn

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", required=True, type=Path)
    parser.add_argument("--port", type=int, default=18271)
    args = parser.parse_args()
    uvicorn.run(create_preview(args.fixture), host="127.0.0.1", port=args.port)
