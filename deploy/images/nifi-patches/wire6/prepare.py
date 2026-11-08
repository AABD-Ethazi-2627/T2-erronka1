"""Rebuild the actual AWS Glue Wire consumer from pinned original upstream source.

No NiFi archive is changed by this tool. All source tests remain in the tree.
The Wire reader itself is the official 6.4.7 release, not a relabelled 5.2 fork.
"""
import argparse
import hashlib
import json
import tarfile
from pathlib import Path, PurePosixPath

SOURCE_COMMIT = 'c6a911301ea8ca72260bed3f2dfda83f3effcba2'
SOURCE_SHA256 = 'acd3b1ae461282698c3a3cb08842a5e6180660d5ad5427d2ab1932f10208bcfc'
SOURCE_URL = 'https://codeload.github.com/awslabs/aws-glue-schema-registry/tar.gz/' + SOURCE_COMMIT
MIGRATION_URL = ('https://raw.githubusercontent.com/awslabs/aws-glue-schema-registry/'
                 'b47e716743c64ec3fb7f4e3e780a32e2f0cff0b5/serializer-deserializer/src/main/'
                 'java/com/amazonaws/services/schemaregistry/utils/apicurio/FileDescriptorUtils.java')
JAVA_PATH = ('serializer-deserializer/src/main/java/com/amazonaws/services/'
             'schemaregistry/utils/apicurio/FileDescriptorUtils.java')
OLD_JAVA_SHA256 = 'b12f70d9892313545f34d4b47bfceee4b71e1389dd90712bbe75f1c4ce4d1f1c'
NEW_JAVA_SHA256 = 'd1c026cc89599c4575ca72ed4a5699373831bfc91fd40fe40940f922e5e0e872'
VERSION = '1.1.24-cnc-wire6.1'
OLD_CALL = ('publicImports.build(), types.build(), services.build(), Collections.emptyList(),\n'
            '                options.build());')
NEW_CALL = ('publicImports.build(), Collections.emptyList(), types.build(), services.build(),\n'
            '                Collections.emptyList(), options.build());')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(archive, output):
    archive, output = Path(archive), Path(output).absolute()
    if archive.is_symlink() or digest(archive) != SOURCE_SHA256:
        raise ValueError('original source archive fingerprint mismatch')
    repository = Path(__file__).resolve().parents[4]
    if output.exists() or output.is_symlink() or repository == output or repository in output.parents:
        raise ValueError('source output must be fresh and outside repository')
    if any(p.is_symlink() for p in output.parents):
        raise ValueError('linked output parent')
    prefix = 'aws-glue-schema-registry-' + SOURCE_COMMIT
    with tarfile.open(archive) as source:
        members = source.getmembers()
        if len(members) > 20000 or sum(m.size for m in members) > 256 * 1024**2:
            raise ValueError('source archive budget exceeded')
        for member in members:
            path = PurePosixPath(member.name)
            if (not path.parts or path.parts[0] != prefix or path.is_absolute()
                    or '..' in path.parts or '\\' in member.name
                    or not (member.isfile() or member.isdir())):
                raise ValueError('unsupported source archive member')
        output.mkdir(parents=True)
        for member in members:
            relative = PurePosixPath(member.name).relative_to(prefix)
            dest = output.joinpath(*relative.parts)
            if member.isdir():
                dest.mkdir(parents=True, exist_ok=True)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                with source.extractfile(member) as src, dest.open('xb') as target:
                    target.write(src.read())
    original = {p.relative_to(output).as_posix(): digest(p) for p in output.rglob('*') if p.is_file()}
    java = output / JAVA_PATH
    if digest(java) != OLD_JAVA_SHA256:
        raise ValueError('unexpected consumer source preimage')
    data = java.read_text(encoding='utf-8')
    if data.count(OLD_CALL) != 1:
        raise ValueError('unexpected Wire constructor occurrence count')
    java.write_bytes(data.replace(OLD_CALL, NEW_CALL).encode())
    if digest(java) != NEW_JAVA_SHA256:
        raise ValueError('consumer migration differs from exact upstream source')
    for pom in output.rglob('pom.xml'):
        data = pom.read_bytes()
        data = data.replace(b'<version>1.1.24</version>', ('<version>' + VERSION + '</version>').encode())
        if pom == output / 'pom.xml':
            for old, new in [(b'<square-wireschema.version>5.2.0', b'<square-wireschema.version>6.4.7'),
                             (b'<kotlin.version>1.9.25', b'<kotlin.version>2.4.20')]:
                if data.count(old) != 1:
                    raise ValueError('unexpected upstream dependency pin')
                data = data.replace(old, new)
        pom.write_bytes(data)
    changed = {name: {'before': sha, 'after': digest(output / name)} for name, sha in original.items()
               if sha != digest(output / name)}
    result = {'source_commit': SOURCE_COMMIT, 'source_sha256': SOURCE_SHA256,
              'source_url': SOURCE_URL, 'migration_url': MIGRATION_URL,
              'consumer_version': VERSION, 'wire_version': '6.4.7',
              'changed': changed, 'original_files': original, 'runtime_approved': False}
    (output / 'cnc-source-provenance.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-archive', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.source_archive, args.output)
    print(json.dumps({k: v for k, v in result.items() if k != 'original_files'}, indent=2))
