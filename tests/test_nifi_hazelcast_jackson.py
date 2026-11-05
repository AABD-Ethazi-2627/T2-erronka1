"""Portable publication and integrity controls; no JVM, service or network."""
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest
import zipfile

HERE=Path(__file__).resolve().parents[1]/'deploy/images/nifi-patches/hazelcast-jackson'
sys.path.insert(0,str(HERE))
spec=importlib.util.spec_from_file_location('hazelcast_prepare',HERE/'prepare.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class WrapperIntegrity(unittest.TestCase):
    def jar(self, extra=None):
        b=io.BytesIO()
        with zipfile.ZipFile(b,'w',compression=zipfile.ZIP_DEFLATED) as z:
            z.comment=b'original-comment'
            z.writestr('META-INF/MANIFEST.MF',b'Manifest-Version: 1.0\r\n')
            z.writestr('com/hazelcast/Consumer.class',b'unrelated code')
            z.writestr('META-INF/services/service.Interface',b'provider\n')
            z.writestr('native/lib.so',b'native bytes')
            z.writestr('jackson/Old.class',b'old code')
            if extra:
                z.writestr(*extra)
        return b.getvalue()
    def test_preserves_unrelated_records_and_adds_real_code(self):
        old=self.jar()
        new=m.assemble(old,{'jackson/Old.class'},{'jackson/New.class':b'fixed code'},{'runtime_approved':False})
        with zipfile.ZipFile(io.BytesIO(new)) as z:
            self.assertEqual(z.comment,b'original-comment')
            self.assertEqual(z.read('native/lib.so'),b'native bytes')
            self.assertEqual(z.read('META-INF/services/service.Interface'),b'provider\n')
            self.assertNotIn('jackson/Old.class',z.namelist())
            self.assertEqual(z.read('jackson/New.class'),b'fixed code')
            self.assertFalse(json.loads(z.read(m.PROVENANCE))['runtime_approved'])
    def test_preserves_utf8_flag_on_ascii_names(self):
        import struct
        b=bytearray(self.jar())
        # Stock Hazelcast uses the UTF-8 flag even on ASCII entry names.
        for sig,offset in [(b'PK\x03\x04',6),(b'PK\x01\x02',8)]:
            pos=0
            while (pos:=b.find(sig,pos))>=0:
                flags=struct.unpack_from('<H',b,pos+offset)[0]
                struct.pack_into('<H',b,pos+offset,flags|0x800);pos+=4
        new=m.assemble(bytes(b),{'jackson/Old.class'},{'jackson/New.class':b'new'}, {})
        with zipfile.ZipFile(io.BytesIO(new)) as z:
            self.assertTrue(z.getinfo('com/hazelcast/Consumer.class').flag_bits & 0x800)
    def test_rejects_collision_with_preserved_code(self):
        with self.assertRaisesRegex(ValueError,'collision'):
            m.assemble(self.jar(),{'jackson/Old.class'},{'com/hazelcast/Consumer.class':b'changed'}, {})
    def test_rejects_signed_original(self):
        for suffix in ['SF','RSA','DSA','EC']:
            with self.subTest(suffix=suffix),self.assertRaisesRegex(ValueError,'signed'):
                m.assemble(self.jar(('META-INF/key.'+suffix,b'signature')),{'jackson/Old.class'},{'jackson/New.class':b'new'}, {})
    def test_rejects_ambiguous_original(self):
        with self.assertWarns(UserWarning):
            b=self.jar(('jackson/Old.class',b'other code'))
        with self.assertRaisesRegex(ValueError,'ambiguous'):
            m.assemble(b,{'jackson/Old.class'},{'jackson/New.class':b'new'}, {})
    def test_rejects_repeated_patch(self):
        with self.assertRaisesRegex(ValueError,'already patched'):
            m.assemble(self.jar((m.PROVENANCE,b'{}')),{'jackson/Old.class'},{'jackson/New.class':b'new'}, {})
    def test_rejects_missing_preimage(self):
        with self.assertRaisesRegex(ValueError,'selected'):
            m.assemble(self.jar(),{'missing.class'},{'jackson/New.class':b'new'}, {})
    def test_rejects_empty_replacement(self):
        with self.assertRaisesRegex(ValueError,'selected'):
            m.assemble(self.jar(),{'jackson/Old.class'},{}, {})
    def test_manifest_digest_is_rejected(self):
        b=io.BytesIO()
        with zipfile.ZipFile(b,'w') as z:
            z.writestr('META-INF/MANIFEST.MF',b'Manifest-Version: 1.0\r\nSHA-256-Digest: abc\r\n')
            z.writestr('old',b'code')
        with self.assertRaisesRegex(ValueError,'signatures'):
            m.assemble(b.getvalue(),{'old'},{'new':b'fixed'}, {})
    def test_constant_pool_member_and_class_references(self):
        import struct
        import linkage
        def utf(x):
            b=x.encode();return b'\x01'+struct.pack('>H',len(b))+b
        # Class C with a field reference to removed owner.field:I, and a
        # descriptor reference. No Java compiler or arbitrary execution.
        cp=[utf('C'),b'\x07\x00\x01',utf('owner'),b'\x07\x00\x03',
            utf('field'),utf('I'),b'\x0c\x00\x05\x00\x06',b'\x09\x00\x04\x00\x07',utf('Ldescriptor/Type;')]
        b=struct.pack('>IHHH',0xcafebabe,0,61,len(cp)+1)+b''.join(cp)
        b+=struct.pack('>HHHHHH',1,2,0,0,0,0)
        name,members,refs=linkage.parse(b)
        self.assertEqual(name,'C')
        self.assertIn(('owner','field','I','field'),refs)
        self.assertIn(('owner','','','class'),refs)
        self.assertIn(('descriptor/Type','','','descriptor'),refs)
    def test_plan_retains_runtime_block_and_exact_tuple_universe(self):
        p=json.loads((HERE/'candidate-plan.json').read_text())
        self.assertFalse(p['runtime_approved'])
        self.assertIsNone(p['replacement'])
        self.assertEqual(len(p['tuples']),37)
        self.assertTrue(all(not x['closure_approved'] for x in p['tuples']))
        self.assertEqual(sum(x['evidence'].startswith('bounded') for x in p['tuples']),6)
        self.assertTrue(all('241ec66cea849178' in x['PkgPath'] for x in p['tuples']))
    def test_pins_have_no_ambiguous_names(self):
        pins=json.loads((HERE/'pins.json').read_text())
        self.assertEqual(len(pins),len({x['file'] for x in pins}))
        for x in pins:
            self.assertEqual(Path(x['file']).name,x['file'])
            self.assertRegex(x['sha256'],r'^[0-9a-f]{64}$')
            self.assertTrue(x['url'].startswith(('https://repo.maven.apache.org/maven2/','https://raw.githubusercontent.com/hazelcast/hazelcast/v5.7.0/')))
if __name__=='__main__': unittest.main()
