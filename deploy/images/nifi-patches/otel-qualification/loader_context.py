"""Pinned read-only loader inputs; extracts only into a fresh private proof."""

import importlib.util
import zipfile
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "_otel_loader_q", Path(__file__).with_name("qualify.py")
)
q = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q)


def verify_parent_table(known, file):
    expected = "".join(
        r["id"] + "\t" + r["manifest"].get("Nar-Dependency-Id", "") + "\n"
        for r in known["nar_chain"]
    ).encode()
    q.verify_file(file, q.sha(expected))
    return q.sha(expected)


def verify_image_roots(known):
    for row in known["nar_chain"]:
        file = q.verify_file(Path("/") / row["path"], row["sha256"])
        with zipfile.ZipFile(file) as z:
            manifest = q.manifest(z.read("META-INF/MANIFEST.MF"))
        if {k: v for k, v in manifest.items() if k.startswith("Nar-")} != row[
            "manifest"
        ]:
            raise ValueError("actual NAR root manifest drift")


def extract_loader_inputs(inputs, output):
    output = Path(output)
    output.mkdir(exist_ok=False)
    for key, nar_id in [
        ("jetty", "nifi-jetty-nar"),
        ("instance_loader", "nifi-framework-nar"),
    ]:
        row = inputs[key]
        path = q.verify_file(Path("/") / row["path"], row["sha256"])
        expected = {r["entry"]: r["sha256"] for r in row["direct_jars"]}
        with zipfile.ZipFile(path) as archive:
            actual = q.manifest(archive.read("META-INF/MANIFEST.MF"))
            if actual != row["manifest"]:
                raise ValueError("loader NAR manifest drift")
        leaf = output / nar_id / "NAR-INF/bundled-dependencies"
        leaf.mkdir(parents=True)
        seen = set()
        for name, data in q.jar_entries(path):
            if name not in expected or q.sha(data) != expected[name]:
                raise ValueError("loader NAR input drift")
            with zipfile.ZipFile(__import__("io").BytesIO(data)) as jar:
                if any(n.startswith("io/opentelemetry/") for n in jar.namelist()):
                    raise ValueError("unexpected OTel in loader parent")
            (leaf / Path(name).name).write_bytes(data)
            seen.add(name)
        if seen != set(expected):
            raise ValueError("loader NAR closure incomplete")
        q.verify_file(path, row["sha256"])
    verify_extracted_loader_inputs(inputs, output)
    return output


def verify_extracted_loader_inputs(inputs, output):
    for key, nar_id in [
        ("jetty", "nifi-jetty-nar"),
        ("instance_loader", "nifi-framework-nar"),
    ]:
        row = inputs[key]
        leaf = Path(output) / nar_id / "NAR-INF/bundled-dependencies"
        expected = {Path(x["entry"]).name: x["sha256"] for x in row["direct_jars"]}
        if {p.name for p in leaf.iterdir()} != set(expected):
            raise ValueError("private loader inventory drift")
        for name, digest in expected.items():
            q.verify_file(leaf / name, digest)


def verify_loader_sources(inputs):
    for row in (inputs["jetty"], inputs["instance_loader"]):
        q.verify_file(Path("/") / row["path"], row["sha256"])
    q.verify_file(Path("/jdk/jmods/java.base.jmod"), inputs["java_base_jmod"])
