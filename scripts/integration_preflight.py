"""Read-only checkout preflight. Passing static checks never proves live integration."""

import ast
import json
import subprocess
from pathlib import Path


def inspect_checkout(root):
    root = Path(root)
    checks = {}
    api = root / "scoring/score_api.py"
    try:
        tree = ast.parse(api.read_text())
        checks["api_parses"] = True
        checks["api_has_unfilled_bodies"] = any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and len(node.body) == 1
            and isinstance(node.body[0], ast.Pass)
            for node in ast.walk(tree)
        )
    except (OSError, SyntaxError):
        checks["api_parses"] = False
        checks["api_has_unfilled_bodies"] = True
    checks["scoring_dockerfile"] = (root / "scoring/Dockerfile").is_file()
    checks["model_at_compose_default"] = (
        root / "models/cnc_failure_model.pkl"
    ).is_file()
    compose = root / "docker-compose.yml"
    checks["compose_services"] = []
    if compose.exists():
        result = subprocess.run(
            ["docker", "compose", "-f", str(compose), "config", "--services"],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if result.returncode == 0:
            checks["compose_services"] = sorted(result.stdout.split())
    required = {"kafka", "filebeat", "nifi", "elasticsearch", "kibana", "scoring-api"}
    checks["missing_services"] = sorted(required - set(checks["compose_services"]))
    checks["static_prerequisites_met"] = all(
        [
            checks["api_parses"],
            not checks["api_has_unfilled_bodies"],
            checks["scoring_dockerfile"],
            checks["model_at_compose_default"],
            not checks["missing_services"],
        ]
    )
    checks["ready"] = False
    checks["live_verified"] = False
    checks["meaning"] = (
        "Read-only static preflight only; ready requires explicit end-to-end event reconciliation and live evidence."
    )
    return checks


if __name__ == "__main__":
    result = inspect_checkout(Path.cwd())
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["static_prerequisites_met"] else 1)
