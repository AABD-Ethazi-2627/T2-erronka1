"""Opt-in CG32 extension. Never use against shared services; budgets unchanged."""

import json
from pathlib import Path

import httpx

from scripts import cg32_lab as lab
from scripts.integration_verify import check_compose, check_wiring


class IntegrationLab(lab.Lab):
    def compose(self, *args, run=None, bundle=None, check=True):
        if args[-1:] == ("stop",) and not run and self.state.get("runs"):
            run = self.state["runs"][-1]
        runtime = str(Path(self.state["python"]).parent.parent)
        services = {
            "nifi": {"volumes": [f"{runtime}:{runtime}:ro"]},
        }
        if run:
            directory = self.root / "runs" / run
            graph = json.loads((directory / "graph.json").read_text())
            manifest = json.loads(Path(graph["manifest"]).read_text())
            alias = graph["es_index"] + "-read"
            read = {
                "scope": {
                    "source_uri": f"kafka://{graph['source_namespace']}/{graph['topic']}",
                    "model_artifact_sha256": manifest["files"]["rf.pkl"],
                    "policy": manifest["policy"],
                },
                "elasticsearch": {"url": graph["es_url"], "index": alias},
                "archive_root": "/archive",
            }
            (directory / "read.json").write_text(json.dumps(read, indent=2))
            services["api"] = {
                "environment": {"CNC_READ_CONFIG": str(directory / "read.json")},
                # Shadow the writable runs mount at BOTH accessible archive paths.
                "volumes": [
                    f"{graph['root']}/archive:/archive:ro",
                    f"{graph['root']}/archive:{graph['root']}/archive:ro",
                ],
            }
            if getattr(self, "view_mode", False):
                services["api"]["command"] = [
                    "/usr/bin/python3.11",
                    "-m",
                    "uvicorn",
                    "scoring.score_api:app",
                    "--host",
                    "0.0.0.0",
                    "--port",
                    "8000",
                ]
                services["api"]["environment"].update(
                    MODEL_MANIFEST="/bundle/manifest.json",
                    SCORING_LEDGER=str(directory / "api-ledger.sqlite3"),
                )
            services["streamlit"] = {
                "image": "python:3.11-slim",
                "user": "1000:1000",
                "working_dir": str(lab.REPO),
                "command": [
                    self.state["python"],
                    "-m",
                    "streamlit",
                    "run",
                    "dashboard_laneki/app.py",
                    "--server.address=0.0.0.0",
                ],
                "environment": {
                    "LANEKI_MODE": "api",
                    "LANEKI_API_URL": "http://api:8000/api",
                    "PYTHONDONTWRITEBYTECODE": "1",
                },
                "volumes": [
                    f"{lab.REPO}:{lab.REPO}:ro",
                    f"{runtime}:{runtime}:ro",
                    f"{self.state['uv_python']}:{self.state['uv_python']}:ro",
                ],
                "ports": ["127.0.0.1::8501"],
                "mem_limit": "512m",
                "cap_drop": ["ALL"],
                "security_opt": ["no-new-privileges:true"],
                "profiles": ["dashboard"],
            }
            if args[:2] == ("up", "-d") and "api" in args:
                Path(graph["root"], "archive").mkdir(exist_ok=True)
                result = lab.sh(
                    "docker",
                    "compose",
                    "-f",
                    str(lab.COMPOSE),
                    "--env-file",
                    "/dev/null",
                    "run",
                    "--rm",
                    "--no-deps",
                    "--entrypoint",
                    "/usr/bin/python3.11",
                    "-w",
                    "/app",
                    "-e",
                    "PYTHONPATH=/app",
                    "api",
                    "-c",
                    "import duckdb,pyarrow,httpx; from scripts.duckdb_output import *; "
                    'assert duckdb.__version__ == "2.0.0"; '
                    'print("integration-imports-ok")',
                    env=self.env(run, bundle),
                )
                # Actual image smoke is mandatory; host imports are not evidence.
                check_wiring(
                    graph,
                    read,
                    manifest,
                    services,
                    {
                        "imports_ok": "integration-imports-ok" in result.stdout,
                        "duckdb": "2.0.0",
                    },
                )
                with httpx.Client(timeout=30, trust_env=False) as client:
                    from scripts.run_automatic_graph import check_es

                    check_es({**graph, "es_url": self.state["es_url"]})
                    client.post(
                        self.state["es_url"] + "/_aliases",
                        json={
                            "actions": [
                                {"add": {"index": graph["es_index"], "alias": alias}}
                            ]
                        },
                    ).raise_for_status()
                (directory / "candidate-data-view.json").write_text(
                    json.dumps(
                        {
                            "data_view": {
                                "title": alias,
                                "name": alias,
                                "timeFieldName": "timestamp",
                            }
                        },
                        indent=2,
                    )
                )
        overlay = self.root / "integration-compose.json"
        overlay.write_text(json.dumps({"services": services}, indent=2))
        if run and args[:2] == ("up", "-d") and "api" in args:
            resolved = lab.sh(
                "docker",
                "compose",
                "-f",
                str(lab.COMPOSE),
                "-f",
                str(overlay),
                "--env-file",
                "/dev/null",
                "--profile",
                "run",
                "--profile",
                "dashboard",
                "config",
                "--format",
                "json",
                env=self.env(run, bundle),
            )
            check_compose(
                json.loads(resolved.stdout), graph, self.state["python"], str(lab.REPO)
            )
        return lab.sh(
            "docker",
            "compose",
            "-f",
            str(lab.COMPOSE),
            "-f",
            str(overlay),
            "--env-file",
            "/dev/null",
            *args,
            env=self.env(run, bundle),
            check=check,
        )


def view(root, run, bundle, identity_record=None):
    """Restart only own API/UI for parent browser acceptance after measured run."""
    lab.preflight()
    instance = IntegrationLab(root)
    lab.verify_bundle(bundle / "manifest.json", identity_record)
    if run not in instance.state["runs"]:
        raise ValueError("Run is not owned by this lab")
    instance.view_mode = True
    instance.compose(
        "up", "-d", "--no-deps", "api", "streamlit", run=run, bundle=bundle
    )
    print(
        instance.compose(
            "port", "streamlit", "8501", run=run, bundle=bundle
        ).stdout.strip()
    )


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "view":
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("view")
        parser.add_argument("--lab", type=Path, required=True)
        parser.add_argument("--run", required=True)
        parser.add_argument("--bundle", type=Path, required=True)
        parser.add_argument("--identity-record", type=Path)
        args = parser.parse_args()
        view(args.lab, args.run, args.bundle, args.identity_record)
    else:
        lab.main(lab_class=IntegrationLab)
