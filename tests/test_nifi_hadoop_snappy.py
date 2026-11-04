"""Portable fail-closed guards; Java consumer evidence is a separate bounded run."""
import importlib.util
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parents[1] / 'deploy/images/nifi-patches/hadoop-snappy'
spec = importlib.util.spec_from_file_location('hadoop_snappy_prepare', HERE / 'prepare.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


def jar(entries):
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w') as z:
        z.comment = b'original comment'
        for n, b in entries:
            i = zipfile.ZipInfo(n, (2026, 3, 24, 1, 2, 4))
            i.external_attr = 0o100644 << 16
            i.comment = b'retain'
            z.writestr(i, b)
    return out.getvalue()


class HadoopSnappyGuards(unittest.TestCase):
    def test_signed_ancestors_and_digest_resources_rejected(self):
        for name, value in [('META-INF/X.SF',b'x'),('META-INF/x.rSa',b'x'),
                            ('META-INF/SIG-CUSTOM',b'x'),
                            ('META-INF/MANIFEST.MF',b'Manifest-Version: 1.0\r\nSHA-256-Digest-Manifest-Main-Attributes: abc\r\n'),
                            ('META-INF/MANIFEST.MF',b'Manifest-Version: 1.0\r\n\r\nName: x\r\nSHA-256-Digest: abc\r\n')]:
            with self.subTest(name=name), self.assertRaisesRegex(ValueError,'signed'):
                p.rebuild(jar([(p.CLASS,b'old'),(name,value)]), b'new', {})

    def test_unrelated_content_attributes_and_visible_metadata_preserved(self):
        entries = [(p.CLASS,b'old'),('META-INF/MANIFEST.MF',b'Manifest-Version: 1.0\n'),
                   ('META-INF/maven/org.apache.hadoop/hadoop-common/pom.properties',b'version=3.5.0\n'),
                   ('META-INF/services/codec',b'provider'),('native/lib.so',b'\x00native'),('LICENSE.txt',b'license')]
        original=jar(entries)
        result=p.rebuild(original,b'new',{'approval':False,'kind':'local correction'})
        with zipfile.ZipFile(io.BytesIO(original)) as a, zipfile.ZipFile(io.BytesIO(result)) as b:
            self.assertEqual(b.namelist(),a.namelist()+[p.PROVENANCE])
            self.assertEqual(a.comment,b.comment)
            for n,value in entries:
                self.assertEqual(b.read(n),b'new' if n==p.CLASS else value)
                for attr in ('date_time','external_attr','comment','extra','compress_type'):
                    self.assertEqual(getattr(a.getinfo(n),attr),getattr(b.getinfo(n),attr))
            self.assertFalse(json.loads(b.read(p.PROVENANCE))['approval'])

    def test_wrong_or_already_patched_input(self):
        for entries in [[('other.class',b'x')],[(p.CLASS,b'old'),(p.PROVENANCE,b'{}')]]:
            with self.assertRaisesRegex(ValueError,'wrong|already'):
                p.rebuild(jar(entries),b'new',{})

    def test_duplicate_and_traversal_entries(self):
        for entries in [[(p.CLASS,b'a'),(p.CLASS,b'b')],[(p.CLASS,b'a'),('../bad',b'b')]]:
            with self.assertRaisesRegex(ValueError,'duplicate|unsafe'):
                p.rebuild(jar(entries),b'new',{})

    def test_publication_is_exclusive_and_inputs_regular(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'result.jar'; p.publish(f,b'first')
            with self.assertRaises(FileExistsError): p.publish(f,b'second')
            self.assertEqual(f.read_bytes(),b'first')
            link=Path(d)/'link'; link.symlink_to(f)
            with self.assertRaisesRegex(ValueError,'symlink'): p.regular(link)
            with self.assertRaisesRegex(ValueError,'outside'): p.external_fresh(Path(d)/'nested', [Path(d)])
            with self.assertRaises(FileExistsError): p.external_fresh(Path(d), [])

    def test_source_transform_rejects_missing_or_wrong_preimage(self):
        for text in ['', 'int size = Snappy.compress();', 'compressedDirectBuf.clear();']:
            with self.assertRaisesRegex(ValueError,'preimage'): p.patch_source(text)

    def test_wrong_preimage_hash_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'input.jar'; f.write_bytes(b'wrong bytes')
            with self.assertRaisesRegex(ValueError,'hash mismatch'):
                p.pinned(f,p.HADOOP)
            self.assertEqual(p.pinned(f,p.sha(b'wrong bytes')),b'wrong bytes')

    def test_descriptor_and_raw_unrelated_records_preserved(self):
        class Nonseekable(io.BytesIO):
            def seekable(self): return False
            def seek(self, *args): raise OSError('stream')
        stream=Nonseekable()
        with zipfile.ZipFile(stream,'w') as z:
            z.writestr(p.CLASS,b'old')
            z.writestr('native/lib.so',b'unchanged native bytes')
        original=stream.getvalue()
        result=p.rebuild(original,b'replacement class bytes',{})
        with zipfile.ZipFile(io.BytesIO(original)) as a, zipfile.ZipFile(io.BytesIO(result)) as b:
            for n in (p.CLASS,'native/lib.so'):
                self.assertEqual(a.getinfo(n).flag_bits,b.getinfo(n).flag_bits)
            x=a.getinfo('native/lib.so').header_offset
            y=b.getinfo('native/lib.so').header_offset
            self.assertEqual(original[x:a.start_dir],result[y:b.getinfo(p.PROVENANCE).header_offset])



if __name__ == '__main__':
    unittest.main()
