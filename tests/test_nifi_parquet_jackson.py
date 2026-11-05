"""Portable guards; no Java, network, build, service or stock modification."""
import importlib.util
import io
import json
import struct
import sys
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parents[1]/'deploy/images/nifi-patches/parquet-jackson'

def load(name, file):
    spec=importlib.util.spec_from_file_location(name,HERE/file)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

# Keep sibling candidate modules isolated when parent discovery imports both.
with mock.patch.dict(sys.modules):
    bounded=load('parquet_bounded','bounded.py');sys.modules['bounded']=bounded
    m=load('parquet_prepare','prepare.py');sys.modules['prepare']=m
    linkage=load('parquet_linkage','linkage.py')

class ParquetGuards(unittest.TestCase):
    def jar(self, extra=None):
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED) as z:
            z.comment=b'acquired-comment'
            z.writestr('META-INF/MANIFEST.MF',b'Manifest-Version: 1.0\r\n')
            z.writestr('META-INF/services/unrelated',b'provider\n')
            z.writestr('META-INF/LICENSE',b'license')
            z.writestr('native/lib.so',b'opaque-native-never-executed')
            z.writestr('old.class',b'old')
            if extra:z.writestr(*extra)
        return out.getvalue()
    def rebuild(self, b):
        return m.assemble(b,{'old.class'},{'new.class':b'fixed'},{'runtime_approved':False})
    def test_raw_and_central_preservation_with_utf8_ascii_and_zero_attrs(self):
        b=bytearray(self.jar());pos=0
        for sig,offset in [(b'PK\x03\x04',6),(b'PK\x01\x02',8)]:
            pos=0
            while (pos:=b.find(sig,pos))>=0:
                flags=struct.unpack_from('<H',b,pos+offset)[0]
                struct.pack_into('<H',b,pos+offset,flags|0x800)
                if sig==b'PK\x01\x02':struct.pack_into('<I',b,pos+38,0)
                pos+=4
        new=self.rebuild(bytes(b))
        with zipfile.ZipFile(io.BytesIO(new)) as z:
            self.assertEqual(z.comment,b'acquired-comment')
            self.assertEqual(z.read('native/lib.so'),b'opaque-native-never-executed')
            self.assertEqual(z.read('META-INF/services/unrelated'),b'provider\n')
            self.assertEqual(z.getinfo('META-INF/LICENSE').external_attr,0)
            self.assertEqual(z.getinfo('META-INF/LICENSE').flag_bits,0x800)
            self.assertNotIn('old.class',z.namelist())
            self.assertFalse(json.loads(z.read(m.PROVENANCE))['runtime_approved'])
    def test_rejects_signed_targets(self):
        for suffix in ('SF','RSA','DSA','EC'):
            with self.subTest(suffix=suffix),self.assertRaisesRegex(ValueError,'signed'):
                self.rebuild(self.jar(('META-INF/key.'+suffix,b'signature')))
    def test_rejects_digest_manifest(self):
        b=io.BytesIO()
        with zipfile.ZipFile(b,'w') as z:
            z.writestr('META-INF/MANIFEST.MF',b'Manifest-Version: 1.0\r\nSHA-256-Digest: x\r\n')
            z.writestr('old.class',b'old')
        with self.assertRaisesRegex(ValueError,'signatures'):self.rebuild(b.getvalue())
    def test_rejects_duplicates(self):
        with warnings.catch_warnings():
            warnings.simplefilter('ignore',UserWarning);b=self.jar(('old.class',b'duplicate'))
        with self.assertRaisesRegex(ValueError,'ambiguous'):self.rebuild(b)
    def test_rejects_collision_and_noop(self):
        with self.assertRaisesRegex(ValueError,'collision'):
            m.assemble(self.jar(),{'old.class'},{'META-INF/LICENSE':b'changed'}, {})
        with self.assertRaisesRegex(ValueError,'no-op'):
            m.assemble(self.jar(),{'old.class'},{'old.class':b'old'}, {})
    def test_rejects_empty_missing_and_repeated_selection(self):
        for selected,replacement in [(set(),{'new':b'new'}),({'missing'},{'new':b'new'}),({'old.class'},{})]:
            with self.subTest(selected=selected),self.assertRaisesRegex(ValueError,'selected'):
                m.assemble(self.jar(),selected,replacement,{})
        with self.assertRaisesRegex(ValueError,'already patched'):self.rebuild(self.jar((m.PROVENANCE,b'{}')))
    def test_pin_guards(self):
        pin={'file':'safe.jar','sha256':'a'*64,'url':'https://repo.maven.apache.org/maven2/safe.jar'}
        m.validate_pins([pin])
        for mutation in [{'file':'../outside.jar'},{'file':'/outside.jar'},{'file':'..'},{'sha256':'bad'},{'url':'https://attacker.invalid/a.jar'}]:
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):m.validate_pins([pin|mutation])
        with self.assertRaisesRegex(ValueError,'duplicate'):m.validate_pins([pin,pin])
    def test_input_drift_missing_and_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'input';p.write_bytes(b'good');m.checked(p,m.sha(b'good'))
            with self.assertRaisesRegex(ValueError,'drift'):m.checked(p,m.sha(b'bad'))
            p.rename(Path(d)/'real');p.symlink_to(Path(d)/'real')
            with self.assertRaisesRegex(ValueError,'linked'):m.checked(p,m.sha(b'good'))
            with self.assertRaisesRegex(ValueError,'missing'):m.checked(Path(d)/'absent','0'*64)
    def test_all_roots_include_unselected_same_count_drift(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'selected').write_bytes(b'one');(root/'unselected').write_bytes(b'two')
            expected={'selected':m.sha(b'one'),'unselected':m.sha(b'two')}
            self.assertEqual(m.source_snapshot(root,expected),expected)
            (root/'unselected').write_bytes(b'DRIFT')
            with self.assertRaisesRegex(ValueError,'drift'):m.source_snapshot(root,expected)
    def test_source_missing_extra_and_linked_roots(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);expected={'one':m.sha(b'one')}
            with self.assertRaisesRegex(ValueError,'drift'):m.source_snapshot(root,expected)
            (root/'one').write_bytes(b'one');(root/'extra').write_bytes(b'extra')
            with self.assertRaisesRegex(ValueError,'drift'):m.source_snapshot(root,expected)
            (root/'extra').unlink();(root/'one').rename(root/'real');(root/'one').symlink_to(root/'real')
            with self.assertRaisesRegex(ValueError,'linked'):m.source_snapshot(root,expected)
    def test_baseline_rejects_wrong_missing_and_unmapped_code(self):
        payload={'shaded/parquet/com/fasterxml/jackson/A.class':b'actual'}
        m.check_baseline(payload,payload)
        for original in [{}, {next(iter(payload)):b'wrong'},payload|{'shaded/parquet/com/fasterxml/jackson/Extra.class':b'extra'}]:
            with self.subTest(original=original),self.assertRaises(ValueError):m.check_baseline(original,payload)
    def test_publication_never_overwrites(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'candidate';m.publish(p,b'first')
            with self.assertRaises(FileExistsError):m.publish(p,b'second')
            self.assertEqual(p.read_bytes(),b'first')
    def test_existing_output_and_shared_m2_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            with self.assertRaisesRegex(ValueError,'fresh'):m.fresh_output(root,[])
            with self.assertRaisesRegex(ValueError,'fresh'):m.fresh_output(root/'child',[root])
            with self.assertRaisesRegex(ValueError,'fresh'):m.fresh_output(root/'.m2'/'child',[])
    def test_constant_pool_and_access_surface(self):
        def utf(v):
            b=v.encode();return b'\x01'+struct.pack('>H',len(b))+b
        cp=[utf('C'),b'\x07\x00\x01',utf('owner'),b'\x07\x00\x03',utf('field'),utf('I'),b'\x0c\x00\x05\x00\x06',b'\x09\x00\x04\x00\x07']
        b=struct.pack('>IHHH',0xcafebabe,0,61,len(cp)+1)+b''.join(cp)
        b+=struct.pack('>HHHHH',1,2,0,0,1)+struct.pack('>HHHH',0x19,5,6,0)+b'\x00\x00'
        name,members,refs,surface=linkage.parse(b,True)
        self.assertEqual(name,'C');self.assertEqual(surface['members'][('field','field','I')],0x19)
        self.assertIn(('owner','field','I','field'),refs)
        self.assertIn(('C','field','I','field'),members)
    def test_launcher_uses_one_finite_flock_and_minimal_environment(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as d, mock.patch.object(bounded.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout=b'ok',stderr=b'')) as invoke:
            log=Path(d)/'run.log'
            bounded.run([bounded.JDK/'bin/java',*bounded.FLAGS,'-version'],log)
            command=invoke.call_args.args[0];kw=invoke.call_args.kwargs
            self.assertEqual(command[:4],['/usr/bin/flock','--no-fork','--timeout','10'])
            self.assertEqual(command.count(bounded.LOCK),1)
            self.assertIn('-Xmx256m',command);self.assertIn('-XX:MaxDirectMemorySize=32m',command)
            self.assertEqual(kw['timeout'],40)
            self.assertEqual(set(kw['env']),{'PATH','LANG','LC_ALL','HOME','TMPDIR'})
            self.assertEqual(json.loads(log.with_suffix('.log.json').read_text())['exit'],0)
    def test_launcher_timeout_records_failure(self):
        import subprocess
        with tempfile.TemporaryDirectory() as d, mock.patch.object(bounded.subprocess,'run',side_effect=subprocess.TimeoutExpired(['java'],40,output=b'partial')):
            log=Path(d)/'run.log'
            with self.assertRaisesRegex(RuntimeError,'bounded command failed'):
                bounded.run([bounded.JDK/'bin/java',*bounded.FLAGS,'-version'],log)
            self.assertEqual(json.loads(log.with_suffix('.log.json').read_text())['status'],'wall-timeout')
            self.assertEqual(log.read_bytes(),b'partial')
    def test_linkage_detects_removed_class_reference(self):
        def class_bytes(name,owner):
            def utf(v):
                b=v.encode();return b'\x01'+struct.pack('>H',len(b))+b
            cp=[utf(name),b'\x07\x00\x01',utf(owner),b'\x07\x00\x03']
            return struct.pack('>IHHH',0xcafebabe,0,61,len(cp)+1)+b''.join(cp)+struct.pack('>HHHHHH',1,2,0,0,0,0)
        with tempfile.TemporaryDirectory() as d:
            old,new=Path(d)/'old.jar',Path(d)/'new.jar'
            for path,deleted in [(old,False),(new,True)]:
                with zipfile.ZipFile(path,'w') as z:
                    z.writestr('C.class',class_bytes('C','Owner'))
                    if not deleted:z.writestr('Owner.class',class_bytes('Owner','Owner'))
            result=linkage.analyze(old,new)
            self.assertEqual(result['removed_classes'],['Owner'])
            self.assertTrue(result['direct_references_to_removed_symbols'])
    def test_plan_keeps_all_four_tuples_runtime_blocked(self):
        p=json.loads((HERE/'candidate-plan.json').read_text())
        self.assertIsNone(p['replacement']);self.assertFalse(p['runtime_approved'])
        self.assertEqual(len(p['tuples']),4)
        self.assertEqual(sum(x['local_runtime_discriminating_probe'] for x in p['tuples']),2)
        self.assertTrue(all(not x['closure_approved'] for x in p['tuples']))
        self.assertTrue(all(x['old_code_sha256']!=x['new_code_sha256'] for x in p['tuples']))
    def test_committed_pins_and_support_have_no_ambiguous_names(self):
        pins=json.loads((HERE/'pins.json').read_text())+json.loads((HERE/'consumer-pins.json').read_text())
        m.validate_pins(pins)
        for n,h in json.loads((HERE/'support-lock.json').read_text()).items():m.checked(HERE.parent/n,h)

if __name__=='__main__':unittest.main()
