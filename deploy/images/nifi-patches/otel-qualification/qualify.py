"""Bounded OTel component qualification; never emits an applicable overlay."""

import hashlib
import io
import json
import re
import stat
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUNDLED = "META-INF/bundled-dependencies/"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def preparation_report(**values):
    if (
        values.get("runtime_approved", False) is not False
        or values.get("replacement") is not None
    ):
        raise ValueError("qualification cannot emit promotion")
    return values | {"replacement": None, "runtime_approved": False}


def verify_file(path, expected):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("linked input")
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024**2), b""):
            digest.update(block)
    if digest.hexdigest() != expected:
        raise ValueError("input integrity mismatch: " + str(path))
    return path


def checked(path, expected):
    return verify_file(path, expected).read_bytes()


def jar_entries(data):
    with zipfile.ZipFile(
        data if isinstance(data, Path) else io.BytesIO(data)
    ) as archive:
        infos = archive.infolist()
        names = [x.filename for x in infos]
        if len(names) != len(set(names)):
            raise ValueError("duplicate archive path")
        if len(infos) > 100000:
            raise ValueError("archive entry budget")
        for info in infos:
            name = info.filename
            if (
                name.startswith("/")
                or "\\" in name
                or ":" in name
                or any(x in ("", ".", "..") for x in name.rstrip("/").split("/"))
            ):
                raise ValueError("unsafe archive path")
            if stat.S_ISLNK(info.external_attr >> 16):
                raise ValueError("linked archive member")
            if info.file_size > 128 * 1024**2:
                raise ValueError("archive member budget")
        for info in infos:
            if info.filename.startswith(BUNDLED) and info.filename.endswith(".jar"):
                yield info.filename, archive.read(info)


def parent_chain(roots, child):
    result = []
    while child:
        if child in result:
            raise ValueError("NAR parent cycle")
        if child not in roots:
            raise ValueError("missing NAR parent")
        result.append(child)
        manifest = roots[child]
        parent = manifest.get("Nar-Dependency-Id")
        if parent:
            if parent not in roots:
                raise ValueError("missing NAR parent")
            wanted = (
                manifest.get("Nar-Dependency-Group"),
                manifest.get("Nar-Dependency-Version"),
            )
            actual = (roots[parent].get("Nar-Group"), roots[parent].get("Nar-Version"))
            if wanted != actual:
                raise ValueError("NAR parent coordinates mismatch")
        child = parent
    return result


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


def required_closure(models, root):
    """Acyclic literal declarations for pinned simple POMs, not Maven mediation."""
    found = set()

    def visit(coordinate, stack):
        if coordinate in stack:
            raise ValueError("dependency cycle")
        if coordinate not in models:
            raise ValueError("missing pinned dependency declaration: " + coordinate)
        if coordinate in found:
            return
        for dependency in models[coordinate]:
            if dependency.get("optional") == "true" or dependency.get(
                "scope", "compile"
            ) not in (None, "compile", "runtime"):
                continue
            values = [
                dependency.get(key) for key in ("groupId", "artifactId", "version")
            ]
            if not all(
                isinstance(value, str) and value and "${" not in value
                for value in values
            ):
                raise ValueError("unsupported dependency selector")
            visit(":".join(values), stack + (coordinate,))
        found.add(coordinate)

    visit(root, ())
    return sorted(found)


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


def classes(path):
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
                if version > 21:
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
