"""Explicit bounded coverage/ABI policy; no overlay or runtime approval."""

import difflib
import importlib.util
import re
import zipfile
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "_otel_coverage_q", Path(__file__).with_name("qualify.py")
)
q = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q)

# Exact JDK declarations, not a name-only exemption. A present OTel owner must
# inherit the declaring JDK type along its modeled chain.
JDK_MEMBERS = {
    "java/lang/Object": {
        ("equals", "(Ljava/lang/Object;)Z"),
        ("hashCode", "()I"),
        ("getClass", "()Ljava/lang/Class;"),
        ("toString", "()Ljava/lang/String;"),
    },
    "java/lang/Enum": {("ordinal", "()I"), ("name", "()Ljava/lang/String;")},
    "java/lang/Throwable": {("getMessage", "()Ljava/lang/String;")},
    "java/util/function/Function": {
        ("apply", "(Ljava/lang/Object;)Ljava/lang/Object;")
    },
}
JDK_PARENTS = {
    "java/lang/Enum": ["java/lang/Object"],
    "java/lang/RuntimeException": ["java/lang/Exception"],
    "java/lang/Exception": ["java/lang/Throwable"],
    "java/lang/Throwable": ["java/lang/Object"],
}


def ancestry(models, owner, seen=None):
    seen = set() if seen is None else seen
    if owner in seen:
        return set()
    seen.add(owner)
    parents = models.get(owner, {}).get("parents", JDK_PARENTS.get(owner, []))
    return {owner}.union(*(ancestry(models, p, seen) for p in parents))


def reference_identity(consumer, reference):
    # Version changes do not turn an unchanged caller/symbol into a new finding.
    label = re.sub(r"(opentelemetry-[^!]+)-1\.(?:62|67)\.0\.jar", r"\1.jar", consumer)
    return label, tuple(reference)


def load_jdk_ancestors(models, jmod):
    """Read the mounted compiler JDK declarations, not name-only exemptions."""
    pending = {p for m in models.values() for p in m["parents"] if p.startswith("java/")}
    result = {}
    with zipfile.ZipFile(jmod) as archive:
        while pending:
            owner = pending.pop()
            if owner in result:
                continue
            model = q.parse(archive.read("classes/" + owner + ".class"))
            if model["name"] != owner:
                raise ValueError("JDK class identity mismatch")
            result[owner] = model
            pending.update(p for p in model["parents"] if p.startswith("java/") and p not in result)
    return result


def classify_unresolved(models, references, scenario, old_identities, jdk_models=None):
    rows = []
    for caller, ref in references:
        owner, name, descriptor, kind = ref
        if q.resolve(models, owner, (kind, name, descriptor)):
            continue
        category = "unknown"
        inherited_from = None
        if jdk_models is not None and owner in models and kind == "method":
            declaring = q.resolve(models | jdk_models, owner, (kind, name, descriptor))
            if declaring in jdk_models and jdk_models[declaring]["members"].get((kind, name, descriptor), 0) & 1:
                category, inherited_from = "jdk-inherited-member", declaring
        elif owner in models and kind == "method":
            for parent in sorted(ancestry(models, owner)):
                if (name, descriptor) in JDK_MEMBERS.get(parent, set()):
                    category, inherited_from = "jdk-inherited-member", parent
                    break
        parts = caller.split("!")
        internal = (
            len(parts) == 3
            and re.fullmatch(
                r"opentelemetry-(?:api|context|common|sdk(?:-(?:common|trace|metrics|logs|extension-autoconfigure-spi))?)-1\.(?:62|67)\.0\.jar",
                parts[1],
            )
            and parts[2].startswith("io/opentelemetry/")
        )
        if (
            owner.startswith("io/opentelemetry/api/incubator/")
            and owner not in models
            and internal
        ):
            category = "internal-optional-incubator"
        # The original SDK logs invokes an inherited default from an absent
        # incubator interface. Keep this one observed optional path explicit;
        # do not exempt other missing members merely because an interface is absent.
        if (
            caller == "nifi-gcp-nar!opentelemetry-sdk-logs-1.62.0.jar!io/opentelemetry/sdk/logs/ExtendedSdkLogRecordBuilder.class"
            and ref == ("io/opentelemetry/sdk/common/internal/ExtendedAttributesMap", "get", "(Lio/opentelemetry/api/common/AttributeKey;)Ljava/lang/Object;", "method")
            and "io/opentelemetry/api/incubator/common/ExtendedAttributes" in ancestry(models, owner)
            and "io/opentelemetry/api/incubator/common/ExtendedAttributes" not in models
        ):
            category = "internal-optional-incubator-inherited-member"
        rows.append(
            {
                "consumer": caller,
                "reference": list(ref),
                "scenario": scenario,
                "category": category,
                "jdk_declaring_type": inherited_from,
                "seen_in_old": reference_identity(caller, ref) in old_identities,
            }
        )
    return rows


def require_closed(records):
    unknown = [r for r in records if r["category"] == "unknown"]
    if unknown:
        raise ValueError(f"unclassified unresolved references: {len(unknown)}")


def verify_expanded(known, original, top):
    checked = []
    for row in known["nar_chain"]:
        root = original / row["id"] / "NAR-INF/bundled-dependencies"
        expected = {Path(x["entry"]).name: x["sha256"] for x in row["direct_jars"]}
        actual = {p.name for p in root.glob("*.jar")}
        if actual != set(expected):
            raise ValueError("expanded JAR inventory mismatch: " + row["id"])
        for name, digest in expected.items():
            q.verify_file(root / name, digest)
            checked.append({"nar": row["id"], "jar": name, "sha256": digest})
    expected = {Path(x["path"]).name: x["sha256"] for x in known["launcher_jars"]}
    if {p.name for p in top.glob("*.jar")} != set(expected):
        raise ValueError("launcher JAR inventory mismatch")
    for name, digest in expected.items():
        q.verify_file(top / name, digest)
    return {"direct_jars": checked, "launcher_jars": expected}


def expected_origin(known, pins, filename):
    fixed = [x["sha256"] for x in pins["files"] if x["file"] == filename]
    old = [
        x["sha256"]
        for r in known["nar_chain"]
        for x in r["direct_jars"]
        if Path(x["entry"]).name == filename
    ]
    matches = fixed or old
    if not matches or len(set(matches)) != 1:
        raise ValueError("missing/ambiguous independently pinned origin: " + filename)
    return matches[0]


def abi_delta(old, new, external, details):
    result = {
        k: []
        for k in (
            "removed_classes",
            "added_classes",
            "declared_public_protected_removals",
            "new_abstract_members",
            "access_restrictions",
            "static_changes",
            "class_interface_changes",
            "new_final_classes",
            "external_impacts",
        )
    }
    result["removed_classes"] = sorted(set(old) - set(new))
    result["added_classes"] = sorted(set(new) - set(old))
    for owner in sorted(set(old) & set(new)):
        before, after = old[owner], new[owner]
        for key, flags in before["members"].items():
            if key not in after["members"] and flags & 5:
                result["declared_public_protected_removals"].append(
                    [owner, *key, flags]
                )
            if key in after["members"]:
                newflags = after["members"][key]
                if (flags & 1 and not newflags & 1) or (flags & 4 and not newflags & 5):
                    result["access_restrictions"].append([owner, *key, flags, newflags])
                if bool(flags & 8) != bool(newflags & 8):
                    result["static_changes"].append([owner, *key, flags, newflags])
        for key, flags in after["members"].items():
            if flags & 0x400 and not before["members"].get(key, 0) & 0x400:
                result["new_abstract_members"].append([owner, *key, flags])
        if bool(before["flags"] & 0x200) != bool(after["flags"] & 0x200):
            result["class_interface_changes"].append(owner)
        if not before["flags"] & 16 and after["flags"] & 16:
            result["new_final_classes"].append(owner)
    combined = new | external
    for caller, model in external.items():
        if model["flags"] & (0x200 | 0x400):
            continue
        parents = ancestry(combined, caller)
        for owner, kind, name, desc, _ in result["new_abstract_members"]:
            if owner in parents:
                resolved = q.resolve(combined, caller, (kind, name, desc))
                if (
                    resolved is None
                    or combined[resolved]["members"][(kind, name, desc)] & 0x400
                ):
                    result["external_impacts"].append(
                        {
                            "caller": caller,
                            "kind": "unimplemented-new-abstract",
                            "owner": owner,
                            "member": [kind, name, desc],
                        }
                    )
        for descriptor_type in model.get("descriptor_types", []):
            if descriptor_type in old and descriptor_type not in new:
                result["external_impacts"].append(
                    {
                        "caller": caller,
                        "kind": "removed-descriptor-type",
                        "owner": descriptor_type,
                    }
                )
    for caller, ref in details:
        owner, name, descriptor, kind, tag = ref
        key = (kind, name, descriptor)
        before = q.resolve(old, owner, key)
        after = q.resolve(new, owner, key)
        if before and not after:
            result["external_impacts"].append(
                {"caller": caller, "kind": "removed-reference", "reference": list(ref)}
            )
        elif before and after and kind != "class":
            bf, af = old[before]["members"][key], new[after]["members"][key]
            if (
                (bf & 1 and not af & 1)
                or (bf & 4 and not af & 5)
                or bool(bf & 8) != bool(af & 8)
            ):
                result["external_impacts"].append(
                    {
                        "caller": caller,
                        "kind": "access-or-static-change",
                        "reference": list(ref),
                    }
                )
            if (
                kind == "method"
                and tag in (10, 11)
                and owner in old
                and owner in new
                and bool(old[owner]["flags"] & 0x200)
                != bool(new[owner]["flags"] & 0x200)
            ):
                result["external_impacts"].append(
                    {
                        "caller": caller,
                        "kind": "methodref-interface-kind-change",
                        "reference": list(ref),
                    }
                )
    return result


def observed_consumers(stdout):
    result = {}
    for line in stdout.splitlines():
        if line.startswith("consumer-init\t"):
            _, name, status, cause = line.split("\t")
            if name in result or status not in ("PASS", "FAIL"):
                raise ValueError("ambiguous consumer coverage")
            result[name] = {"status": status, "cause": cause}
    return result


def require_consumer_parity(old, new, expected):
    if set(old) != set(expected) or set(new) != set(expected) or old != new:
        raise ValueError("external consumer initialization coverage/parity mismatch")


def source_change(old, new, entry):
    with zipfile.ZipFile(old) as a, zipfile.ZipFile(new) as b:
        patch = "".join(
            difflib.unified_diff(
                a.read(entry).decode().splitlines(True),
                b.read(entry).decode().splitlines(True),
                fromfile="old/" + entry,
                tofile="aligned/" + entry,
            )
        )
    if not patch:
        raise ValueError("empty security source diff")
    return patch
