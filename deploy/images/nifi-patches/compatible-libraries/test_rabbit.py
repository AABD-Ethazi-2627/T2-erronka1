"""Focused synthetic-model and real downloader rejection regressions (no network)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from maven_closure import Closure
from verify import compare, sha

HERE=Path(__file__).resolve().parent
CACHE=Path(os.environ['RABBIT_CACHE'])
class ModelTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=CACHE);self.cache=Path(self.tmp.name);self.pins=[]
    def tearDown(self):self.tmp.cleanup()
    def pom(self,artifact,body='',version='1'):
        name=f'{artifact}-{version}.pom';(self.cache/name).write_text('<project xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion><groupId>x</groupId><artifactId>'+artifact+'</artifactId><version>'+version+'</version>'+body+'</project>')
        self.pins.extend([{'file':name,'coordinate':f'x:{artifact}:{version}','sha256':sha((self.cache/name).read_bytes())},{'file':f'{artifact}-{version}.jar','coordinate':f'x:{artifact}:{version}'}])
    def resolve(self):return Closure(self.cache,self.pins).resolve('x:root:1')
    def test_inherited_managed_test_scope_is_not_a_runtime_dependency(self):
        self.pom('parent','<dependencyManagement><dependencies><dependency><groupId>x</groupId><artifactId>test-only</artifactId><version>1</version><scope>test</scope></dependency></dependencies></dependencyManagement>')
        self.pom('root','<parent><groupId>x</groupId><artifactId>parent</artifactId><version>1</version></parent><dependencies><dependency><groupId>x</groupId><artifactId>test-only</artifactId></dependency></dependencies>')
        r=self.resolve();self.assertEqual(r['required_coordinates'],['x:root:1']);self.assertTrue(any(d['disposition']=='excluded-test' for d in r['excluded_dependencies']))
    def test_profile_dependency_is_rejected(self):
        self.pom('root','<profiles><profile><id>hidden</id><dependencies><dependency><groupId>x</groupId><artifactId>hidden</artifactId></dependency></dependencies></profile></profiles>')
        with self.assertRaisesRegex(ValueError,'unsupported profile'):self.resolve()
    def test_profile_can_not_change_a_required_version(self):
        self.pom('root','<properties><dep.version>1</dep.version></properties><profiles><profile><id>hidden</id><properties><dep.version>2</dep.version></properties></profile></profiles><dependencies><dependency><groupId>x</groupId><artifactId>child</artifactId><version>${dep.version}</version></dependency></dependencies>')
        with self.assertRaisesRegex(ValueError,'profile-dependent runtime'):self.resolve()
    def test_exclusions_apply_to_transitive_path_not_a_missing_artifact(self):
        self.pom('root','<dependencies><dependency><groupId>x</groupId><artifactId>codec</artifactId><version>1</version><exclusions><exclusion><groupId>x</groupId><artifactId>protobuf</artifactId></exclusion></exclusions></dependency></dependencies>')
        self.pom('codec','<dependencies><dependency><groupId>x</groupId><artifactId>protobuf</artifactId><version>1</version></dependency></dependencies>')
        self.assertEqual(self.resolve()['required_coordinates'],['x:codec:1','x:root:1'])
    def test_managed_optional_dependency_is_recorded_not_required(self):
        self.pom('parent','<dependencyManagement><dependencies><dependency><groupId>x</groupId><artifactId>optional</artifactId><version>1</version><optional>true</optional></dependency></dependencies></dependencyManagement>')
        self.pom('root','<parent><groupId>x</groupId><artifactId>parent</artifactId><version>1</version></parent><dependencies><dependency><groupId>x</groupId><artifactId>optional</artifactId></dependency></dependencies>')
        r=self.resolve();self.assertEqual(r['required_coordinates'],['x:root:1']);self.assertTrue(any(d['disposition']=='excluded-optional' for d in r['excluded_dependencies']))
    def test_two_required_versions_are_not_silently_mediated(self):
        self.pom('root','<dependencies><dependency><groupId>x</groupId><artifactId>leaf</artifactId><version>1</version></dependency><dependency><groupId>x</groupId><artifactId>other</artifactId><version>1</version></dependency></dependencies>')
        self.pom('leaf');self.pom('leaf',version='2')
        self.pom('other','<dependencies><dependency><groupId>x</groupId><artifactId>leaf</artifactId><version>2</version></dependency></dependencies>')
        with self.assertRaisesRegex(ValueError,'version conflict'):self.resolve()
    def test_unknown_required_pom_is_rejected(self):
        self.pom('root','<dependencies><dependency><groupId>x</groupId><artifactId>missing</artifactId><version>1</version></dependency></dependencies>')
        with self.assertRaisesRegex(ValueError,'unpinned POM'):self.resolve()
    def test_unknown_imported_bom_is_rejected(self):
        self.pom('root','<dependencyManagement><dependencies><dependency><groupId>x</groupId><artifactId>missing</artifactId><version>1</version><type>pom</type><scope>import</scope></dependency></dependencies></dependencyManagement>')
        with self.assertRaisesRegex(ValueError,'unpinned POM'):self.resolve()
    def test_required_classifier_is_rejected(self):
        self.pom('root','<dependencies><dependency><groupId>x</groupId><artifactId>native</artifactId><version>1</version><classifier>unknown</classifier></dependency></dependencies>')
        with self.assertRaisesRegex(ValueError,'type/classifier'):self.resolve()
    def test_unresolved_version_is_rejected(self):
        self.pom('root','<dependencies><dependency><groupId>x</groupId><artifactId>missing</artifactId><version>${unknown}</version></dependency></dependencies>')
        with self.assertRaisesRegex(ValueError,'unresolved POM'):self.resolve()
    def test_resource_only_aggregate_has_no_class_major(self):
        import zipfile
        for n in ['old.jar','new.jar']:
            with zipfile.ZipFile(self.cache/n,'w') as z:z.writestr('META-INF/MANIFEST.MF','Manifest-Version: 1.0\n')
        r=compare(self.cache/'old.jar',self.cache/'new.jar');self.assertEqual(r['public_classes'],0);self.assertIsNone(r['candidate_max_base_class_major'])

class DownloaderTests(unittest.TestCase):
    def invoke(self,cache):
        env=os.environ|{'PYTHONDONTWRITEBYTECODE':'1'}
        return subprocess.run([sys.executable,'-O',str(HERE/'verify_rabbit.py'),'--cache',str(cache),'--offline'],capture_output=True,check=False,text=True,timeout=15,env=env)
    def test_missing_input_has_no_success_proof(self):
        with tempfile.TemporaryDirectory(dir=CACHE) as d:
            p=self.invoke(d);self.assertNotEqual(p.returncode,0);self.assertIn('missing offline input',p.stderr);self.assertFalse(list(Path(d).rglob('rabbit-transport-result.json')))
    def test_tampered_netty_parent_has_no_success_proof(self):
        with tempfile.TemporaryDirectory(dir=CACHE) as d:
            first=json.loads((HERE/'rabbit-pins.json').read_text())[0]['file']
            (Path(d)/first).write_text('tampered POM')
            p=self.invoke(d);self.assertNotEqual(p.returncode,0);self.assertIn('input integrity',p.stderr);self.assertFalse(list(Path(d).rglob('rabbit-transport-result.json')))
if __name__=='__main__':unittest.main()
