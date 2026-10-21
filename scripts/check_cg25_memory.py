"""Read-only CG25 coverage, local links/anchors and source hash verification."""

import hashlib
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def local_path(parent, target):
    path = (parent / unquote(target)).resolve()
    require(path.is_relative_to(ROOT), f"Link escapes repository: {target}")
    require(path.is_file(), f"Missing local file: {target}")
    return path


def anchors(text):
    seen = {}
    result = set()
    for heading in re.findall(r"^#{1,6}\s+(.+?)\s*#*\s*$", text, re.MULTILINE):
        slug = re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")
        count = seen.get(slug, 0)
        result.add(f"{slug}-{count}" if count else slug)
        seen[slug] = count + 1
    return result


def check_links(path):
    count = 0
    for target in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
        parts = urlsplit(target)
        require(not parts.scheme and not parts.netloc, f"Nonlocal CG25 link: {target}")
        linked = local_path(path.parent, parts.path) if parts.path else path
        if parts.fragment:
            require(linked.suffix == ".md", f"Unsupported anchor source: {target}")
            require(
                unquote(parts.fragment) in anchors(linked.read_text(encoding="utf-8")),
                f"Missing anchor: {target}",
            )
        count += 1
    return count


def main():
    manifest = json.loads(
        (ROOT / "docs/memoria/manifest.json").read_text(encoding="utf-8")
    )
    source = json.loads((ROOT / "docs/rubrica/fuente.json").read_text(encoding="utf-8"))
    expected = {f"Zereginak!{d['advanced_cell']}" for d in source["descriptors"]}
    memory = (ROOT / "docs/memoria/README.md").read_text(encoding="utf-8")
    rows = re.findall(r"^\| (Zereginak!G\d+) \| (.+)$", memory, re.MULTILINE)
    cells = [cell for cell, _ in rows]
    require(len(cells) == 40 and set(cells) == expected, "Criterion coverage mismatch")
    base = manifest["base_commit"]
    for cell, row in rows:
        fields = [field.strip() for field in row.rstrip("|").split("|")]
        require(len(fields) == 4 and all(fields), f"Incomplete matrix row: {cell}")
        require(f"git show {base[:7]}:" in row, f"Stale matrix revision: {cell}")
        require(fields[-1] == "Pendiente", f"Unsubstantiated human review: {cell}")
    for name, digest in manifest["files"].items():
        path = local_path(ROOT, name)
        require(
            hashlib.sha256(path.read_bytes()).hexdigest() == digest,
            f"Hash mismatch: {name}",
        )
    historical = manifest["historical_snapshot"]
    for name, digest in historical["files"].items():
        data = subprocess.check_output(
            ["git", "show", f"{historical['base_commit']}:{name}"], cwd=ROOT
        )
        require(
            hashlib.sha256(data).hexdigest() == digest,
            f"Historical hash mismatch: {name}",
        )
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", base, "HEAD"], cwd=ROOT, check=True
    )
    require(manifest["human_review"] == "pending", "Human review must remain pending")
    require(
        manifest["active_scope"]
        == {
            "task": "contemporary_classification",
            "rows": 8000,
            "fit": 5600,
            "development_validation": 1200,
            "excluded_previously_inspected_test": 1200,
            "eta_rul": False,
            "final_test_evaluated_by_this_change": False,
        },
        "Active scope mismatch",
    )
    links = sum(check_links(path) for path in (ROOT / "docs/memoria").glob("*.md"))
    print(
        f"PASS: {len(cells)} criteria, {links} local links/anchors, "
        f"{len(manifest['files'])} current and "
        f"{len(historical['files'])} historical hashes"
    )
    print(
        "Documentation only; no technical reruns, CI result "
        "or human acceptance asserted."
    )


if __name__ == "__main__":
    main()
