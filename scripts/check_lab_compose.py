"""Validate the historical template without a daemon or real credentials."""

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "docs/templates/infra/docker-compose.yaml"
ENV = {
    key: value
    for key, value in os.environ.items()
    if not key.startswith(("CNC_", "COMPOSE_"))
}
ENV.update(
    CNC_NIFI_PASSWORD="validation-only-password",
    CNC_STREAM_DIR=str(ROOT / "tests/fixtures"),
)


def render(overrides=None, missing=None, archive=True):
    env = ENV | (overrides or {})
    if missing:
        env.pop(missing, None)
    command = [
        "docker",
        "compose",
        "--env-file",
        os.devnull,
        "-f",
        str(COMPOSE),
    ]
    if archive:
        command += ["--profile", "historical-archive-only"]
    return subprocess.run(
        command
        + [
            "config",
            "--format",
            "json",
        ],
        env=env,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def check(overrides=None):
    result = render(overrides)
    assert result.returncode == 0, result.stderr
    config = json.loads(result.stdout)
    services = config["services"]
    assert set(services) == {
        "kafka",
        "filebeat",
        "nifi",
        "elasticsearch",
        "kibana",
        "scoring-api",
    }
    for name, service in services.items():
        for port in service.get("ports", []):
            assert port.get("host_ip") == "127.0.0.1", (name, port)
    nifi = services["nifi"]
    assert nifi["image"] == "apache/nifi:1.25.0"
    assert nifi["environment"]["NIFI_WEB_PROXY_HOST"] == (
        "localhost:8443,127.0.0.1:8443"
    )
    assert str(nifi["environment"]["NIFI_WEB_HTTPS_PORT"]) == "8443"
    assert (
        nifi["environment"]["SINGLE_USER_CREDENTIALS_PASSWORD"]
        == (ENV["CNC_NIFI_PASSWORD"])
    )
    assert "NIFI_WEB_HTTP_PORT" not in nifi["environment"]
    assert nifi["ports"][0]["target"] == 8443
    assert services["scoring-api"]["build"]["context"] == str(
        COMPOSE.parent / "scoring"
    )
    assert any(
        volume["source"] == str(ROOT / "models") and volume["read_only"]
        for volume in services["scoring-api"]["volumes"]
    )
    assert any(
        volume["type"] == "bind"
        and volume["source"] == ENV["CNC_STREAM_DIR"]
        and volume["target"] == "/mnt/cnc-stream"
        and volume["read_only"]
        for volume in services["filebeat"]["volumes"]
    )
    assert all(not volume.get("driver_opts") for volume in config["volumes"].values())
    assert not (ROOT / "infra").exists(), "Keep one canonical historical template"


if __name__ == "__main__":
    default = render(archive=False)
    assert default.returncode == 0, default.stderr
    assert not json.loads(default.stdout)["services"], (
        "Historical services must be opt-in"
    )
    check()
    check({"CNC_LAN_BIND_IP": "0.0.0.0", "CNC_NIFI_PROXY_HOST": "untrusted:8443"})
    for key in ("CNC_NIFI_PASSWORD", "CNC_STREAM_DIR"):
        for result in (render(missing=key), render({key: ""})):
            assert result.returncode != 0 and key in result.stderr, key
    print(
        "PASS: private ports, TLS/auth, read-only local input, paths, "
        "required variables"
    )
