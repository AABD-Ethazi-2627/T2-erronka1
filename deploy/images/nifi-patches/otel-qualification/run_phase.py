"""Reserved VM-only phases against actual pinned image; proof output only."""

import argparse
import difflib
import json
import os
import resource
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import qualify as q

p = argparse.ArgumentParser()
p.add_argument("phase", choices=["extract", "static", "runtime"])
p.add_argument("--proof", type=Path, required=True)
a = p.parse_args()
b = a.proof
known = json.loads((q.HERE / "known-inputs.json").read_text())
public = json.loads((q.HERE / "public-pins.json").read_text())
CACHE = Path(os.environ.get("CNC_OTEL_CACHE", "/cache"))
base_sources = {str(p): q.sha(p.read_bytes()) for p in q.HERE.iterdir() if p.is_file()}
for pin in public["files"]:
    q.checked(CACHE / pin["file"], pin["sha256"])
for name, pin in known["existing_fixed_artifacts"].items():
    q.checked(CACHE / name, pin["sha256"])
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
# JVM memory is bounded by cgroup+heap/metaspace/direct/code caches, not a false
# claim that Java can initialize inside a 512MiB virtual address space.
if a.phase != "runtime":
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2,) * 2)
start = time.monotonic()
report = {
    "phase": a.phase,
    "replacement": None,
    "runtime_approved": False,
    "image_id_expected": known["image_id"],
    "sources_before": base_sources,
}
commands = []


def checked_run(cmd, label, expected=0, timeout=35):
    cmd = list(map(str, cmd))
    with (
        (b / (label + ".stdout")).open("w") as so,
        (b / (label + ".stderr")).open("w") as se,
    ):
        r = subprocess.run(
            cmd,
            check=False,
            stdout=so,
            stderr=se,
            timeout=timeout,
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
    commands.append({"label": label, "command": cmd, "returncode": r.returncode})
    if expected is not None and (
        (expected == 0 and r.returncode != 0) or (expected != 0 and r.returncode == 0)
    ):
        raise ValueError(label + " unexpected exit " + str(r.returncode))
    return (b / (label + ".stdout")).read_text(), (b / (label + ".stderr")).read_text()


try:
    if a.phase == "extract":
        out = b / "expanded-old"
        out.mkdir(exist_ok=False)
        records = []
        manifests = {}
        for row in known["nar_chain"]:
            path = Path("/") / row["path"]
            q.verify_file(path, row["sha256"])
            with zipfile.ZipFile(path) as z:
                actual = q.manifest(z.read("META-INF/MANIFEST.MF"))
            if {k: v for k, v in actual.items() if k.startswith("Nar-")} != row[
                "manifest"
            ]:
                raise ValueError("actual NAR manifest drift")
            manifests[row["id"]] = row["manifest"]
            wanted = {x["entry"]: x["sha256"] for x in row["direct_jars"]}
            seen = set()
            destination = out / row["id"] / "NAR-INF/bundled-dependencies"
            destination.mkdir(parents=True)
            for entry, blob in q.jar_entries(path):
                if entry not in wanted or q.sha(blob) != wanted[entry]:
                    raise ValueError("actual bundled jar drift " + entry)
                seen.add(entry)
                name = Path(entry).name
                (destination / name).write_bytes(blob)
                records.append(
                    {"nar": row["id"], "entry": entry, "sha256": q.sha(blob)}
                )
            if seen != set(wanted):
                raise ValueError("incomplete actual NAR closure")
            q.verify_file(path, row["sha256"])
        order = q.parent_chain(manifests, "nifi-gcp-nar")
        if order != [x["id"] for x in known["nar_chain"]]:
            raise ValueError("actual NAR ancestry drift")
        top = b / "top"
        top.mkdir()
        for row in known["launcher_jars"]:
            data = q.checked(Path("/") / row["path"], row["sha256"])
            (top / Path(row["path"]).name).write_bytes(data)
        (b / "parents.tsv").write_text(
            "".join(
                x["id"] + "\t" + x["manifest"].get("Nar-Dependency-Id", "") + "\n"
                for x in known["nar_chain"]
            )
        )
        q.save(b / "expanded-inputs.json", records)
        report.update(
            status="actual-image-inputs-extracted",
            nar_order=order,
            actual_jars=len(records),
            launcher_jars=len(known["launcher_jars"]),
        )
    elif a.phase == "static":
        providers = {
            f"opentelemetry-{x}-1.62.0.jar" for x in ("api", "context", "common")
        }
        models = {}
        references = []
        consumers = []
        nifi = []
        jar_count = 0
        class_count = 0
        # Parent-first, matching ordinary installed URLClassLoader delegation.
        for row in reversed(known["nar_chain"]):
            for jar in sorted(
                (b / "expanded-old" / row["id"] / "NAR-INF/bundled-dependencies").glob(
                    "*.jar"
                )
            ):
                jar_count += 1
                for path, model in q.classes(jar):
                    class_count += 1
                    if model["name"].startswith("io/opentelemetry/"):
                        models.setdefault(model["name"], model)
                    if jar.name not in providers and model["references"]:
                        label = row["id"] + "!" + jar.name + "!" + path
                        consumers.append(
                            {
                                "class": model["name"],
                                "jar": jar.name,
                                "nar": row["id"],
                                "reference_count": len(model["references"]),
                            }
                        )
                        references.extend(
                            (label, tuple(ref)) for ref in model["references"]
                        )
                    if (
                        row["id"] == "nifi-gcp-nar"
                        and model["name"].startswith("org/apache/nifi/processors/gcp/")
                        and "$" not in model["name"]
                        and model["flags"] & 1
                        and not model["flags"] & 0x400
                    ):
                        nifi.append(model["name"].replace("/", "."))
        if jar_count != 189 or not references or not consumers:
            raise ValueError("vacuous classloader consumer inventory")
        # Published API closure is independent of SDK's existing declarations.
        namespace = {"m": "http://maven.apache.org/POM/4.0.0"}
        pom_reports = []
        for pin in public["files"]:
            if not pin["file"].endswith(".pom"):
                continue
            model = ET.fromstring((CACHE / pin["file"]).read_bytes())
            dependencies = [
                {
                    key: d.findtext("m:" + key, None, namespace)
                    for key in ("groupId", "artifactId", "version", "scope", "optional")
                }
                for d in model.findall("m:dependencies/m:dependency", namespace)
            ]
            pom_reports.append(
                {
                    "file": pin["file"],
                    "sha256": pin["sha256"],
                    "dependencies": dependencies,
                }
            )
        declarations = {
            pin["coordinate"]: next(
                report["dependencies"]
                for report in pom_reports
                if report["file"] == pin["file"]
            )
            for pin in public["files"]
            if pin["file"].endswith(".pom")
        }
        declared = q.required_closure(
            declarations, "io.opentelemetry:opentelemetry-api:1.67.0"
        )
        expected = [
            "io.opentelemetry:opentelemetry-api:1.67.0",
            "io.opentelemetry:opentelemetry-common:1.67.0",
            "io.opentelemetry:opentelemetry-context:1.67.0",
        ]
        if declared != expected:
            raise ValueError(
                "unexpected published transitive API closure; review needed"
            )
        q.save(b / "published-dependency-declarations.json", pom_reports)
        source_name = (
            "io/opentelemetry/api/trace/propagation/W3CTraceContextPropagator.java"
        )
        with zipfile.ZipFile(CACHE / "opentelemetry-api-1.62.0-sources.jar") as z:
            old_source = z.read(source_name).decode()
        with zipfile.ZipFile(CACHE / "opentelemetry-api-1.67.0-sources.jar") as z:
            new_source = z.read(source_name).decode()
        (b / "tracestate-source-diff.patch").write_text(
            "".join(
                difflib.unified_diff(
                    old_source.splitlines(True),
                    new_source.splitlines(True),
                    fromfile="official1.62.0",
                    tofile="official1.67.0",
                )
            )
        )
        results = {}
        for variant, artifacts in [
            ("api-context-common", ("api", "context", "common")),
            ("api-context", ("api", "context")),
        ]:
            candidate = dict(models)
            removed = []
            added_abstract = []
            for artifact in artifacts:
                old = (
                    b
                    / "expanded-old/nifi-gcp-nar/NAR-INF/bundled-dependencies"
                    / f"opentelemetry-{artifact}-1.62.0.jar"
                )
                before = {m["name"]: m for _, m in q.classes(old)}
                after = {
                    m["name"]: m
                    for _, m in q.classes(
                        CACHE / f"opentelemetry-{artifact}-1.67.0.jar"
                    )
                }
                for name, model in before.items():
                    candidate.pop(name, None)
                    if name not in after:
                        removed.append({"class": name})
                    else:
                        for key, flags in model["members"].items():
                            if flags & 5 and key not in after[name]["members"]:
                                removed.append({"class": name, "member": list(key)})
                        for key, flags in after[name]["members"].items():
                            if flags & 0x400 and key not in model["members"]:
                                added_abstract.append(
                                    {"class": name, "member": list(key)}
                                )
                candidate.update(after)
            broken = q.newly_broken(models, candidate, references)
            mutant = dict(candidate)
            mutant.pop("io/opentelemetry/api/OpenTelemetry", None)
            negative = q.newly_broken(models, mutant, references)
            if not negative:
                raise ValueError(
                    "missing API class negative control did not discriminate"
                )
            results[variant] = {
                "newly_broken_direct_or_otel_inherited_references": broken,
                "declared_public_protected_removals": removed,
                "new_abstract_members": added_abstract,
                "negative_missing_api_class_new_failures": len(negative),
            }
        q.save(b / "consumer-references.json", consumers)
        q.save(b / "nifi-consumer-candidates.json", sorted(set(nifi)))
        report.update(
            status="static-analysis-completed",
            effective_jar_count=jar_count,
            classes_examined=class_count,
            consumer_classes=len(consumers),
            references_examined=len(references),
            variants=results,
            published_api_167_required_coordinates=[
                "io.opentelemetry:opentelemetry-api:1.67.0",
                "io.opentelemetry:opentelemetry-context:1.67.0",
                "io.opentelemetry:opentelemetry-common:1.67.0",
            ],
            common_167_is_transitively_required=True,
            limits=[
                "direct references and inheritance within io.opentelemetry class models only",
                "not JVM access/invocation/method-handle/default-method/reflection verification",
                "external subclasses and complete resource/SPI/linkage remain unproven",
                "metadata parent order is checked by isolated actual NarClassLoader controls separately",
            ],
        )
    else:
        runtime = b / "runtime"
        runtime.mkdir(exist_ok=False)
        opts = [
            "-Xmx256m",
            "-XX:MaxMetaspaceSize=96m",
            "-XX:MaxDirectMemorySize=32m",
            "-XX:ReservedCodeCacheSize=32m",
            "-XX:CompressedClassSpaceSize=32m",
            "-XX:ActiveProcessorCount=1",
            "-XX:-CreateCoredumpOnCrash",
        ]
        java = Path(shutil.which("java")).resolve()
        javac = Path("/jdk/bin/javac")
        checked_run([java, *opts, "-version"], "actual-image-java-version")
        checked_run([javac, *["-J" + x for x in opts], "-version"], "compiler-version")
        topcp = os.pathsep.join(str(p) for p in sorted((b / "top").glob("*.jar")))
        launcher = runtime / "launcher"
        launcher.mkdir()
        checked_run(
            [
                javac,
                *["-J" + x for x in opts],
                "-cp",
                topcp,
                "-d",
                launcher,
                q.HERE / "NarOtelProbe.java",
            ],
            "compile-launcher",
        )
        compilecp = os.pathsep.join(
            str(p)
            for row in reversed(known["nar_chain"])
            for p in sorted(
                (b / "expanded-old" / row["id"] / "NAR-INF/bundled-dependencies").glob(
                    "*.jar"
                )
            )
        )
        exercise = runtime / "exercise"
        exercise.mkdir()
        checked_run(
            [
                javac,
                *["-J" + x for x in opts],
                "-cp",
                compilecp,
                "-d",
                exercise,
                q.HERE / "OtelExercise.java",
            ],
            "compile-exercise",
        )
        original = b / "expanded-old"
        variants = [
            ("old", ()),
            ("api-context-common", ("api", "context", "common")),
            ("api-context", ("api", "context")),
        ]
        exercised = []
        candidates = json.loads((b / "nifi-consumer-candidates.json").read_text())
        # Concrete NiFi classes are loaded without initialization; SDK operations
        # execute separately. Loading is not processor scheduling acceptance.
        selected = candidates[:3]
        for variant, artifacts in variants:
            dest = runtime / variant
            shutil.copytree(original, dest, copy_function=os.link)
            leaf = dest / "nifi-gcp-nar/NAR-INF/bundled-dependencies"
            for artifact in artifacts:
                (leaf / f"opentelemetry-{artifact}-1.62.0.jar").unlink()
                shutil.copyfile(
                    CACHE / f"opentelemetry-{artifact}-1.67.0.jar",
                    leaf / f"opentelemetry-{artifact}-1.67.0.jar",
                )
            for f in exercise.glob("*.class"):
                shutil.copyfile(f, dest / "nifi-gcp-nar" / f.name)
            args = []
            for artifact in ("api", "context", "common"):
                version = "1.67.0" if artifact in artifacts else "1.62.0"
                name = f"opentelemetry-{artifact}-{version}.jar"
                args += [name, q.sha((leaf / name).read_bytes())]
            cmd = [
                java,
                *opts,
                "-cp",
                str(launcher) + os.pathsep + topcp,
                "NarOtelProbe",
                dest,
                b / "parents.tsv",
                *args,
                "io.grpc.opentelemetry.GrpcOpenTelemetry",
                *selected,
            ]
            checked_run(
                cmd, "nar-" + variant, expected=None if variant == "api-context" else 0
            )
            exercised.append(
                {
                    "variant": variant,
                    "fixed_artifacts": list(artifacts),
                    "published_closure_conformant": variant != "api-context",
                    "observed_returncode": commands[-1]["returncode"],
                    "loaded_nifi_consumers": selected,
                }
            )
        negative = runtime / "negative-missing-api"
        shutil.copytree(runtime / "api-context-common", negative, copy_function=os.link)
        (
            negative
            / "nifi-gcp-nar/NAR-INF/bundled-dependencies/opentelemetry-api-1.67.0.jar"
        ).unlink()
        cmd = [
            java,
            *opts,
            "-cp",
            str(launcher) + os.pathsep + topcp,
            "NarOtelProbe",
            negative,
            b / "parents.tsv",
            "opentelemetry-api-1.67.0.jar",
            known["existing_fixed_artifacts"]["opentelemetry-api-1.67.0.jar"]["sha256"],
            "opentelemetry-context-1.67.0.jar",
            known["existing_fixed_artifacts"]["opentelemetry-context-1.67.0.jar"][
                "sha256"
            ],
            "opentelemetry-common-1.67.0.jar",
            known["existing_fixed_artifacts"]["opentelemetry-common-1.67.0.jar"][
                "sha256"
            ],
        ]
        _, err = checked_run(cmd, "negative-missing-api", expected=1)
        if "ClassNotFoundException: io.opentelemetry.api.OpenTelemetry" not in err:
            raise ValueError("negative classloader failed for unrelated reason")
        report.update(
            status="actual-NarClassLoader-component-controls-passed",
            variants=exercised,
            negative_control="missing_api_class_rejected_without_flat_fallback",
            limits=[
                "not processor scheduling/NiFi server/GCP service compatibility",
                "no exporter/service autoconfigure/resource-provider traversal",
                "not a complexity/adversarial reproduction of tracestate advisory",
                "both variants are qualification only; no replacement approved",
            ],
        )
    report["commands"] = commands
    report["elapsed_seconds"] = round(time.monotonic() - start, 3)
    after = {str(p): q.sha(p.read_bytes()) for p in q.HERE.iterdir() if p.is_file()}
    if after != base_sources:
        raise ValueError("qualification source drift")
    report["sources_after"] = after
    for row in known["nar_chain"]:
        q.verify_file(Path("/") / row["path"], row["sha256"])
    report["actual_original_NARs_unchanged"] = True
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
except BaseException as e:
    report.update(
        status="failed-qualification-phase",
        error=type(e).__name__ + ": " + str(e),
        commands=commands,
        elapsed_seconds=round(time.monotonic() - start, 3),
    )
    q.save(b / (a.phase + "-result.json"), report)
    raise
