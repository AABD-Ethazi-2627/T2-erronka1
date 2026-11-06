"""Separate SDK-family qualification; no overlay output or automatic promotion."""

import argparse
import importlib.util
import json
import os
import re
import resource
import shutil
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "_cnc_otel_qualifier", HERE / "qualify.py"
)
q = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(q)


def select_observed(known, artifacts):
    result = {}
    for artifact in artifacts:
        old = "opentelemetry-" + artifact + "-1.62.0.jar"
        if old not in known["old_gcp_otel"]:
            raise ValueError("unobserved OTel family artifact: " + artifact)
        result[old] = "opentelemetry-" + artifact + "-1.67.0.jar"
    return result


def collect(known, original, cache, replacements):
    models = {}
    references = []
    consumers = []
    count = 0
    api = {
        "opentelemetry-" + a + "-" + v + ".jar"
        for a in ("api", "context", "common")
        for v in ("1.62.0", "1.67.0")
    }
    for row in reversed(known["nar_chain"]):
        for old in sorted(
            (original / row["id"] / "NAR-INF/bundled-dependencies").glob("*.jar")
        ):
            file = (
                cache / replacements[old.name]
                if row["id"] == "nifi-gcp-nar" and old.name in replacements
                else old
            )
            for name, model in q.classes(file):
                count += 1
                if model["name"].startswith("io/opentelemetry/"):
                    models.setdefault(model["name"], model)
                if file.name not in api and model["references"]:
                    label = row["id"] + "!" + file.name + "!" + name
                    references.extend(
                        (label, tuple(ref)) for ref in model["references"]
                    )
                    consumers.append(
                        {
                            "class": model["name"],
                            "jar": file.name,
                            "references": len(model["references"]),
                        }
                    )
    if not references:
        raise ValueError("empty applicable consumer set")
    return models, references, consumers, count


def main():
    p = argparse.ArgumentParser()
    p.add_argument("phase", choices=["oracle", "static", "runtime"])
    p.add_argument("--proof", type=Path, required=True)
    a = p.parse_args()
    b = a.proof
    cache = Path("/cache")
    baseline = Path("/baseline")
    known = json.loads((HERE / "known-inputs.json").read_text())
    pins = json.loads((HERE / "aligned-pins.json").read_text())
    original = baseline / "attempt-03/expanded-old"
    replacements = select_observed(known, pins["artifacts"])
    if len(replacements) != 9:
        raise ValueError("incomplete observed family")
    for pin in pins["files"]:
        q.checked(cache / pin["file"], pin["sha256"])
    source = {str(f): q.sha(f.read_bytes()) for f in HERE.iterdir() if f.is_file()}
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    # Oracle also launches a bounded JVM; its virtual reservation is not RSS.
    if a.phase == "static":
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2,) * 2)
    report = {
        "phase": a.phase,
        "replacement": None,
        "runtime_approved": False,
        "sources_before": source,
        "commands": [],
    }
    start = time.monotonic()

    def run(cmd, label, expected=0):
        with (
            (b / (label + ".stdout")).open("w") as so,
            (b / (label + ".stderr")).open("w") as se,
        ):
            r = subprocess.run(
                list(map(str, cmd)),
                stdout=so,
                stderr=se,
                timeout=40,
                check=False,
                env={
                    k: v
                    for k, v in os.environ.items()
                    if k
                    not in (
                        "JAVA_TOOL_OPTIONS",
                        "JDK_JAVA_OPTIONS",
                        "_JAVA_OPTIONS",
                        "MAVEN_OPTS",
                    )
                },
            )
        report["commands"].append(
            {"label": label, "command": list(map(str, cmd)), "returncode": r.returncode}
        )
        q.save(b / (a.phase + "-result.json"), report)
        if (expected == 0 and r.returncode) or (expected != 0 and r.returncode == 0):
            raise ValueError(label + " unexpected exit")
        return (b / (label + ".stdout")).read_text(), (
            b / (label + ".stderr")
        ).read_text()

    options = [
        "-Xmx256m",
        "-XX:MaxMetaspaceSize=96m",
        "-XX:MaxDirectMemorySize=32m",
        "-XX:ReservedCodeCacheSize=32m",
        "-XX:CompressedClassSpaceSize=32m",
        "-XX:ActiveProcessorCount=1",
        "-XX:-CreateCoredumpOnCrash",
    ]
    java = Path(shutil.which("java")).resolve()
    try:
        if a.phase == "oracle":
            repo = b / "maven-repository"
            repo.mkdir(exist_ok=False)
            models = {}
            byname = {x["file"]: x for x in pins["files"]}
            for pin in pins["files"]:
                if not pin["file"].endswith(".pom"):
                    continue
                models[pin["coordinate"]] = pin["dependencies"]
                g, artifact, version = pin["coordinate"].split(":")
                directory = repo / g.replace(".", "/") / artifact / version
                directory.mkdir(parents=True)
                for ext in ("pom", "jar"):
                    name = artifact + "-" + version + "." + ext
                    q.checked(cache / name, byname[name]["sha256"])
                    shutil.copyfile(cache / name, directory / name)
            roots = [
                "io.opentelemetry:opentelemetry-sdk:1.67.0",
                "io.opentelemetry:opentelemetry-sdk-extension-autoconfigure-spi:1.67.0",
            ]
            expected = {r: q.required_closure(models, r) for r in roots}
            tools = json.loads((HERE / "maven-oracle-inputs.json").read_text())
            for name, expected_hash in tools["files"].items():
                q.verify_file(Path("/maven") / name, expected_hash)
            report["maven_tool_input_sha256"] = tools["files"]
            classfile = Path("/maven/maven-classes/MvnClosure.class")
            q.verify_file(
                classfile,
                "3fb91664291da3b9a4dbb811c22bd0d4199cc3a7b535f2649c21e89b75610bb5",
            )
            cp = "/maven/maven-classes:/maven/apache-maven-3.9.11/lib/*:/maven/apache-maven-3.9.11/boot/*"
            arguments = [value for root in roots for value in (repo, root)]
            out, _ = run(
                [java, *options, "-cp", cp, "MvnClosure", *arguments],
                "real-maven-offline",
            )
            lines = [line for line in out.splitlines() if line.startswith("RESULT")]
            if len(lines) != 2:
                raise ValueError("Maven coverage missing")
            actual = {}
            for root, line in zip(roots, lines):
                match = re.search(r"\[(.*)\]$", line)
                if not match or "FAIL" in line:
                    raise ValueError("Maven resolver failure")
                values = []
                for entry in match[1].split(", "):
                    group, artifact, ext, classifier, version, scope, optional = (
                        entry.split(":")
                    )
                    if scope in ("compile", "runtime") and optional != "true":
                        if ext != "jar" or classifier:
                            raise ValueError(
                                "unsupported required Maven type/classifier"
                            )
                        values.append(group + ":" + artifact + ":" + version)
                actual[root] = sorted(set(values))
            if actual != expected:
                raise ValueError("published closure differs from real Maven")
            if len(set().union(*map(set, actual.values()))) != 9:
                raise ValueError("unexpected additional family closure")
            report.update(
                status="published-closure-equals-real-Maven",
                expected=expected,
                actual=actual,
                union_required_coordinates=sorted(
                    set().union(*map(set, actual.values()))
                ),
            )
        elif a.phase == "static":
            old, oldrefs, oldconsumers, oldcount = collect(known, original, cache, {})
            narrow = {
                k: v
                for k, v in replacements.items()
                if any(
                    k == "opentelemetry-" + x + "-1.62.0.jar"
                    for x in ("api", "context", "common")
                )
            }
            narrowmodels, _, _, _ = collect(known, original, cache, narrow)
            narrow_fail = q.newly_broken(old, narrowmodels, oldrefs)
            if len(narrow_fail) != 10:
                raise ValueError("sealed ten-reference negative control changed")
            aligned, refs, consumers, count = collect(
                known, original, cache, replacements
            )
            failures = q.newly_broken(old, aligned, refs)
            mutant = dict(aligned)
            mutant.pop("io/opentelemetry/api/OpenTelemetry", None)
            control = q.newly_broken(old, mutant, refs)
            if not control:
                raise ValueError("missing API mutation did not discriminate")
            unresolved = [
                {"consumer": c, "reference": list(r)}
                for c, r in refs
                if q.resolve(aligned, r[0], (r[3], r[1], r[2])) is None
            ]
            q.save(b / "aligned-consumers.json", consumers)
            report.update(
                status="aligned-symbolic-analysis-completed",
                old_class_entries=oldcount,
                new_class_entries=count,
                old_consumer_entries=len(oldconsumers),
                aligned_consumer_entries=len(consumers),
                old_references=len(oldrefs),
                aligned_references=len(refs),
                narrow_negative_control=narrow_fail,
                newly_broken_references=failures,
                missing_api_negative_new_failures=len(control),
                unresolved_current_references=unresolved,
                limits=[
                    "direct CP and inheritance within OTel model only; no full JVM access/reflection/default-method proof",
                    "descriptor-only references and JDK-inherited symbols incompletely modeled",
                    "physical duplicate/shadowed entries counted; actual loader tested separately",
                ],
            )
        else:
            out = b / "runtime"
            out.mkdir(exist_ok=False)
            top = baseline / "attempt-03/top"
            cp = os.pathsep.join(map(str, sorted(top.glob("*.jar"))))
            classes = out / "classes"
            classes.mkdir()
            javac = Path("/jdk/bin/javac")
            run([javac, *["-J" + o for o in options], "-version"], "compiler-version")
            run([java, *options, "-version"], "actual-image-java-version")
            run(
                [
                    javac,
                    *["-J" + o for o in options],
                    "-cp",
                    cp,
                    "-d",
                    classes,
                    HERE / "NarOtelProbe.java",
                    HERE / "AlignedNarProbe.java",
                ],
                "compile-real-loader-launcher",
            )
            compilecp = os.pathsep.join(
                str(path)
                for row in reversed(known["nar_chain"])
                for path in sorted(
                    (original / row["id"] / "NAR-INF/bundled-dependencies").glob(
                        "*.jar"
                    )
                )
            )
            exercise = out / "exercise"
            exercise.mkdir()
            run(
                [
                    javac,
                    *["-J" + o for o in options],
                    "-cp",
                    compilecp,
                    "-d",
                    exercise,
                    HERE / "OtelExercise.java",
                    HERE / "ConfigPropertiesProbe.java",
                ],
                "compile-actual-consumer-exercises",
            )
            # Copy once across read-only mount boundary; hardlink only private descendants.
            first = out / "old"
            shutil.copytree(original, first)
            variants = [
                ("old", {}),
                (
                    "narrow",
                    {
                        k: v
                        for k, v in replacements.items()
                        if k
                        in {
                            "opentelemetry-" + x + "-1.62.0.jar"
                            for x in ("api", "context", "common")
                        }
                    },
                ),
                ("aligned", replacements),
            ]
            filenames = [
                "api",
                "context",
                "common",
                "sdk",
                "sdk-common",
                "sdk-trace",
                "sdk-metrics",
                "sdk-logs",
                "sdk-extension-autoconfigure-spi",
            ]
            outcomes = []
            for name, mapping in variants:
                tree = first if name == "old" else out / name
                if name != "old":
                    shutil.copytree(first, tree, copy_function=os.link)
                leaf = tree / "nifi-gcp-nar/NAR-INF/bundled-dependencies"
                for oldname, newname in mapping.items():
                    (leaf / oldname).unlink()
                    shutil.copyfile(cache / newname, leaf / newname)
                for f in exercise.glob("*.class"):
                    shutil.copyfile(f, tree / "nifi-gcp-nar" / f.name)
                arguments = []
                for suffix in filenames:
                    oldname = "opentelemetry-" + suffix + "-1.62.0.jar"
                    file = mapping.get(oldname, oldname)
                    arguments.extend([file, q.sha((leaf / file).read_bytes())])
                consumers = json.loads(
                    (baseline / "attempt-03/nifi-consumer-candidates.json").read_text()
                )[:3]
                stdout, stderr = run(
                    [
                        java,
                        *options,
                        "-cp",
                        str(classes) + os.pathsep + cp,
                        "AlignedNarProbe",
                        tree,
                        baseline / "attempt-03/parents.tsv",
                        *arguments,
                        "io.grpc.opentelemetry.GrpcOpenTelemetry",
                        *consumers,
                    ],
                    "real-nar-" + name,
                    expected=1 if name == "narrow" else 0,
                )
                if (
                    name == "narrow"
                    and "NoClassDefFoundError: io/opentelemetry/api/internal/ConfigUtil"
                    not in stderr
                ):
                    raise ValueError("narrow variant failed for unrelated reason")
                outcomes.append(
                    {
                        "variant": name,
                        "returncode": report["commands"][-1]["returncode"],
                        "actual_loaded_consumer_names": consumers,
                        "configutil_consumer_passed": "actual-sdk-configutil-consumer=pass"
                        in stdout,
                    }
                )
            report.update(
                status="bounded-real-NarClassLoader-aligned-controls-passed",
                outcomes=outcomes,
                limits=[
                    "not NiFi scheduling/server, exporters, resource-provider traversal or GCP service acceptance",
                    "unrelated gRPC/alpha artifacts stay unchanged; selected classes loaded only",
                ],
            )
        report["sources_after"] = {
            str(f): q.sha(f.read_bytes()) for f in HERE.iterdir() if f.is_file()
        }
        if report["sources_after"] != source:
            raise ValueError("qualification source drift")
        for row in known["nar_chain"]:
            q.verify_file(Path("/") / row["path"], row["sha256"])
        report["original_image_NARs_unchanged"] = True
        report["elapsed_seconds"] = round(time.monotonic() - start, 3)
        q.save(b / (a.phase + "-result.json"), report)
        print(
            json.dumps(
                {
                    "phase": a.phase,
                    "status": report["status"],
                    "elapsed_seconds": report["elapsed_seconds"],
                }
            ),
            flush=True,
        )
    except BaseException as error:
        report.update(
            status="blocked-aligned-qualification-phase",
            error=type(error).__name__ + ": " + str(error),
            elapsed_seconds=round(time.monotonic() - start, 3),
        )
        q.save(b / (a.phase + "-result.json"), report)
        raise


if __name__ == "__main__":
    main()
