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
PROTOBUF4_VERSION = '1.1.24-cnc-wire6.5'
DESCRIPTOR_SHA256 = 'c96db5406336ebcc82523c1dfb122721986a1f43c4aaed45a4a4ad6996efacc2'
DESCRIPTOR_LICENSE_SHA256 = '6e5e117324afd944dcf67f36cf329843bc1a92229a8cd9bb573d7a83130fea7d'
LOADER_JAVA = ('serializer-deserializer/src/main/java/com/amazonaws/services/'
               'schemaregistry/utils/apicurio/ProtobufSchemaLoader.java')
OLD_CALL = ('publicImports.build(), types.build(), services.build(), Collections.emptyList(),\n'
            '                options.build());')
NEW_CALL = ('publicImports.build(), Collections.emptyList(), types.build(), services.build(),\n'
            '                Collections.emptyList(), options.build());')
PHP_COMPAT = '''
    // descriptor.proto reserved field 42 after removing php_generic_services.
    // Preserve its wire value across Protobuf3 known fields and Protobuf4 unknown fields.
    private static Boolean legacyPhpGenericServices(FileOptions options) {
        com.google.protobuf.Descriptors.FieldDescriptor field = options.getDescriptorForType().findFieldByNumber(42);
        if (field != null && options.hasField(field)) {
            return (Boolean) options.getField(field);
        }
        List<Long> values = options.getUnknownFields().getField(42).getVarintList();
        return values.isEmpty() ? null : values.get(values.size() - 1) != 0;
    }

    private static FileOptions legacyPhpGenericServicesOption(boolean value) {
        com.google.protobuf.Message.Builder builder = FileOptions.newBuilder();
        com.google.protobuf.Descriptors.FieldDescriptor field = builder.getDescriptorForType().findFieldByNumber(42);
        if (field != null) {
            builder.setField(field, value);
        } else {
            builder.setUnknownFields(com.google.protobuf.UnknownFieldSet.newBuilder()
                    .addField(42, com.google.protobuf.UnknownFieldSet.Field.newBuilder().addVarint(value ? 1 : 0).build())
                    .build());
        }
        return (FileOptions) builder.build();
    }
'''


def protobuf4_compat(data):
    old = 'FileOptions.newBuilder().setPhpGenericServices(phpGenericServices).build()'
    if data.count(old) != 1:
        raise ValueError('unexpected PHP option setter preimage')
    data = data.replace(old, 'legacyPhpGenericServicesOption(phpGenericServices)')
    old = ('if (file.getOptions().hasPhpGenericServices()) {\n'
           '            OptionElement option = new OptionElement(PHP_GENERIC_SERVICES_OPTION, '
           'booleanKind, file.getOptions().getPhpGenericServices(), false);')
    if data.count(old) != 1:
        raise ValueError('unexpected PHP option getter preimage')
    data = data.replace(old, 'Boolean phpGenericServices = legacyPhpGenericServices(file.getOptions());\n'
                        '        if (phpGenericServices != null) {\n'
                        '            OptionElement option = new OptionElement(PHP_GENERIC_SERVICES_OPTION, '
                        'booleanKind, phpGenericServices, false);')
    close = data.rfind('}')
    return data[:close] + PHP_COMPAT + data[close:]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(archive, output, *, protobuf4=False, descriptor_source=None, descriptor_license=None):
    archive, output = Path(archive), Path(output).absolute()
    if archive.is_symlink() or digest(archive) != SOURCE_SHA256:
        raise ValueError('original source archive fingerprint mismatch')
    repository = Path(__file__).resolve().parents[4]
    if output.exists() or output.is_symlink() or repository == output or repository in output.parents:
        raise ValueError('source output must be fresh and outside repository')
    if any(p.is_symlink() for p in output.parents):
        raise ValueError('linked output parent')
    if protobuf4:
        if descriptor_source is None or descriptor_license is None:
            raise ValueError('pinned Protobuf descriptor source and license required')
        descriptor = Path(descriptor_source).read_bytes()
        license_bytes = Path(descriptor_license).read_bytes()
        if (hashlib.sha256(descriptor).hexdigest() != DESCRIPTOR_SHA256
                or hashlib.sha256(license_bytes).hexdigest() != DESCRIPTOR_LICENSE_SHA256):
            raise ValueError('Protobuf descriptor or license fingerprint mismatch')
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
    version = VERSION
    if protobuf4:
        java.write_bytes(protobuf4_compat(java.read_text(encoding='utf-8')).encode())
        version = PROTOBUF4_VERSION
        loader = output / LOADER_JAVA
        anchor = '        return inMemoryFileSystem;'
        data = loader.read_text(encoding='utf-8')
        if data.count(anchor) != 1:
            raise ValueError('unexpected loader preimage')
        data = data.replace(anchor, '''        // Scope legacy option compatibility to this AWS parser's private filesystem.
        try (InputStream descriptor = classLoader.getResourceAsStream("cnc-compat/protobuf4/descriptor.proto")) {
            if (descriptor == null) {
                throw new IOException("AWS compatibility descriptor missing");
            }
            byte[] bytes = CharStreams.toString(new InputStreamReader(descriptor, Charsets.UTF_8)).getBytes(Charsets.UTF_8);
            writeToFakeFileSystem(inMemoryFileSystem, bytes, Path.get("/google/protobuf/descriptor.proto"));
        }
''' + anchor)
        loader.write_bytes(data.encode())
        old = b'  reserved 42;  // removed php_generic_services\n  reserved "php_generic_services";'
        if descriptor.count(old) != 1:
            raise ValueError('unexpected descriptor legacy field preimage')
        descriptor = descriptor.replace(old, b'  optional bool php_generic_services = 42 [default = false];')
        resources = output / 'serializer-deserializer/src/main/resources/cnc-compat/protobuf4'
        resources.mkdir(parents=True)
        (resources / 'descriptor.proto').write_bytes(descriptor)
        (resources / 'LICENSE').write_bytes(license_bytes)
    for pom in output.rglob('pom.xml'):
        data = pom.read_bytes()
        data = data.replace(b'<version>1.1.24</version>', ('<version>' + version + '</version>').encode())
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
              'consumer_version': version, 'wire_version': '6.4.7', 'protobuf4_compat': protobuf4,
              'changed': changed, 'original_files': original,
              'added_files': {p.relative_to(output).as_posix(): digest(p) for p in output.rglob('*')
                              if p.is_file() and p.relative_to(output).as_posix() not in original},
              'runtime_approved': False}
    (output / 'cnc-source-provenance.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-archive', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--protobuf4-compatible', action='store_true')
    parser.add_argument('--descriptor-source', type=Path)
    parser.add_argument('--descriptor-license', type=Path)
    args = parser.parse_args()
    result = prepare(args.source_archive, args.output, protobuf4=args.protobuf4_compatible,
                     descriptor_source=args.descriptor_source, descriptor_license=args.descriptor_license)
    print(json.dumps({k: v for k, v in result.items() if k != 'original_files'}, indent=2))
