"""Read immutable image references and reject drift in active Compose/build files."""

import argparse
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_images(root=ROOT):
    images = json.loads((root / "deploy/images.json").read_text())
    if not images or any(
        not isinstance(value, str)
        or not re.fullmatch(r"[^\s@]+:[^\s@]+@sha256:[0-9a-f]{64}", value)
        for value in images.values()
    ):
        raise ValueError("Every image needs an explicit tag and SHA-256 digest")
    return images


def read_build_targets(root=ROOT):
    targets = json.loads((root / "deploy/build-targets.json").read_text())
    if not targets or any(
        not isinstance(key, str)
        or not isinstance(value, str)
        or Path(value).is_absolute()
        or not (root / value).is_file()
        for key, value in targets.items()
    ):
        raise ValueError("Every build target needs a repository-relative Dockerfile")
    return targets


def image(name):
    return read_images()[name]


def compose(root, path, profiles=()):
    # No credentials or private environment are needed for static rendering.
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("COMPOSE_", "CNC_", "CG14_", "NIFI_", "SINGLE_USER_"))
    }
    env.update(
        NIFI_SENSITIVE_PROPS_KEY="validation-only-key-never-a-real-secret",
        SINGLE_USER_CREDENTIALS_USERNAME="validation-only",
        SINGLE_USER_CREDENTIALS_PASSWORD="validation-only-password",
        CG32_PROJECT="validation-cg32",
        CG32_KAFKA_PORT="19092",
        CG32_NIFI_PORT="18443",
        CG32_LAB="/validation/lab",
        CG32_REPO="/validation/repo",
        CG32_UV_PYTHON="/validation/python",
        CG32_BUNDLE="/validation/bundle",
        CG32_RUN="validation-run",
    )
    args = ["docker", "compose", "--env-file", os.devnull, "-f", str(root / path)]
    for profile in profiles:
        args += ["--profile", profile]
    result = subprocess.run(
        args + ["config", "--no-env-resolution", "--format", "json"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)["services"]


def check(root=ROOT):
    images = read_images(root)
    build_targets = read_build_targets(root)
    errors = []
    specifications = [
        (
            "docker-compose.yml",
            ("dashboard",),
            {
                "kafka-init": "kafka",
                "kafka": "kafka",
                "nifi": "nifi",
                "elasticsearch": "elasticsearch",
                "kibana": "kibana",
                "filebeat": "filebeat",
            },
        ),
        (
            "deploy/cg14/compose.yaml",
            ("integration-mocks", "kafka-test"),
            {"nifi": "nifi", "kafka-test": "kafka", "mock-predict": "mock-python"},
        ),
    ]
    if (root / "deploy/cg32/compose.yaml").is_file():
        specifications.append(
            (
                "deploy/cg32/compose.yaml",
                ("run", "dashboard"),
                {
                    "kafka": "kafka",
                    "filebeat": "filebeat",
                    "elasticsearch": "elasticsearch",
                    "kibana": "kibana",
                    "api": "api",
                    "nifi": "nifi",
                },
            )
        )
    optional_image_files = {
        "docker-compose.lan.yml": {"haproxy": "haproxy"},
    }
    for path, expected in optional_image_files.items():
        file = root / path
        if not file.is_file():
            continue
        text = file.read_text()
        for service, key in expected.items():
            if "image: " + images[key] not in text:
                errors.append(f"{path}: {service} differs from deploy/images.json")
    for path, profiles, expected in specifications:
        actual = compose(root, path, profiles)
        for service, key in expected.items():
            config = actual.get(service, {})
            if key in build_targets:
                if config.get("build", {}).get("dockerfile") != build_targets[key]:
                    errors.append(
                        f"{path}: {service} differs from deploy/build-targets.json"
                    )
            elif config.get("image") != images[key]:
                errors.append(f"{path}: {service} differs from deploy/images.json")
        for service, config in actual.items():
            if "image" in config and config["image"] not in images.values():
                errors.append(f"{path}: {service} has an unreviewed image")
            if (
                "build" in config
                and config["build"].get("dockerfile") not in build_targets.values()
            ):
                errors.append(f"{path}: {service} has an unreviewed build")
    dockerfile = (root / build_targets["api"]).read_text()
    for key in ("python",):
        if "FROM " + images[key] not in dockerfile:
            errors.append(f"scoring/Dockerfile: {key} differs from deploy/images.json")
    for key in (
        "elasticsearch",
        "filebeat",
        "kafka",
        "kibana",
        "mock-python",
        "nifi",
        "python",
        "wolfi",
    ):
        dockerfile = (root / build_targets[key]).read_text()
        if "FROM " + images[key] not in dockerfile:
            errors.append(
                f"{build_targets[key]}: {key} differs from deploy/images.json"
            )
    filebeat = (root / build_targets["filebeat"]).read_text()
    if "FROM " + images["go"] not in filebeat:
        errors.append(
            "deploy/images/filebeat.Dockerfile: go differs from deploy/images.json"
        )
    nifi = (root / build_targets["nifi"]).read_text()
    for key in ("wolfi",):
        if "FROM " + images[key] not in nifi:
            errors.append(
                f"deploy/images/nifi.Dockerfile: {key} differs from deploy/images.json"
            )
    stage = (root / "deploy/images/uv-stage.Dockerfile").read_text()
    uv_version = images["uv"].split(":", 1)[1].split("@", 1)[0]
    if f"/refs/tags/{uv_version}.tar.gz" not in stage:
        errors.append("Patched uv source version differs from upstream inventory")
    for key in ("api", "nifi", "uv"):
        if not (root / build_targets[key]).read_text().startswith(stage):
            errors.append(f"{build_targets[key]}: patched uv source stage differs")
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if args.check:
        errors = check()
        if errors:
            parser.exit(1, "\n".join(errors) + "\n")
        print("Active image pins match the immutable inventory")
    else:
        print(json.dumps(read_images()))


if __name__ == "__main__":
    main()
