"""Portable guards for component preparation; no network, Java or services."""
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

HERE=Path(__file__).resolve().parents[1]/'deploy/images/nifi-patches/jackson'
spec=importlib.util.spec_from_file_location('cnc_jackson_candidate',HERE/'verify.py')
v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)

class JacksonCandidateTests(unittest.TestCase):
    def setUp(self): self.pins=json.loads((HERE/'pins.json').read_text())
    def test_official_pins_and_family_annotations(self):
        v.validate_pins(self.pins)
        annotations=[p['coordinate'] for p in self.pins if 'annotations' in p['file']]
        self.assertTrue(all(x.startswith('com.fasterxml.jackson.core:') for x in annotations))
    def test_untrusted_mirror_rejected(self):
        self.pins[0]['url']=self.pins[0]['url'].replace('repo.maven.apache.org','evil.example')
        with self.assertRaisesRegex(ValueError,'untrusted URL'):v.validate_pins(self.pins)
    def test_duplicate_and_empty_pins_rejected(self):
        for pins in [[], self.pins+[self.pins[0]]]:
            with self.assertRaises(ValueError):v.validate_pins(pins)
    def test_filename_path_injection_rejected(self):
        self.pins[0]['file']='../../outside.jar'
        with self.assertRaises(ValueError):v.validate_pins(self.pins)
    def test_shaded_wrapper_never_gets_plain_replacement(self):
        objects=[{'package':'tools.jackson.core:jackson-core','version':'3.1.2','object_paths':['nested/'+('a'*64)+'.jar']}]
        result=v.classify(objects,[{'sha256':'a'*64,'outer':'hazelcast.jar','members':[]}],self.pins)
        self.assertIsNone(result[0]['replacement'])
        self.assertFalse(result[0]['upstream_old_equal'])
    def test_absent_occurrence_fails_closed(self):
        objects=[{'package':'tools.jackson.core:jackson-core','version':'3.1.2','object_paths':['a.jar']}]
        with self.assertRaisesRegex(ValueError,'absent'):v.classify(objects,[],self.pins)
    def test_stock_equality_and_candidate_remain_same_major_minor(self):
        for old,new in v.PAIRS:
            g='com.fasterxml.jackson.core' if old.startswith('2') else 'tools.jackson.core'
            pin=next(p for p in self.pins if p['coordinate']==g+':jackson-core:'+old and p['file'].endswith(old+'.jar'))
            objects=[{'package':g+':jackson-core','version':old,'object_paths':['nested/'+pin['sha256']+'.jar']}]
            result=v.classify(objects,[{'sha256':pin['sha256'],'outer':'stock.jar','members':[]}],self.pins)[0]
            self.assertEqual(result['replacement']['coordinate'],g+':jackson-core:'+new)
            self.assertEqual(old.split('.')[:2],new.split('.')[:2])
    def test_changed_and_linked_artifact_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'jar';p.write_bytes(b'altered')
            with self.assertRaisesRegex(ValueError,'integrity'):v.checked(p,v.sha(b'original'))
            q=Path(t)/'link';q.symlink_to(p)
            with self.assertRaisesRegex(ValueError,'linked'):v.checked(q,v.sha(b'altered'))
    def test_archive_chain_integrity_and_ambiguity(self):
        with tempfile.TemporaryDirectory() as t:
            b=io.BytesIO()
            with zipfile.ZipFile(b,'w') as z:z.writestr('lib.jar',b'stock')
            data=b.getvalue();Path(t,'outer.nar').write_bytes(data)
            o={'outer':'outer.nar','outer_sha256':v.sha(data),'members':['lib.jar'],'chain_sha256':[v.sha(data),v.sha(b'stock')],'sha256':v.sha(b'stock')}
            self.assertEqual(v.extract(Path(t),o),b'stock')
            o['chain_sha256'][1]=v.sha(b'changed')
            with self.assertRaisesRegex(ValueError,'nested chain'):v.extract(Path(t),o)
            o['chain_sha256']=[]
            with self.assertRaisesRegex(ValueError,'chain length'):v.extract(Path(t),o)
    def test_bounded_model_namespace_and_tamper_guards(self):
        helper,model=v.support_modules()
        with self.assertRaisesRegex(ValueError,'truncated'):helper.class_api(b'\xca\xfe\xba\xbe')
        import xml.etree.ElementTree as E
        for xml in ['<project/>','<project xmlns="urn:evil"/>','<project xmlns="http://maven.apache.org/POM/4.0.0"><dependencies xmlns=""/></project>']:
            with self.assertRaises(ValueError):model.model_namespace(E.fromstring(xml))

if __name__=='__main__':unittest.main()
