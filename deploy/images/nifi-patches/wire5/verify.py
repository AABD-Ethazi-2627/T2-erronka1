"""Build/verify the explicit Wire 5 reader fork; does not modify a NiFi image."""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE_SHA256 = "7be3ac3d239e532c62becb6195602f0770d7b8de11d8793b9fc01702dea2ecd8"
ARTIFACTS = {
    "wire-runtime-jvm-5.2.0.jar": "c247dbd0dc4f42546090cf203a928400bab5c561746b3ffa2fd3270502d7c5f1",
    "wire-schema-jvm-5.2.0.jar": "dade32aba414c7695c90022f028705c67f65b88d26ab04f0168334838142b86e",
    "wire-runtime-jvm-5.2.0-sources.jar": SOURCE_SHA256,
}
CLASSES = {
    "com/squareup/wire/ProtoReader.class",
    "com/squareup/wire/ProtoReader$Companion.class",
    "com/squareup/wire/ProtoReader$WhenMappings.class",
    "com/squareup/wire/ByteArrayProtoReader32.class",
    "com/squareup/wire/ByteArrayProtoReader32$WhenMappings.class",
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def verify(work, mvn, java_home, maven_repo):
    pins = json.loads((HERE / "verification-pins.json").read_text())
    for name, expected in pins["inputs"].items():
        if sha((HERE / name).read_bytes()) != expected:
            raise ValueError("Reviewed candidate input changed: " + name)
    for name, expected in pins["maven_distribution"].items():
        if sha((mvn.parent.parent / name).read_bytes()) != expected:
            raise ValueError("Maven toolchain changed: " + name)
    for name, expected in pins["jdk"].items():
        if sha((java_home / name).read_bytes()) != expected:
            raise ValueError("JDK toolchain changed: " + name)
    work.mkdir(parents=True, exist_ok=False)
    if shutil.disk_usage(work).free < 2 * 1024**3:
        raise RuntimeError("Keep at least 2 GiB disk free")
    env = {
        **os.environ,
        "JAVA_HOME": str(java_home),
        "MAVEN_OPTS": "-Xmx512m -XX:ActiveProcessorCount=1",
    }

    def run(name, command, *, expected=0):
        result = subprocess.run(
            list(map(str, command)),
            check=False,
            env=env,
            capture_output=True,
            timeout=180,
        )
        (work / (name + ".log")).write_bytes(result.stdout + result.stderr)
        if result.returncode != expected:
            raise RuntimeError(f"{name} exit {result.returncode}; inspect retained log")
        return result.stdout

    artifacts = work / "artifacts"
    artifacts.mkdir()
    for name, expected in ARTIFACTS.items():
        artifact = (
            "wire-schema-jvm" if name.startswith("wire-schema") else "wire-runtime-jvm"
        )
        url = f"https://repo.maven.apache.org/maven2/com/squareup/wire/{artifact}/5.2.0/{name}"
        with urllib.request.urlopen(url, timeout=30) as response:
            raw = response.read()
        if sha(raw) != expected:
            raise ValueError("Official artifact checksum mismatch: " + name)
        (artifacts / name).write_bytes(raw)
    build = work / "build"
    (build / "src").mkdir(parents=True)
    shutil.copyfile(HERE / "pom.xml", build / "pom.xml")
    with zipfile.ZipFile(artifacts / "wire-runtime-jvm-5.2.0-sources.jar") as source:
        for name in ("ProtoReader.kt", "ByteArrayProtoReader32.kt"):
            (build / "src" / name).write_bytes(
                source.read("commonMain/com/squareup/wire/" + name)
            )
    run(
        "apply-patch",
        [
            "patch",
            "--batch",
            "--fuzz=0",
            "-p1",
            "-d",
            build / "src",
            "-i",
            HERE / "readers.patch",
        ],
    )
    run(
        "compile",
        [
            mvn,
            "-T",
            "1",
            "--batch-mode",
            "--no-transfer-progress",
            f"-Dmaven.repo.local={maven_repo}",
            "-f",
            build / "pom.xml",
            "compile",
        ],
    )
    generated = build / "target/classes"
    compiler = (
        maven_repo
        / "org/jetbrains/kotlin/kotlin-compiler/2.0.21/kotlin-compiler-2.0.21.jar"
    )
    if sha(compiler.read_bytes()) != pins["kotlin_compiler_sha256"]:
        raise ValueError("Kotlin compiler changed")
    changes = {
        str(p.relative_to(generated)): p.read_bytes()
        for p in generated.rglob("*.class")
    }
    if set(changes) != CLASSES:
        raise ValueError("Unexpected compiler class set")
    original = artifacts / "wire-runtime-jvm-5.2.0.jar"
    patched = artifacts / "wire-runtime-jvm-5.2.0-cncguard.1.jar"
    provenance = {
        "upstream_version": "5.2.0",
        "patch_version": "5.2.0+cncguard.1",
        "source_sha256": SOURCE_SHA256,
        "patch_sha256": sha((HERE / "readers.patch").read_bytes()),
        "rebuilt_classes": sorted(changes),
        "scope": "reader bounds candidate; explicit fork Maven identity; scanner visibility must be verified separately",
    }
    with zipfile.ZipFile(original) as old, zipfile.ZipFile(patched, "w") as new:
        if any(n.upper().endswith((".SF", ".RSA", ".DSA")) for n in old.namelist()):
            raise ValueError("Refuse invalidating signed artifact")
        for info in old.infolist():
            new.writestr(info, changes.get(info.filename, old.read(info.filename)))
        new.writestr(
            zipfile.ZipInfo("META-INF/cncguard-reader-backport.json"),
            json.dumps(provenance, sort_keys=True),
        )
        new.writestr(
            zipfile.ZipInfo(
                "META-INF/maven/com.squareup.wire/wire-runtime-jvm/pom.properties"
            ),
            "groupId=com.squareup.wire\nartifactId=wire-runtime-jvm\nversion=5.2.0+cncguard.1\n",
        )
    for name in sorted(changes):
        class_name = name[:-6].replace("/", ".")
        command = [java_home / "bin/javap", "-public", "-s", class_name]
        before = run(
            "abi-original-" + Path(name).stem,
            [command[0], "-classpath", original, *command[1:]],
        )
        after = run(
            "abi-patched-" + Path(name).stem,
            [command[0], "-classpath", patched, *command[1:]],
        )
        if before != after:
            raise ValueError("Public JVM ABI changed: " + class_name)
    with zipfile.ZipFile(original) as old, zipfile.ZipFile(patched) as new:
        untouched = [name for name in old.namelist() if name not in changes]
        if any(old.read(name) != new.read(name) for name in untouched):
            raise ValueError("Untouched upstream entries changed")
    deps = sorted((build / "deps").glob("*.jar"))
    if {p.name: sha(p.read_bytes()) for p in deps} != pins["dependencies"]:
        raise ValueError("Resolved verification dependencies changed")
    if sha(patched.read_bytes()) != pins["candidate_sha256"]:
        raise ValueError("Candidate bytes changed; independent review required")
    if (
        sha((build / "deps/wire-runtime-jvm-5.2.0.jar").read_bytes())
        != ARTIFACTS[original.name]
    ):
        raise ValueError("Maven resolved another upstream runtime")
    test_classes = work / "test-classes"
    classpath = os.pathsep.join(map(str, deps))
    run(
        "javac",
        [
            java_home / "bin/javac",
            "-cp",
            classpath,
            "-d",
            test_classes,
            HERE / "Wire5ReaderRegression.java",
        ],
    )
    baseline_cp = os.pathsep.join([str(test_classes), classpath])
    command = [java_home / "bin/java", "-Xmx256m", "-XX:ActiveProcessorCount=1", "-cp"]
    baseline = run(
        "regression-original",
        [*command, baseline_cp, "Wire5ReaderRegression"],
        expected=1,
    )
    result = run(
        "regression-patched",
        [*command, str(patched) + os.pathsep + baseline_cp, "Wire5ReaderRegression"],
    )
    for marker in (
        b"FAIL stream/negative-length-in-skipped-group",
        b"FAIL array/positive-length-overflow",
        b"FAIL array/negative-128-advisory",
        b"FAIL stream/nested-tag-must-not-read-parent",
        b"FAIL stream/untrusted-length-cannot-drive-preallocation",
        b"PASS schema5/actual-runtime-message-adapter-roundtrip",
    ):
        if marker not in baseline:
            raise ValueError("Original vulnerable controls did not reproduce")
    patched_counts = re.search(rb"RESULT passed=(\d+) failed=(\d+)", result)
    baseline_counts = re.search(rb"RESULT passed=(\d+) failed=(\d+)", baseline)
    if (
        not patched_counts
        or int(patched_counts[1]) != 44
        or int(patched_counts[2]) != 0
    ):
        raise ValueError("Patched regression incomplete")
    if not baseline_counts or (int(baseline_counts[1]), int(baseline_counts[2])) != (
        35,
        9,
    ):
        raise ValueError("Original negative controls changed")
    if any(
        b"FAIL " in line and (b"valid-" in line or b"schema5/" in line)
        for line in baseline.splitlines()
    ):
        raise ValueError("A valid-input control failed on the original")
    report = {
        **provenance,
        "public_abi_unchanged": True,
        "unchanged_upstream_entries": len(untouched),
        "patched_sha256": sha(patched.read_bytes()),
        "regressions": int(patched_counts[1]),
        "original_failures": int(baseline_counts[2]),
        "dependency_sha256": {p.name: sha(p.read_bytes()) for p in deps},
        "limits": "No NiFi execution/image scan; explicit fork identity is not proof of scanner coverage; needs independent patch review",
    }
    (work / "verification.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--mvn", type=Path, required=True)
    parser.add_argument("--java-home", type=Path, required=True)
    parser.add_argument("--maven-repo", type=Path, required=True)
    args = parser.parse_args()
    verify(
        args.work_dir.resolve(),
        args.mvn.resolve(),
        args.java_home.resolve(),
        args.maven_repo.resolve(),
    )
