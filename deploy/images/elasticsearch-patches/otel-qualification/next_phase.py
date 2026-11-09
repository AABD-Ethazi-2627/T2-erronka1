"""Plan only: print exact commands for the coordinator's next finite VM slots."""

import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "_es_next_reserved", HERE / "run_reserved.py"
)
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)
BASE = Path("/opt/cnc-guard/evidence/es-otel-qualification-20261106")
TOOLS = BASE / "next-source/deploy/images/elasticsearch-patches/otel-qualification"
PROOF = BASE / "stage-01"


def stage_command():
    cmd = r.command("cnc-es-otel-stage-UNIQUE", TOOLS)
    index = cmd.index("--entrypoint")
    cmd[index:index] = ["--mount", f"type=bind,src={PROOF},dst=/proof"]
    cmd[cmd.index("/tools/ModuleAudit.java")] = "/tools/StageInputs.java"
    cmd.append("/proof/input")
    cmd[cmd.index("cnc.es-otel-qualification=inventory")] = (
        "cnc.es-otel-qualification=stage"
    )
    return cmd


def loader_command(variant):
    if variant not in ("current", "sdk-six"):
        raise ValueError("unknown loader variant")
    cmd = r.command("cnc-es-otel-loader-" + variant + "-UNIQUE", TOOLS)
    index = cmd.index("/tools/ModuleAudit.java")
    cmd[index:index] = [
        "--module-path",
        "/usr/share/elasticsearch/lib",
        "--add-modules",
        "ALL-MODULE-PATH",
    ]
    cmd[cmd.index("/tools/ModuleAudit.java")] = "/tools/EsLoaderProbe.java"
    if variant == "sdk-six":
        index = cmd.index("--entrypoint")
        cmd[index:index] = [
            "--mount",
            f"type=bind,src={BASE}/sdk-six-01/apm,dst=/usr/share/elasticsearch/modules/apm,readonly",
        ]
    cmd.extend([variant, "/tools/origin-pins.properties"])
    cmd[cmd.index("cnc.es-otel-qualification=inventory")] = (
        "cnc.es-otel-qualification=loader"
    )
    return cmd


if __name__ == "__main__":
    print(
        json.dumps(
            {
                "status": "prepared-not-executed",
                "replacement": None,
                "runtime_approved": False,
                "next_slot": "stage-only",
                "stage_command": stage_command(),
                "stage_requirements": [
                    "coordinator-granted slot",
                    "common nonblocking finite lock",
                    "6 GiB available / 20 GiB free preflight",
                    "fresh proof directory stage-01",
                    "175-second container wall timeout",
                    "snapshot exact next-source and input hashes",
                    "verify copied selected93JARs against inventory-01 hashes",
                    "seal all11module/SPI and bootlib paths/hashes",
                    "recheck source/image identity; remove only unique owned container",
                ],
                "later_loader_commands": {
                    v: loader_command(v) for v in ("current", "sdk-six")
                },
                "later_requirements": [
                    "compile against actual ES image/JDK27; retain any harness failure",
                    "private sixSDK tree only after official cached-JAR hashes pass",
                    "full published/mediated closure remains a separate real-Maven phase",
                    "loader probe does not initialize ES plugin/exporter consumers or establish entitlement behavior",
                    "no exporter traffic, agent attach or ES startup",
                ],
            },
            indent=2,
        )
    )
