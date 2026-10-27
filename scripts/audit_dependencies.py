"""Audit every lock row and the pinned uv tool against official PyPI metadata.

No installation, credentials, private index or deployment is involved. A local
patch is hash/provenance checked, but the advisory feed covers its upstream only.
"""

import argparse
import hashlib
import json
import re
import time
import tomllib
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from email.parser import BytesParser
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from zipfile import BadZipFile, ZipFile

ROOT = Path(__file__).resolve().parents[1]


def validate_metadata_url(url):
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "pypi.org"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in (None, 443)
        or not parsed.path.startswith("/pypi/")
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Metadata URL is outside the approved PyPI HTTPS origin")


class PyPIRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_metadata_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


PYPI_OPENER = build_opener(PyPIRedirectHandler())


def fetch_json(url):
    validate_metadata_url(url)
    for attempt in range(3):
        try:
            request = Request(
                url, headers={"User-Agent": "cnc-guard-dependency-audit/1"}
            )
            with PYPI_OPENER.open(request, timeout=15) as response:
                validate_metadata_url(response.geturl())
                payload = response.read(32 * 1024 * 1024 + 1)
            if len(payload) > 32 * 1024 * 1024:
                raise ValueError("Metadata exceeds the size limit")
            return json.loads(payload)
        except (OSError, ValueError):
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


def advisories(data):
    records = data["vulnerabilities"]
    if not isinstance(records, list):
        raise TypeError("Missing advisory list")
    groups = []
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("id"), str):
            raise TypeError("Malformed advisory")
        aliases = record.get("aliases", [])
        if not isinstance(aliases, list) or any(
            not isinstance(a, str) for a in aliases
        ):
            raise ValueError("Malformed aliases")
        if record.get("withdrawn") is not None and not isinstance(
            record["withdrawn"], str
        ):
            raise TypeError("Malformed withdrawal date")
        if record.get("withdrawn"):
            continue
        identifiers = {record["id"], *aliases}
        matches = [group for group in groups if group & identifiers]
        for group in matches:
            identifiers |= group
            groups.remove(group)
        groups.append(identifiers)
    return records, [sorted(group) for group in groups]


def upstream_version(row, root):
    source = row["source"]
    if source == {"registry": "https://pypi.org/simple"}:
        return row["version"], "registry"
    if source == {"virtual": "."}:
        return None, "project"
    if set(source) != {"path"} or row["name"] != "kafka-python":
        raise ValueError("Uncovered lock source")
    wheel = (root / source["path"]).resolve()
    if (
        not wheel.is_relative_to(root.resolve())
        or not wheel.is_relative_to((root / "vendor").resolve())
        or not wheel.is_file()
    ):
        raise ValueError("Local wheel must be inside vendor")
    provenance = json.loads((root / "vendor/kafka-python-provenance.json").read_text())
    patched = provenance["patched"]
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    hashes = {item["hash"] for item in row["wheels"]}
    if (
        patched["filename"] != wheel.name
        or patched["version"] != row["version"]
        or patched["sha256"] != digest
        or hashes != {"sha256:" + digest}
    ):
        raise ValueError("Local wheel hash/provenance mismatch")
    return provenance["upstream"]["version"], "local-upstream-only"


def audit(rows, root=ROOT, fetch=fetch_json, *, latest=False):
    def inspect(row):
        result = {"name": row["name"], "version": row["version"]}
        if "manifest" in row:
            result["manifest"] = row["manifest"]
        try:
            version, status = upstream_version(row, root)
            result["status"] = status
            if version is None:
                return result
            if not re.fullmatch(r"[A-Za-z0-9_.-]+", row["name"]) or not re.fullmatch(
                r"[A-Za-z0-9_.+!-]+", version
            ):
                raise ValueError("Invalid public package identifier")
            base = "https://pypi.org/pypi/" + row["name"]
            result["advisory_url"] = base + "/" + version + "/json"
            data = fetch(result["advisory_url"])
            result["advisories"], result["active_advisory_groups"] = advisories(data)
            result["audited_version"] = version
            result["requires_python"] = data["info"].get("requires_python")
            if status == "local-upstream-only":
                result["upstream_requires_python"] = result["requires_python"]
                wheel = root / row["source"]["path"]
                with ZipFile(wheel) as archive:
                    metadata = [
                        name
                        for name in archive.namelist()
                        if name.endswith(".dist-info/METADATA")
                    ]
                    if len(metadata) != 1:
                        raise ValueError("Ambiguous local wheel metadata")
                    headers = BytesParser().parsebytes(archive.read(metadata[0]))
                if (
                    headers["Name"] != row["name"]
                    or headers["Version"] != row["version"]
                ):
                    raise ValueError("Local wheel metadata does not match lock")
                result["requires_python"] = headers["Requires-Python"]
                result["limit"] = (
                    "Feed covers upstream; local changes require review and wheel regressions"
                )
            if latest:
                current = fetch(base + "/json")
                _, groups = advisories(current)
                result["latest"] = {
                    "version": current["info"]["version"],
                    "requires_python": current["info"].get("requires_python"),
                    "active_advisory_groups": groups,
                }
        except (OSError, ValueError, KeyError, TypeError, BadZipFile) as error:
            # Do not echo arbitrary network error strings or source URLs.
            result.update(status="error", error=type(error).__name__)
        return result

    with ThreadPoolExecutor(max_workers=4) as pool:
        packages = list(pool.map(inspect, rows))
    return {
        "schema": 1,
        "checked_at": datetime.now(UTC).isoformat(),
        "passed": all(
            row["status"] != "error" and not row.get("active_advisory_groups")
            for row in packages
        )
        and bool(packages),
        "coverage": "Every uv.lock row, including optional groups, platform markers and local sources; separate research pins and uv additionally",
        "limit": "Advisory absence is not proof of safety or local patch correctness",
        "packages": packages,
    }


def uv_tool_version(root=ROOT):
    images = json.loads((root / "deploy/images.json").read_text())
    match = re.fullmatch(
        r"ghcr.io/astral-sh/uv:([0-9.]+)@sha256:[0-9a-f]{64}", images["uv"]
    )
    if match is None:
        raise ValueError("Cannot identify the pinned uv tool")
    consumers = 0
    declared = 0
    for workflow in (root / ".github/workflows").glob("*.yml"):
        content = workflow.read_text()
        declared += content.count("astral-sh/setup-uv@")
        for step in re.split(r"(?m)^\s*- uses:", content):
            if not step.startswith(" astral-sh/setup-uv@"):
                continue
            consumers += 1
            version = re.search(r"(?m)^\s+version:\s*['\"]?([0-9.]+)['\"]?\s*$", step)
            if version is None or version[1] != match[1]:
                raise ValueError("CI uv version differs from the audited image pin")
    if not consumers or consumers != declared:
        raise ValueError("Cannot account for every pinned CI uv consumer")
    return match[1]


def requirements_rows(path):
    rows = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(
            r"([A-Za-z0-9_.-]+)==([A-Za-z0-9_.+!-]+)"
            r"(?:\s*;\s*sys_platform\s*==\s*'(?:win32|linux)')?",
            line,
        )
        if match is None:
            raise ValueError("Research requirements need exact public package pins")
        rows.append(
            {
                "name": match[1],
                "version": match[2],
                "source": {"registry": "https://pypi.org/simple"},
            }
        )
    if not rows:
        raise ValueError("Research requirements contain no pins")
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--latest",
        action="store_true",
        help="Also record current PyPI release metadata",
    )
    parser.add_argument(
        "--output", type=Path, help="Create a new report; refuse to overwrite evidence"
    )
    args = parser.parse_args(argv)
    rows = tomllib.loads((ROOT / "uv.lock").read_text())["package"]
    for row in rows:
        row["manifest"] = "uv.lock"
    research = ROOT / "scripts/ml_study_requirements.txt"
    if research.exists():
        additional = requirements_rows(research)
        for row in additional:
            row["manifest"] = "scripts/ml_study_requirements.txt"
        rows.extend(additional)
    version = uv_tool_version()
    rows.append(
        {
            "name": "uv",
            "version": version,
            "source": {"registry": "https://pypi.org/simple"},
            "manifest": "CI/Docker uv tool",
        }
    )
    report = audit(rows, latest=args.latest)
    encoded = json.dumps(report, indent=2) + "\n"
    if args.output:
        with args.output.open("x") as destination:
            destination.write(encoded)
    else:
        print(encoded, end="")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
