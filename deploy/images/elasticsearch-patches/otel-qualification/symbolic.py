"""Reused narrow class-file model from NiFi preparation; not a JVM verifier.
Source: deploy/images/nifi-patches/otel-qualification/qualify.py at preparation.
ES realm semantics, module checks and runtime qualification are separate.
"""

import io
import re
import zipfile


def resolve(models, owner, key, seen=None):
    seen = set() if seen is None else seen
    if owner in seen or owner not in models:
        return None
    seen.add(owner)
    model = models[owner]
    if key[0] in ("class", "descriptor"):
        return owner
    if key in model["members"]:
        return owner
    if key[1] == "<init>":
        return None
    for parent in model["parents"]:
        found = resolve(models, parent, key, seen)
        if found:
            return found
    return None


def newly_broken(old, new, references):
    if not references:
        raise ValueError("no actual consumer references")
    result = []
    for consumer, reference in references:
        owner, name, descriptor, kind = reference
        key = (kind, name, descriptor)
        if resolve(old, owner, key) and not resolve(new, owner, key):
            result.append({"consumer": consumer, "reference": list(reference)})
    return result


def parse(data):
    """Class-file declarations/CP references; not a complete JVM verifier."""
    stream = io.BytesIO(data)

    def u(size):
        block = stream.read(size)
        if len(block) != size:
            raise ValueError("truncated class")
        return int.from_bytes(block, "big")

    if u(4) != 0xCAFEBABE:
        raise ValueError("class magic")
    u(2)
    major = u(2)
    cp = [None] * u(2)
    index = 1
    while index < len(cp):
        tag = u(1)
        if tag == 1:
            length = u(2)
            text = stream.read(length)
            if len(text) != length:
                raise ValueError("truncated UTF8")
            cp[index] = text.decode("utf8", "replace")
        elif tag in (7, 8, 16, 19, 20):
            cp[index] = (tag, u(2))
        elif tag in (9, 10, 11, 12, 17, 18):
            cp[index] = (tag, u(2), u(2))
        elif tag in (3, 4):
            u(4)
        elif tag in (5, 6):
            u(8)
            index += 1
        elif tag == 15:
            cp[index] = (tag, u(1), u(2))
        else:
            raise ValueError("unknown constant tag")
        index += 1

    def cls(index):
        return cp[cp[index][1]]

    refs = set()
    details = set()
    descriptors = set()
    for item in cp:
        if isinstance(item, tuple) and item[0] in (12, 16):
            descriptor = cp[item[2] if item[0] == 12 else item[1]]
            descriptors.update(re.findall(r"L(io/opentelemetry/[^;]+);", descriptor))
        if isinstance(item, tuple) and item[0] == 7:
            name = cp[item[1]]
            if name.startswith("io/opentelemetry/"):
                refs.add((name, "", "", "class"))
                details.add((name, "", "", "class", 7))
        if isinstance(item, tuple) and item[0] in (9, 10, 11):
            owner = cls(item[1])
            if owner.startswith("io/opentelemetry/"):
                nt = cp[item[2]]
                reference = (
                    owner,
                    cp[nt[1]],
                    cp[nt[2]],
                    "field" if item[0] == 9 else "method",
                )
                refs.add(reference)
                details.add((*reference, item[0]))
    flags = u(2)
    name = cls(u(2))
    sup = u(2)
    parents = ([cls(sup)] if sup else []) + [cls(u(2)) for _ in range(u(2))]
    members = {}
    for kind in ("field", "method"):
        for _ in range(u(2)):
            access, member, descriptor = u(2), cp[u(2)], cp[u(2)]
            members[(kind, member, descriptor)] = access
            descriptors.update(re.findall(r"L(io/opentelemetry/[^;]+);", descriptor))
            for _ in range(u(2)):
                u(2)
                size = u(4)
                if len(stream.read(size)) != size:
                    raise ValueError("truncated attribute")
    return {
        "name": name,
        "flags": flags,
        "major": major,
        "parents": parents,
        "members": members,
        "references": sorted(refs),
        "reference_details": sorted(details),
        "descriptor_types": sorted(descriptors),
    }


def classes(path, java_feature):
    if not isinstance(java_feature, int) or not 21 <= java_feature <= 30:
        raise ValueError("explicit supported runtime feature required")
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("duplicate class archive names")
        manifest = (
            archive.read("META-INF/MANIFEST.MF")
            if "META-INF/MANIFEST.MF" in names
            else b""
        )
        multi = b"Multi-Release: true" in manifest.replace(b"\r\n ", b"")
        selected = {}
        for name in names:
            if not name.endswith(".class"):
                continue
            version, base = 0, name
            if name.startswith("META-INF/versions/"):
                if not multi:
                    continue
                _, _, raw, base = name.split("/", 3)
                version = int(raw)
                if version > java_feature:
                    continue
            if base == "module-info.class":
                continue
            if base not in selected or selected[base][0] < version:
                selected[base] = (version, name)
        for base, (_, name) in selected.items():
            if archive.getinfo(name).file_size > 8 * 1024**2:
                raise ValueError("class member budget")
            yield base, parse(archive.read(name))


def manifest(data):
    text = data.decode("utf8").replace("\r\n", "\n").replace("\n ", "")
    return dict(line.split(": ", 1) for line in text.splitlines() if ": " in line)
