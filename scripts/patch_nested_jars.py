"""Occurrence-complete, offline ZIP inventory and exact hash-bound copy patcher.

CLI is dry-run unless --apply. No dependency resolution or candidate approval.
"""
import argparse
import copy
import hashlib
import json
import os
import re
import resource
import shutil
import stat
import struct
import tempfile
import zipfile
import zlib
from pathlib import Path

EXTENSIONS = {'.jar', '.nar', '.war', '.zip'}
CHUNK = 1024 * 1024
BLOCKED_INPUTS = {
    '70d5c152622df6fffbf8836af7833215dc7acdd5d9c881af11b8c0fbf30cdc0a',
    '396d48d93ef5735f2ddef0cf9b3d6968ebd67b64b5cfe753d41c429d3f46a2a1',
    'c23f1dffc08e2c209035f8d22a48edfd83477b629477e9416a5d25e2c116f3f6',
}
DEFAULTS = {'max_depth': 8, 'max_entries': 1000000, 'max_bytes': 32 * 1024**3,
                'max_archive': 256 * 1024**2}


def canonical(name):
    if (not isinstance(name, str) or not name or '\\' in name or '\x00' in name
            or name.startswith('/') or ':' in name or '//' in name
            or any(ord(c) < 32 for c in name)
            or any(p in ('', '.', '..') for p in name.rstrip('/').split('/'))):
        raise ValueError(f'noncanonical path: {name!r}')
    return name


def regular(path):
    path = Path(path).absolute()
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError(f'symlink input: {part}')
    if not path.is_file():
        raise ValueError(f'not a regular file: {path}')
    return Path(os.path.abspath(path))


def digest(path):
    h = hashlib.sha256()
    with regular(path).open('rb') as f:
        for b in iter(lambda: f.read(CHUNK), b''):
            h.update(b)
    return h.hexdigest()


def inventory_hash(rows):
    return hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def files(source):
    source = Path(source).absolute()
    for p in (source, *source.parents):
        if p.is_symlink():
            raise ValueError(f'symlink source: {p}')
    source = Path(os.path.abspath(source))
    if not source.is_dir():
        raise ValueError('source must be a directory')
    result = []
    for base, dirs, names in os.walk(source, followlinks=False):
        for name in sorted(dirs + names):
            p = Path(base) / name
            if p.is_symlink():
                raise ValueError(f'symlink in source: {p}')
            if not p.is_dir() and not stat.S_ISREG(p.stat().st_mode):
                raise ValueError(f'special file in source: {p}')
        for name in names:
            p = Path(base) / name
            canonical(p.relative_to(source).as_posix())
            if p.suffix.lower() in EXTENSIONS:
                result.append(p)
    if not result:
        raise ValueError('no archives in source')
    return sorted(result)


class Budget:
    def __init__(self, **limits):
        self.limits = DEFAULTS | limits
        if any(type(v) is not int or not 0 <= v <= DEFAULTS[k] for k, v in self.limits.items()):
            raise ValueError('budgets must be nonnegative integers no greater than defaults')
        self.entries = self.bytes = 0

    def add(self, size=0, entries=0):
        self.entries += entries
        self.bytes += size
        if self.entries > self.limits['max_entries'] or self.bytes > self.limits['max_bytes']:
            raise ValueError(f'archive budget exceeded: entries={self.entries}, bytes={self.bytes}')


def checked_entries(z, budget):
    seen = set()
    entries = z.infolist()
    budget.add(entries=len(entries))
    for i in entries:
        canonical(i.filename)
        key = i.filename.rstrip('/')
        if key in seen or i.orig_filename != i.filename:
            raise ValueError(f'duplicate/ambiguous ZIP path: {i.filename}')
        seen.add(key)
        mode = i.external_attr >> 16
        # Several pinned legacy Maven JARs use -1 as an unset Unix mode on
        # empty STORED directory records. No filesystem extraction occurs.
        # Recognize only that exact inert representation; links, special files,
        # nonempty records and other unknown modes remain rejected.
        legacy_empty_directory = (
            i.create_system == 3 and i.external_attr == 0xffff0010
            and i.is_dir() and i.file_size == i.compress_size == i.CRC == 0
            and i.compress_type == zipfile.ZIP_STORED
        )
        if not legacy_empty_directory and stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR):
            raise ValueError(f'ZIP special file/symlink: {i.filename}')
        if i.flag_bits & 1 or i.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
            raise ValueError(f'encrypted/unsupported ZIP entry: {i.filename}')
        if i.file_size > budget.limits['max_archive']:
            raise ValueError(f'entry size budget exceeded: {i.filename}')
        budget.add(size=i.file_size)
    validate_layout(z, entries)
    directories = {i.filename for i in entries if i.is_dir()}
    for key in seen:
        parts = key.split('/')
        for n in range(1, len(parts)):
            parent = '/'.join(parts[:n])
            if parent in seen and parent + '/' not in directories:
                raise ValueError(f'file/directory path collision: {key}')
    return entries


def validate_layout(z, entries):
    """Refuse hidden payloads and ambiguous local/central ZIP representations."""
    ordered = sorted(entries, key=lambda i: i.header_offset)
    if (ordered and ordered[0].header_offset != 0) or (not ordered and z.start_dir != 0):
        raise ValueError('ZIP preamble is unsupported')
    for index, info in enumerate(ordered):
        boundary = ordered[index + 1].header_offset if index + 1 < len(ordered) else z.start_dir
        z.fp.seek(info.header_offset)
        raw = z.fp.read(30)
        if len(raw) != 30:
            raise ValueError('truncated local ZIP header')
        sig, _version, flags, method, _time, _date, crc, compressed, size, namesize, extrasize = struct.unpack('<4s5H3I2H', raw)
        if sig != b'PK\x03\x04' or flags != info.flag_bits or method != info.compress_type:
            raise ValueError('local/central ZIP header mismatch')
        name = z.fp.read(namesize)
        extra = z.fp.read(extrasize)
        if len(name) != namesize or len(extra) != extrasize:
            raise ValueError('truncated local ZIP metadata')
        if name.decode('utf-8' if flags & 0x800 else 'cp437') != info.orig_filename:
            raise ValueError('local/central ZIP name mismatch')
        if not flags & 0x800 and not info.filename.isascii():
            raise ValueError('non-ASCII ZIP name without UTF-8 flag')
        # ZIP64 values are ordered only for sentinel fields that are present.
        if size == 0xffffffff or compressed == 0xffffffff:
            offset = 0
            values = b''
            while offset + 4 <= len(extra):
                kind, length = struct.unpack_from('<HH', extra, offset)
                offset += 4
                if offset + length > len(extra):
                    raise ValueError('truncated ZIP64 extra')
                if kind == 1:
                    values = extra[offset:offset + length]
                    break
                offset += length
            for field in ('size', 'compressed'):
                if (size if field == 'size' else compressed) == 0xffffffff:
                    if len(values) < 8:
                        raise ValueError('missing local ZIP64 value')
                    value, = struct.unpack_from('<Q', values)
                    values = values[8:]
                    if field == 'size': size = value
                    else: compressed = value
        end = info.header_offset + 30 + namesize + extrasize + info.compress_size
        gap = boundary - end
        if flags & 8:
            if gap not in (12, 16, 20, 24):
                raise ValueError('invalid ZIP data descriptor boundary')
            z.fp.seek(end)
            descriptor = z.fp.read(gap)
            if len(descriptor) != gap:
                raise ValueError('truncated ZIP data descriptor')
            if gap in (16, 24):
                if descriptor[:4] != b'PK\x07\x08':
                    raise ValueError('invalid ZIP data descriptor signature')
                descriptor = descriptor[4:]
            actual = struct.unpack('<IQQ' if len(descriptor) == 20 else '<III', descriptor)
            if actual != (info.CRC, info.compress_size, info.file_size):
                raise ValueError('local/central ZIP descriptor mismatch')
        elif gap != 0 or (crc, compressed, size) != (info.CRC, info.compress_size, info.file_size):
            raise ValueError('local/central ZIP size/CRC boundary mismatch')
        if info.is_dir():
            if info.file_size or info.CRC or info.compress_size > 16:
                raise ValueError('directory has ZIP payload')
            z.fp.seek(info.header_offset + 30 + namesize + extrasize)
            payload = z.fp.read(info.compress_size)
            if method == zipfile.ZIP_STORED:
                if payload: raise ValueError('directory has ZIP payload')
            elif method == zipfile.ZIP_DEFLATED:
                decoder = zlib.decompressobj(-15)
                if decoder.decompress(payload, 1) or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
                    raise ValueError('directory has compressed ZIP payload')


def transfer(src, dst, limit):
    h = hashlib.sha256()
    size = 0
    while True:
        b = src.read(CHUNK)
        if not b:
            break
        size += len(b)
        if size > limit:
            raise ValueError('stream size budget exceeded')
        h.update(b)
        if dst is not None:
            dst.write(b)
    return h.hexdigest()


def manifest_fields(data):
    text = data.decode('utf-8', errors='replace').replace('\r\n', '\n')
    text = re.sub(r'\n ', '', text)
    return dict(line.split(': ', 1) for line in text.split('\n\n', 1)[0].splitlines() if ': ' in line)


def inventory(source, **limits):
    """Every archive occurrence, including loose JARs and equal-hash ancestry."""
    source = Path(source).absolute()
    budget = Budget(**limits)
    rows = []

    def visit(path, outer, members, chain):
        if len(members) > budget.limits['max_depth']:
            raise ValueError(f'depth budget exceeded: {outer}!{members}')
        if path.stat().st_size > budget.limits['max_archive']:
            raise ValueError(f'archive size budget exceeded: {outer}!{members}')
        hash_ = digest(path)
        chain = chain + [hash_]
        row = {'outer': outer, 'members': members, 'chain_sha256': chain,
                   'outer_sha256': chain[0], 'sha256': hash_, 'manifest': {}, 'maven': [],
                   'class_packages': [], 'signed': False}
        rows.append(row)
        with zipfile.ZipFile(path) as z:
            try:
                entries = checked_entries(z, budget)
            except ValueError as e:
                raise ValueError(f'{outer}!{members}: {e}') from e
            packages = set()
            for i in entries:
                name = i.filename
                upper = name.upper()
                if upper.startswith('META-INF/') and '/' not in upper[9:] and (
                        upper.endswith(('.SF', '.RSA', '.DSA', '.EC')) or upper[9:].startswith('SIG-')):
                    row['signed'] = True
                if name.endswith('.class') and '/' in name:
                    packages.add(name.rsplit('/', 1)[0])
                # Read every entry to check CRC/truncation; nested payloads live on disk.
                with z.open(i) as f:
                    if Path(name).suffix.lower() in EXTENSIONS and not i.is_dir():
                        with tempfile.TemporaryDirectory() as tmp:
                            child = Path(tmp) / 'archive'
                            with child.open('wb') as out:
                                transfer(f, out, budget.limits['max_archive'])
                            visit(child, outer, members + [name], chain)
                    elif upper == 'META-INF/MANIFEST.MF' or (name.startswith('META-INF/maven/') and name.endswith('/pom.properties')):
                        if i.file_size > 1024 * 1024:
                            raise ValueError(f'metadata size budget exceeded: {name}')
                        data = f.read(1024 * 1024 + 1)
                        if upper == 'META-INF/MANIFEST.MF':
                            row['manifest'] = manifest_fields(data)
                            if re.search(rb'(?im)^[-\w]+-Digest(?:-Manifest)?:', data):
                                row['signed'] = True
                        else:
                            row['maven'].append({'path': name, 'sha256': hashlib.sha256(data).hexdigest(),
                                                     'properties': data.decode('utf-8', errors='replace')})
                    else:
                        transfer(f, None, budget.limits['max_archive'])
            row['class_packages'] = sorted(packages)
        return row

    try:
        for path in files(source):
            visit(path, path.relative_to(source).as_posix(), [], [])
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError, EOFError, zlib.error, UnicodeError) as e:
        raise ValueError(f'invalid/unsupported archive: {e}') from e
    return rows


def exact_keys(obj, keys):
    if not isinstance(obj, dict) or set(obj) != set(keys.split()):
        raise ValueError(f'unknown/missing plan fields; expected {keys}')


def rewrite(path, output, targets, depth=0):
    """Rebuild each changed ancestor once; stock replacement bytes are opaque."""
    direct = [t for t in targets if len(t['members']) == depth]
    if direct:
        shutil.copyfile(direct[0]['replacement'], output)
        return
    with zipfile.ZipFile(path) as src, zipfile.ZipFile(output, 'w', allowZip64=True) as dst:
        dst.comment = src.comment
        for i in src.infolist():
            copied = copy.copy(i)
            external_attr = i.external_attr
            subset = [t for t in targets if t['members'][depth] == i.filename]
            if subset:
                with tempfile.TemporaryDirectory() as tmp:
                    old, new = Path(tmp) / 'old', Path(tmp) / 'new'
                    with src.open(i) as f, old.open('wb') as o:
                        shutil.copyfileobj(f, o, CHUNK)
                    rewrite(old, new, subset, depth + 1)
                    with new.open('rb') as f, dst.open(copied, 'w') as o:
                        shutil.copyfileobj(f, o, CHUNK)
            else:
                with src.open(i) as f, dst.open(copied, 'w') as o:
                    shutil.copyfileobj(f, o, CHUNK)
            # zipfile substitutes a default when external_attr is zero. Restore
            # the actual input value before it writes the central directory.
            copied.external_attr = external_attr


def verify_rewrite(original, output, targets, depth=0):
    """Verify every rewritten ancestor and every unaffected sibling before publish."""
    direct = [t for t in targets if len(t['members']) == depth]
    if direct:
        if digest(output) != direct[0]['replacement_sha256']:
            raise ValueError('post-write leaf verification failed')
        return
    with zipfile.ZipFile(original) as src, zipfile.ZipFile(output) as dst:
        left, right = src.infolist(), dst.infolist()
        if src.comment != dst.comment or [i.filename for i in left] != [i.filename for i in right]:
            raise ValueError('post-write sibling names/order/comment mismatch')
        metadata = ('date_time', 'compress_type', 'comment', 'extra', 'external_attr',
                    'internal_attr', 'create_system', 'create_version', 'extract_version')
        for old, new in zip(left, right):
            if any(getattr(old, field) != getattr(new, field) for field in metadata):
                raise ValueError('post-write sibling metadata mismatch')
            subset = [t for t in targets if t['members'][depth] == old.filename]
            if subset:
                with tempfile.TemporaryDirectory() as tmp:
                    a, b = Path(tmp) / 'original', Path(tmp) / 'output'
                    with src.open(old) as f, a.open('wb') as o: shutil.copyfileobj(f, o, CHUNK)
                    with dst.open(new) as f, b.open('wb') as o: shutil.copyfileobj(f, o, CHUNK)
                    verify_rewrite(a, b, subset, depth + 1)
            else:
                hashes = []
                for archive, info in ((src, old), (dst, new)):
                    h = hashlib.sha256()
                    with archive.open(info) as f:
                        for block in iter(lambda: f.read(CHUNK), b''): h.update(block)
                    hashes.append(h.digest())
                if hashes[0] != hashes[1]:
                    raise ValueError('post-write sibling content mismatch')


def patch(source, output, plan, apply=False, **limits):
    source, output = Path(source).absolute(), Path(output).absolute()
    if output.exists() or output.is_symlink():
        raise ValueError('output must not exist')
    for p in (output.parent, *output.parent.parents):
        if p.is_symlink():
            raise ValueError('symlink output parent')
    # Validate original path components before normalizing '..' aliases.
    for p in (source, *source.parents):
        if p.is_symlink():
            raise ValueError('symlink source')
    source, output = Path(os.path.abspath(source)), Path(os.path.abspath(output))
    if source == output or source in output.parents or output in source.parents:
        raise ValueError('overlapping input/output')
    exact_keys(plan, 'schema inventory_sha256 targets')
    if type(plan['schema']) is not int or plan['schema'] != 1 or not isinstance(plan['targets'], list) or not plan['targets']:
        raise ValueError('unsupported/empty executable plan')
    # Stable owned snapshots bind preflight to writer, including replacement bytes.
    with tempfile.TemporaryDirectory(prefix='.nested-preflight-', dir=output.parent) as tmp:
        staging = Path(tmp)
        snapshot = staging / 'inputs'
        snapshot.mkdir()
        snapshot_bytes = 0
        for p in files(source):
            size = p.stat().st_size
            snapshot_bytes += size
            if size > (DEFAULTS | limits)['max_archive'] or snapshot_bytes > (DEFAULTS | limits)['max_bytes']:
                raise ValueError('input snapshot size budget exceeded')
            dest = snapshot / p.relative_to(source)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, dest)
        inv = inventory(snapshot, **limits)
        if inventory_hash(inv) != plan['inventory_sha256']:
            raise ValueError('complete inventory hash mismatch')
        bykey = {(r['outer'], tuple(r['members'])): r for r in inv}
        selected, checked = {}, []
        replacements = staging / 'replacements'
        replacements.mkdir()
        for index, t in enumerate(plan['targets']):
            exact_keys(t, 'outer members chain_sha256 replacement replacement_sha256 status expected_occurrences')
            if t['status'] != 'approved-exact-occurrence':
                raise ValueError('blocked/unapproved plan entry')
            canonical(t['outer'])
            if not isinstance(t['members'], list) or any(not isinstance(m, str) for m in t['members']):
                raise ValueError('members must be exact path strings')
            for member in t['members']: canonical(member)
            key = (t['outer'], tuple(t['members']))
            r = bykey.get(key)
            if key in selected or r is None or t['chain_sha256'] != r['chain_sha256']:
                raise ValueError('duplicate/missing occurrence or preimage hash mismatch')
            if set(r['chain_sha256']) & BLOCKED_INPUTS:
                raise ValueError('known blocked candidate input; separate review required')
            count = sum(x['sha256'] == r['sha256'] for x in inv)
            if type(t['expected_occurrences']) is not int or t['expected_occurrences'] != count:
                raise ValueError('occurrence count mismatch')
            if not isinstance(t['replacement'], str) or not isinstance(t['replacement_sha256'], str):
                raise ValueError('replacement path/hash must be strings')  # noqa: TRY004 - all invalid external plans fail as ValueError
            replacement = regular(t['replacement'])
            if output == replacement or output in replacement.parents:
                raise ValueError('overlapping replacement/output')
            if replacement.stat().st_size > (DEFAULTS | limits)['max_archive']:
                raise ValueError('replacement size budget exceeded')
            dest = replacements / f'{index}.jar'
            shutil.copyfile(replacement, dest)
            if digest(dest) != t['replacement_sha256']:
                raise ValueError('replacement hash mismatch')
            if t['replacement_sha256'] == r['sha256']:
                raise ValueError('no-op replacement is forbidden')
            inventory(replacements, **limits)  # validates stock signatures/resources without editing
            selected[key] = r
            checked.append(t | {'replacement': str(dest)})
        selected_hashes = {r['sha256'] for r in selected.values()}
        if any(r['sha256'] in BLOCKED_INPUTS | selected_hashes for r in inventory(replacements, **limits)):
            raise ValueError('replacement contains blocked or selected old archive')
        for key, r in bykey.items():
            if r['sha256'] in selected_hashes and key not in selected:
                raise ValueError('selected leaf hash has unmapped occurrences')
        for key in selected:
            outer, members = key
            for n in range(len(members)):
                ancestor = (outer, members[:n])
                if ancestor in selected:
                    raise ValueError('overlapping ancestor/leaf targets')
                if bykey[ancestor]['signed']:
                    raise ValueError('refusing modification inside signed enclosing archive')
        if not apply:
            return {'mode': 'dry-run', 'inventory_sha256': inventory_hash(inv), 'targets': len(checked)}
        result = staging / 'result'
        result.mkdir()
        for outer in sorted({t['outer'] for t in checked}):
            dest = result / outer
            dest.parent.mkdir(parents=True, exist_ok=True)
            rewrite(snapshot / outer, dest, [t for t in checked if t['outer'] == outer])
        after = inventory(result, **limits)
        for outer in sorted({t['outer'] for t in checked}):
            verify_rewrite(snapshot / outer, result / outer, [t for t in checked if t['outer'] == outer])
        post = {(r['outer'], tuple(r['members'])): r for r in after}
        if any(r['sha256'] in selected_hashes for r in after):
            raise ValueError('selected old archive survives output')
        for t in checked:
            if post[(t['outer'], tuple(t['members']))]['sha256'] != t['replacement_sha256']:
                raise ValueError('post-write leaf verification failed')
        # Linux renameat2 NOREPLACE prevents concurrent output clobber.
        import ctypes
        libc = ctypes.CDLL(None, use_errno=True)
        if libc.renameat2(-100, os.fsencode(result), -100, os.fsencode(output), 1):
            raise OSError(ctypes.get_errno(), 'atomic no-replace output publication failed')
        return {'mode': 'applied', 'inventory_sha256': inventory_hash(inv), 'targets': len(checked)}


def main():
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2, 512 * 1024**2))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--plan', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--apply', action='store_true')
    for key, default in DEFAULTS.items():
        parser.add_argument('--' + key.replace('_', '-'), type=int, default=default)
    args = parser.parse_args()
    limits = {k: getattr(args, k) for k in DEFAULTS}
    try:
        if args.plan:
            if not args.output:
                parser.error('--plan requires --output')
            # Reject duplicate JSON keys as well as unknown plan fields.
            def pairs(items):
                d = {}
                for k, v in items:
                    if k in d: raise ValueError(f'duplicate JSON key: {k}')
                    d[k] = v
                return d
            plan = json.loads(regular(args.plan).read_text(), object_pairs_hook=pairs)
            result = patch(args.source, args.output, plan, args.apply, **limits)
        else:
            if args.apply or args.output:
                parser.error('--apply/--output requires --plan')
            rows = inventory(args.source, **limits)
            result = {'schema': 1, 'inventory_sha256': inventory_hash(rows), 'occurrences': rows}
        print(json.dumps(result, sort_keys=True, indent=2))
    except (ValueError, OSError, MemoryError, zipfile.BadZipFile) as e:
        parser.exit(1, f'FAIL CLOSED: {type(e).__name__}: {e}\n')


if __name__ == '__main__':
    main()
