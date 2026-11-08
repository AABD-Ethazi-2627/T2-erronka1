"""Verify every archive blob against a complete official Git tree, without extraction."""

import argparse
import hashlib
import json
import tarfile
from pathlib import Path, PurePosixPath


def verify(archive, tree_path, commit_path):
    tree = json.loads(tree_path.read_bytes())
    commit = json.loads(commit_path.read_bytes())
    if commit.get("verification", {}).get("verified") is not True:
        raise ValueError("Require the official API's verified commit signature")
    if tree.get("truncated") is not False or tree["sha"] != commit["tree"]["sha"]:
        raise ValueError("Require the complete tree identified by the official commit")
    expected = {row["path"]: row for row in tree["tree"] if row["type"] == "blob"}
    attributes = [name for name in expected if name.endswith(".gitattributes")]
    if attributes != [".gitattributes"] or expected[".gitattributes"]["sha"] != (
        "449125ffc0c4cd718589d3f77cc3d5325c54b923"
    ):
        raise ValueError("Official archive EOL rules require renewed review")
    seen, roots, total, normalized = set(), set(), 0, []
    with tarfile.open(archive, "r:gz") as source:
        for member in source:
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts or not path.parts:
                raise ValueError("Unsafe archive path")
            roots.add(path.parts[0])
            if len(roots) != 1:
                raise ValueError("Multiple archive roots")
            if member.isdir():
                continue
            name = "/".join(path.parts[1:])
            if name not in expected or name in seen:
                raise ValueError("Unexpected or duplicate archive blob: " + name)
            row = expected[name]
            if member.issym() and row["mode"] == "120000":
                payload = member.linkname.encode("utf-8")
            elif member.isfile() and row["mode"] in {"100644", "100755"}:
                if member.size > 256 * 1024**2:
                    raise ValueError("Oversized source blob")
                with source.extractfile(member) as handle:
                    payload = handle.read()
                if bool(member.mode & 0o111) != (row["mode"] == "100755"):
                    raise ValueError("Executable mode mismatch: " + name)
            else:
                raise ValueError("Unexpected archive member type: " + name)
            total += len(payload)
            if total > 2 * 1024**3 or len(seen) >= 30000:
                raise ValueError("Source inventory budget exceeded")
            # This exact official .gitattributes requires *.bat/*.cmd CRLF in
            # archives/worktrees; their authenticated Git blobs use LF. No other
            # byte normalization or missing-file allowance is permitted.
            if path.suffix in {".bat", ".cmd"}:
                if payload.count(b"\n") != payload.count(b"\r\n"):
                    raise ValueError("Archive violates official CRLF rule: " + name)
                payload = payload.replace(b"\r\n", b"\n")
                normalized.append(name)
            blob = b"blob " + str(len(payload)).encode("ascii") + b"\0" + payload
            if hashlib.sha1(blob).hexdigest() != row["sha"]:
                raise ValueError("Git blob mismatch: " + name)
            seen.add(name)
    if seen != set(expected):
        raise ValueError("Archive omits official source blobs")
    return {
        "commit": commit["sha"],
        "tree": tree["sha"],
        "github_commit_signature_verified": commit["verification"]["verified"],
        "files": len(seen),
        "bytes": total,
        "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "all_git_blobs_and_executable_modes_match": True,
        "official_gitattributes_crlf_to_git_lf": normalized,
        "extracted_files": 0,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("tree", type=Path)
    parser.add_argument("commit", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.archive, args.tree, args.commit), indent=2))
