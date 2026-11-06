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
COVERAGE_SPEC = importlib.util.spec_from_file_location(
    "_otel_coverage", HERE / "coverage.py"
)
c = importlib.util.module_from_spec(COVERAGE_SPEC)
COVERAGE_SPEC.loader.exec_module(c)

EXTERNAL_CONSUMERS = [
    "io.grpc.opentelemetry.GrpcOpenTelemetry",
    "io.grpc.opentelemetry.OpenTelemetryMetricSink",
    "com.google.cloud.opentelemetry.metric.MetricTranslator",
    "com.google.cloud.opentelemetry.metric.InternalMetricExporter",
    "com.google.cloud.storage.OpenTelemetryBootstrappingUtils",
    "com.google.cloud.bigquery.storage.v1.TelemetryMetrics",
    "com.google.cloud.pubsub.v1.OpenTelemetryPubsubTracer",
    "com.google.api.gax.tracing.OpenTelemetryMetricsRecorder",
    "io.opentelemetry.contrib.gcp.resource.GCPResourceProvider",
]


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
    external = {}
    external_details = []
    all_references = []
    family = {
        "opentelemetry-" + a + "-" + v + ".jar"
        for a in (
            "api",
            "context",
            "common",
            "sdk",
            "sdk-common",
            "sdk-trace",
            "sdk-metrics",
            "sdk-logs",
            "sdk-extension-autoconfigure-spi",
        )
        for v in ("1.62.0", "1.67.0")
    }
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
                label = row["id"] + "!" + file.name + "!" + name
                all_references.extend(
                    (label, tuple(ref)) for ref in model["references"]
                )
                is_external = file.name not in family and not file.name.startswith(
                    "opentelemetry-semconv-"
                )
                if is_external and (model["references"] or model["descriptor_types"]):
                    external[model["name"]] = model
                    external_details.extend(
                        (label, tuple(ref)) for ref in model["reference_details"]
                    )
                if file.name not in api and model["references"]:
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
    return {
        "models": models,
        "references": references,
        "consumers": consumers,
        "class_entries": count,
        "external_models": external,
        "external_details": external_details,
        "all_references": all_references,
    }


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
    top = baseline / "attempt-03/top"
    input_verification = c.verify_expanded(known, original, top)
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
    report = q.preparation_report(
        phase=a.phase,
        sources_before=source,
        commands=[],
        verified_inputs=input_verification,
    )
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
            old_data = collect(known, original, cache, {})
            old, oldrefs = old_data["models"], old_data["references"]
            old_unresolved = c.classify_unresolved(old, oldrefs, "old", set())
            old_identities = {
                c.reference_identity(r["consumer"], r["reference"])
                for r in old_unresolved
            }
            c.require_closed(old_unresolved)
            narrow = {
                k: v
                for k, v in replacements.items()
                if k
                in {
                    "opentelemetry-" + x + "-1.62.0.jar"
                    for x in ("api", "context", "common")
                }
            }
            narrow_data = collect(known, original, cache, narrow)
            narrow_fail = q.newly_broken(old, narrow_data["models"], oldrefs)
            if len(narrow_fail) != 10:
                raise ValueError("sealed ten-reference negative control changed")
            aligned_data = collect(known, original, cache, replacements)
            aligned, refs = aligned_data["models"], aligned_data["references"]
            failures = q.newly_broken(old, aligned, refs)
            classified = c.classify_unresolved(aligned, refs, "aligned", old_identities)
            all_classified = c.classify_unresolved(
                aligned,
                aligned_data["all_references"],
                "aligned-all-family-including-api",
                old_identities,
            )
            c.require_closed(classified)
            c.require_closed(all_classified)
            if failures:
                raise ValueError("newly broken aligned symbolic references")
            reversed_data = collect(
                known,
                original,
                cache,
                {k: v for k, v in replacements.items() if k not in narrow},
            )
            reversed_unresolved = c.classify_unresolved(
                reversed_data["models"],
                reversed_data["references"],
                "sdk-new-api-old",
                old_identities,
            )
            reversed_unknown = [
                r for r in reversed_unresolved if r["category"] == "unknown"
            ]
            if len(reversed_unknown) != 8 or any(
                r["reference"][0] != "io/opentelemetry/common/impl/ConfigUtil"
                for r in reversed_unknown
            ):
                raise ValueError(
                    "reversed SDK/API negative control lost its eight ConfigUtil references"
                )
            try:
                c.require_closed(reversed_unresolved)
            except ValueError:
                pass
            else:
                raise ValueError("reversed SDK/API unknown references accepted")
            mutant = dict(aligned)
            mutant.pop("io/opentelemetry/api/OpenTelemetry", None)
            control = q.newly_broken(old, mutant, refs)
            if not control:
                raise ValueError("missing API mutation did not discriminate")
            abi = c.abi_delta(
                old,
                aligned,
                aligned_data["external_models"],
                aligned_data["external_details"],
            )
            if abi["external_impacts"]:
                raise ValueError("observed external ABI impact")
            actual_external_classes = {
                x.replace("/", ".") for x in aligned_data["external_models"]
            }
            if not set(EXTERNAL_CONSUMERS) <= actual_external_classes:
                raise ValueError(
                    "selected probe class is not an observed external OTel consumer"
                )
            q.save(b / "external-consumers-for-probe.json", EXTERNAL_CONSUMERS)
            q.save(b / "aligned-consumers.json", aligned_data["consumers"])
            # The first narrow proof compared the unchanged propagator. Preserve it;
            # here require the actual encoding source and shipped bytecode change.
            public = json.loads((HERE / "public-pins.json").read_text())["files"]
            old_source = baseline / "public-cache/opentelemetry-api-1.62.0-sources.jar"
            old_pin = next(x for x in public if x["file"] == old_source.name)
            q.verify_file(old_source, old_pin["sha256"])
            encoding = "io/opentelemetry/api/trace/propagation/internal/W3CTraceContextEncoding.java"
            patch = c.source_change(
                old_source, cache / "opentelemetry-api-1.67.0-sources.jar", encoding
            )
            (b / "tracestate-encoding-source-diff.patch").write_text(patch)
            encoding_class = encoding.removesuffix(".java") + ".class"
            with __import__("zipfile").ZipFile(
                original
                / "nifi-gcp-nar/NAR-INF/bundled-dependencies/opentelemetry-api-1.62.0.jar"
            ) as z:
                old_code = z.read(encoding_class)
            with __import__("zipfile").ZipFile(
                cache / "opentelemetry-api-1.67.0.jar"
            ) as z:
                new_code = z.read(encoding_class)
            if (
                b"java/util/regex/Pattern" not in old_code
                or b"TRACESTATE_ENTRY_DELIMITER_SPLIT_PATTERN" not in old_code
                or b"java/util/regex/Pattern" in new_code
                or b"lastIndexOf" not in new_code
            ):
                raise ValueError(
                    "encoding bytecode security-change control did not discriminate"
                )
            report.update(
                status="aligned-symbolic-analysis-completed",
                old_class_entries=old_data["class_entries"],
                new_class_entries=aligned_data["class_entries"],
                old_consumer_entries=len(old_data["consumers"]),
                aligned_consumer_entries=len(aligned_data["consumers"]),
                old_references=len(oldrefs),
                aligned_references=len(refs),
                narrow_negative_control=narrow_fail,
                reversed_sdk_api_negative_control=reversed_unknown,
                newly_broken_references=failures,
                missing_api_negative_new_failures=len(control),
                unresolved_old=old_unresolved,
                unresolved_current_references=classified,
                unresolved_including_api_family=all_classified,
                abi_delta=abi,
                actual_external_consumer_classes=len(aligned_data["external_models"]),
                selected_external_consumers=EXTERNAL_CONSUMERS,
                security_source_patch_sha256=q.sha(patch.encode()),
                security_evidence="actual changed encoding source and shipped bytecode; benign runtime limits are compatibility controls, not CVE closure",
                limits=[
                    "CP/inheritance/declared ABI and observed external implementations only; no complete JVM access/reflection/method-handle verifier",
                    "optional internal incubator symbols remain absent and paths unexecuted; external unresolved non-JDK symbols fail closed",
                    "physical duplicate/shadowed entries counted; loader checked separately",
                ],
            )
        else:
            out = b / "runtime"
            out.mkdir(exist_ok=False)
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
                    arguments.extend([file, c.expected_origin(known, pins, file)])
                consumers = json.loads(
                    (b / "external-consumers-for-probe.json").read_text()
                )
                if consumers != EXTERNAL_CONSUMERS:
                    raise ValueError("external consumer selection drift")
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
                        "observed_external_consumer_initialization": c.observed_consumers(
                            stdout
                        ),
                        "service_provider_lines": [
                            line
                            for line in stdout.splitlines()
                            if line.startswith(
                                ("service-provider\t", "service-result\t")
                            )
                        ],
                        "configutil_consumer_passed": "actual-sdk-configutil-consumer=pass"
                        in stdout,
                    }
                )
            c.require_consumer_parity(
                outcomes[0]["observed_external_consumer_initialization"],
                outcomes[2]["observed_external_consumer_initialization"],
                EXTERNAL_CONSUMERS,
            )
            if outcomes[1]["observed_external_consumer_initialization"]:
                raise ValueError(
                    "narrow early failure unexpectedly claimed later consumer initialization"
                )
            if (
                outcomes[0]["service_provider_lines"]
                != outcomes[2]["service_provider_lines"]
                or not outcomes[2]["service_provider_lines"]
            ):
                raise ValueError(
                    "explicit ResourceProvider loader coverage/parity mismatch"
                )
            if (
                not outcomes[0]["configutil_consumer_passed"]
                or not outcomes[2]["configutil_consumer_passed"]
            ):
                raise ValueError("SDK actual configuration consumer not observed")
            report.update(
                status="bounded-real-NarClassLoader-aligned-controls-passed",
                outcomes=outcomes,
                limits=[
                    "not NiFi scheduling/server, exporter operations, resource-provider getAttributes or GCP service acceptance",
                    "ResourceProvider constructors traversed with explicit NAR loader; actual processor InstanceClassLoader and TCCL remain unmodeled",
                    "unrelated gRPC/alpha artifacts unchanged; selected actual external consumers initialized with old/aligned parity",
                ],
            )
        c.verify_expanded(known, original, top)
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
