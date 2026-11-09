"""Fetch only the six already pinned SDK experiment JARs from Maven Central."""

import argparse
import hashlib
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
SDK = (
    "sdk",
    "sdk-common",
    "sdk-trace",
    "sdk-metrics",
    "sdk-logs",
    "sdk-extension-autoconfigure-spi",
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    pins = dict(
        line.split("=", 1)
        for line in (HERE / "origin-pins.properties").read_text().splitlines()
        if line.startswith("sha.")
    )
    for artifact in SDK:
        name = f"opentelemetry-{artifact}-1.67.0.jar"
        url = f"https://repo.maven.apache.org/maven2/io/opentelemetry/opentelemetry-{artifact}/1.67.0/{name}"
        with urllib.request.urlopen(url, timeout=30) as response:
            data = response.read(8 * 1024 * 1024)
        if hashlib.sha256(data).hexdigest() != pins["sha." + name]:
            raise ValueError("official SDK hash mismatch: " + name)
        (args.output / name).write_bytes(data)


if __name__ == "__main__":
    main()
