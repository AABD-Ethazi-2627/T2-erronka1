import hashlib
import json
import tarfile
from pathlib import Path

root = Path(__file__).resolve().parent

def entries(path, strip):
    with tarfile.open(path) as archive:
        result = {}
        for member in archive:
            name = member.name.split('/', 1)[1] if strip and '/' in member.name else member.name
            if member.isdir():
                continue
            data = archive.extractfile(member).read() if member.isfile() else member.linkname.encode()
            result[name] = (member.type.decode(), member.mode, hashlib.sha256(data).hexdigest())
        return result

downloaded = entries(root / 'uv-tag.tar.gz', True)
git = entries(root / 'uv-git.tar', False)
assert downloaded == git, sorted(set(downloaded) ^ set(git))
digest = hashlib.sha256((root / 'uv-tag.tar.gz').read_bytes()).hexdigest()
assert digest == 'c2e01687fbbcb109277698ec97baca46e1547656ad580abf6d993f9c459af1c7'
print(json.dumps({'tag': '0.13.6', 'commit': '329bf9448afd9f9088d14a4d57fbc61eb454f117', 'archive_sha256': digest, 'matching_entries': len(git), 'verified': True}, indent=2))
