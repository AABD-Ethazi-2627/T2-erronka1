"""Authentication and archive-tampering controls for the Filebeat source pin."""

import hashlib
import importlib.util
import io
import json
import tarfile
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1] / "deploy/images/filebeat-source"
spec = importlib.util.spec_from_file_location(
    "filebeat_source_verify", HERE / "verify_archive.py"
)
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


@pytest.fixture
def inputs(tmp_path):
    files = {
        ".gitattributes": (HERE / "upstream-gitattributes.txt").read_bytes(),
        "source.go": b"package main\n",
        "make.bat": b"@echo off\n",
    }
    tree = {
        "sha": "a" * 40,
        "truncated": False,
        "tree": [
            {
                "path": name,
                "mode": "100644",
                "type": "blob",
                "sha": hashlib.sha1(
                    b"blob " + str(len(raw)).encode() + b"\0" + raw
                ).hexdigest(),
            }
            for name, raw in files.items()
        ],
    }
    commit = {
        "sha": "b" * 40,
        "tree": {"sha": tree["sha"]},
        "verification": {"verified": True},
    }
    tree_path, commit_path = tmp_path / "tree.json", tmp_path / "commit.json"
    tree_path.write_text(json.dumps(tree))
    commit_path.write_text(json.dumps(commit))
    files["make.bat"] = files["make.bat"].replace(b"\n", b"\r\n")

    def archive(members=None, executable=False):
        target = tmp_path / "source.tar.gz"
        with tarfile.open(target, "w:gz") as output:
            for name, data in (files if members is None else members).items():
                info = tarfile.TarInfo("source/" + name)
                info.size, info.mode = len(data), 0o755 if executable else 0o644
                output.addfile(info, io.BytesIO(data))
        return target

    return files, archive, tree_path, commit_path


def test_exact_git_tree_and_official_eol_conversion(inputs):
    _, archive, tree, commit = inputs
    result = verifier.verify(archive(), tree, commit)
    assert result["files"] == 3
    assert result["official_gitattributes_crlf_to_git_lf"] == ["make.bat"]
    assert result["all_git_blobs_and_executable_modes_match"]


@pytest.mark.parametrize("fault", ["modified", "extra", "missing", "traversal", "mode"])
def test_changed_source_or_archive_shape_is_rejected(inputs, fault):
    files, archive, tree, commit = inputs
    members = dict(files)
    if fault == "modified":
        members["source.go"] += b"malicious change\n"
    elif fault == "extra":
        members["extra.go"] = b"package extra\n"
    elif fault == "missing":
        del members["source.go"]
    elif fault == "traversal":
        members["../outside"] = b"escape"
    with pytest.raises(ValueError):
        verifier.verify(archive(members, executable=fault == "mode"), tree, commit)


def test_incomplete_or_wrong_tree_is_rejected(inputs):
    _, archive, tree, commit = inputs
    original = json.loads(tree.read_bytes())
    for change in ({"truncated": True}, {"sha": "c" * 40}):
        document = original | change
        tree.write_text(json.dumps(document))
        with pytest.raises(ValueError, match="complete tree"):
            verifier.verify(archive(), tree, commit)


def test_unverified_commit_is_rejected(inputs):
    _, archive, tree, commit = inputs
    document = json.loads(commit.read_bytes())
    document["verification"]["verified"] = False
    commit.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="verified commit signature"):
        verifier.verify(archive(), tree, commit)
