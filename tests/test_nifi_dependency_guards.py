"""Portable regressions for dependency-model and readiness guards; no JDK/network."""

import hashlib
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / 'deploy/images/nifi-patches/compatible-libraries'


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, COMPONENT / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DependencyGuardTests(unittest.TestCase):
    def setUp(self):
        self.verify = load('_cnc_component_verify', 'verify.py')
        with patch.dict(sys.modules, {'verify': self.verify}):
            self.model = load('_cnc_component_model', 'maven_closure.py')
        self.imports = patch.dict(sys.modules, {
            'verify': self.verify, 'maven_closure': self.model,
        })
        self.imports.start()
        self.addCleanup(self.imports.stop)
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.cache = Path(self.temporary.name)
        self.pins = []

    def pom(self, name, body='', namespace='http://maven.apache.org/POM/4.0.0', version='1'):
        file = name + '-' + version + '.pom'
        ns = f' xmlns="{namespace}"' if namespace else ''
        data = (f'<project{ns}><modelVersion>4.0.0</modelVersion>'
                f'<groupId>x</groupId><artifactId>{name}</artifactId><version>{version}</version>'
                f'{body}</project>').encode()
        (self.cache / file).write_bytes(data)
        self.pins.append({'file': file, 'coordinate': f'x:{name}:{version}',
                          'sha256': hashlib.sha256(data).hexdigest()})
        self.pins.append({'file': name + '-' + version + '.jar', 'coordinate': f'x:{name}:{version}'})

    def deps(self):
        return self.verify.deps(self.cache, 'root-1.pom', self.pins)

    def test_namespace_free_and_foreign_poms_fail(self):
        for namespace in ('', 'urn:wrong'):
            with self.subTest(namespace=namespace):
                self.pins = []
                self.pom('root', namespace=namespace)
                with self.assertRaisesRegex(ValueError, 'namespace'):
                    self.deps()

    def test_namespace_reset_cannot_hide_dependencies(self):
        self.pom('root', '<dependencies xmlns=""><dependency><groupId>x</groupId>'
                 '<artifactId>hidden</artifactId><version>1</version></dependency></dependencies>')
        with self.assertRaisesRegex(ValueError, 'namespace'):
            self.deps()

    def test_present_unpinned_parent_is_rejected(self):
        self.pom('parent')
        self.pom('root', '<parent><groupId>x</groupId><artifactId>parent</artifactId>'
                 '<version>1</version></parent>')
        self.pins = [pin for pin in self.pins if pin['file'] != 'parent-1.pom']
        with self.assertRaisesRegex(ValueError, 'unpinned POM'):
            self.deps()

    def test_changed_pinned_parent_is_rejected(self):
        self.pom('parent')
        self.pom('root', '<parent><groupId>x</groupId><artifactId>parent</artifactId>'
                 '<version>1</version></parent>')
        with (self.cache / 'parent-1.pom').open('ab') as out:
            out.write(b'<!-- drift -->')
        with self.assertRaisesRegex(ValueError, 'POM integrity'):
            self.deps()

    def test_pom_coordinate_must_match_the_pinned_identity(self):
        self.pom('root')
        self.pins[0]['coordinate'] = 'y:root:1'
        with self.assertRaisesRegex(ValueError, 'coordinate mismatch'):
            self.deps()

    def test_grandparent_dependency_is_not_omitted(self):
        self.pom('grand', '<dependencies><dependency><groupId>x</groupId><artifactId>leaf'
                 '</artifactId><version>1</version></dependency></dependencies>')
        self.pom('parent', '<parent><groupId>x</groupId><artifactId>grand</artifactId>'
                 '<version>1</version></parent>')
        self.pom('root', '<parent><groupId>x</groupId><artifactId>parent</artifactId>'
                 '<version>1</version></parent>')
        self.assertEqual(self.deps(), ['x:leaf:1'])

    def test_missing_grandparent_is_rejected(self):
        self.pom('parent', '<parent><groupId>x</groupId><artifactId>missing</artifactId>'
                 '<version>1</version></parent>')
        self.pom('root', '<parent><groupId>x</groupId><artifactId>parent</artifactId>'
                 '<version>1</version></parent>')
        with self.assertRaisesRegex(ValueError, 'unpinned POM'):
            self.deps()

    def test_ancestor_profile_dependency_is_rejected(self):
        self.pom('parent', '<profiles><profile><id>hidden</id><activation><activeByDefault>'
                 'true</activeByDefault></activation><dependencies><dependency><groupId>x'
                 '</groupId><artifactId>hidden</artifactId><version>1</version></dependency>'
                 '</dependencies></profile></profiles>')
        self.pom('root', '<parent><groupId>x</groupId><artifactId>parent</artifactId>'
                 '<version>1</version></parent>')
        with self.assertRaisesRegex(ValueError, 'profile dependency'):
            self.deps()

    def test_classifier_and_nonjar_type_are_not_reduced_to_plain_coordinates(self):
        for extra in ('<classifier>native</classifier>', '<type>pom</type>'):
            with self.subTest(extra=extra):
                self.pins = []
                self.pom('root', '<dependencies><dependency><groupId>x</groupId>'
                         '<artifactId>leaf</artifactId><version>1</version>' + extra +
                         '</dependency></dependencies>')
                with self.assertRaisesRegex(ValueError, 'type/classifier'):
                    self.deps()

    def test_jar_pin_alone_does_not_prove_transitive_closure(self):
        pins = [{'file': 'leaf-1.jar', 'coordinate': 'x:leaf:1'}]
        self.assertEqual(self.verify.missing_closure(['x:leaf:1'], pins), ['x:leaf:1'])

    def test_wildcard_exclusions_keep_the_dependency_declaring_them(self):
        for group,artifact in (('*','*'),('x','*'),('*','leaf')):
            with self.subTest(group=group,artifact=artifact):
                self.pins=[]
                self.pom('mid','<dependencies><dependency><groupId>x</groupId><artifactId>leaf</artifactId>'
                         '<version>1</version></dependency></dependencies>')
                self.pom('root','<dependencies><dependency><groupId>x</groupId><artifactId>mid</artifactId>'
                         '<version>1</version><exclusions><exclusion><groupId>'+group+'</groupId>'
                         '<artifactId>'+artifact+'</artifactId></exclusion></exclusions></dependency></dependencies>')
                result=self.model.Closure(self.cache,self.pins).resolve('x:root:1')
                self.assertEqual(result['required_coordinates'],['x:mid:1','x:root:1'])
                self.assertTrue(next(e for e in result['edges'] if e['to']=='x:leaf:1')['excluded_by_path'])

    def test_self_exclusion_does_not_remove_the_declaring_dependency(self):
        self.pom('mid')
        self.pom('root','<dependencies><dependency><groupId>x</groupId><artifactId>mid</artifactId>'
                 '<version>1</version><exclusions><exclusion><groupId>x</groupId><artifactId>mid'
                 '</artifactId></exclusion></exclusions></dependency></dependencies>')
        self.assertEqual(self.model.Closure(self.cache,self.pins).resolve('x:root:1')['required_coordinates'],
                         ['x:mid:1','x:root:1'])

    def test_managed_optional_does_not_hide_a_required_artifact(self):
        self.pom('leaf')
        self.pom('parent','<dependencyManagement><dependencies><dependency><groupId>x</groupId>'
                 '<artifactId>leaf</artifactId><version>1</version><optional>true</optional>'
                 '</dependency></dependencies></dependencyManagement>')
        self.pom('root','<parent><groupId>x</groupId><artifactId>parent</artifactId><version>1</version>'
                 '</parent><dependencies><dependency><groupId>x</groupId><artifactId>leaf</artifactId>'
                 '</dependency></dependencies>')
        self.assertEqual(self.model.Closure(self.cache,self.pins).resolve('x:root:1')['required_coordinates'],
                         ['x:leaf:1','x:root:1'])

    def test_bom_owned_interpolation_cannot_use_consumer_properties(self):
        self.pom('bom','<packaging>pom</packaging><dependencyManagement><dependencies><dependency>'
                 '<groupId>x</groupId><artifactId>leaf</artifactId><version>${project.version}</version>'
                 '</dependency></dependencies></dependencyManagement>',version='2')
        self.pom('root','<dependencyManagement><dependencies><dependency><groupId>x</groupId><artifactId>bom'
                 '</artifactId><version>2</version><type>pom</type><scope>import</scope></dependency>'
                 '</dependencies></dependencyManagement><dependencies><dependency><groupId>x</groupId>'
                 '<artifactId>leaf</artifactId></dependency></dependencies>')
        with self.assertRaisesRegex(ValueError,'interpolated BOM'):
            self.deps()

    def test_child_management_of_inherited_dependency_fails_closed(self):
        for managed in ('<version>2</version>','<version>1</version><scope>test</scope>'):
            with self.subTest(managed=managed):
                self.pins=[]
                self.pom('parent','<dependencies><dependency><groupId>x</groupId><artifactId>leaf</artifactId>'
                         '<version>1</version></dependency></dependencies>')
                self.pom('root','<parent><groupId>x</groupId><artifactId>parent</artifactId><version>1</version>'
                         '</parent><dependencyManagement><dependencies><dependency><groupId>x</groupId>'
                         '<artifactId>leaf</artifactId>'+managed+'</dependency></dependencies></dependencyManagement>')
                with self.assertRaisesRegex(ValueError,'inherited dependency management'):
                    self.deps()

    def test_managed_and_local_exclusions_do_not_silently_union(self):
        self.pom('root','<dependencyManagement><dependencies><dependency><groupId>x</groupId><artifactId>mid'
                 '</artifactId><version>1</version><exclusions><exclusion><groupId>x</groupId><artifactId>a'
                 '</artifactId></exclusion></exclusions></dependency></dependencies></dependencyManagement>'
                 '<dependencies><dependency><groupId>x</groupId><artifactId>mid</artifactId><exclusions><exclusion>'
                 '<groupId>x</groupId><artifactId>b</artifactId></exclusion></exclusions></dependency></dependencies>')
        with self.assertRaisesRegex(ValueError,'managed/local exclusion'):
            self.deps()

    def test_distribution_relocation_is_not_silently_ignored(self):
        for own_dependencies in ('', '<dependencies><dependency><groupId>x</groupId>'
                                 '<artifactId>old</artifactId><version>1</version>'
                                 '</dependency></dependencies>'):
            with self.subTest(own_dependencies=own_dependencies):
                self.pins=[]
                self.pom('root','<distributionManagement><relocation><artifactId>new'
                         '</artifactId></relocation></distributionManagement>'+own_dependencies)
                with self.assertRaisesRegex(ValueError,'relocation'):
                    self.deps()

    def test_child_management_exclusions_on_inherited_dependency_are_rejected(self):
        self.pom('parent','<dependencies><dependency><groupId>x</groupId><artifactId>mid'
                 '</artifactId><version>1</version></dependency></dependencies>')
        self.pom('root','<parent><groupId>x</groupId><artifactId>parent</artifactId><version>1'
                 '</version></parent><dependencyManagement><dependencies><dependency><groupId>x'
                 '</groupId><artifactId>mid</artifactId><version>1</version><exclusions><exclusion>'
                 '<groupId>x</groupId><artifactId>leaf</artifactId></exclusion></exclusions>'
                 '</dependency></dependencies></dependencyManagement>')
        with self.assertRaisesRegex(ValueError,'inherited dependency management'):
            self.deps()

    def test_profile_dependent_exclusion_selector_is_rejected_before_expansion(self):
        self.pom('root','<properties><ex>a</ex><alias>${ex}</alias></properties>'
                 '<profiles><profile><id>active</id><activation><activeByDefault>true'
                 '</activeByDefault></activation><properties><ex>b</ex></properties></profile>'
                 '</profiles><dependencies><dependency><groupId>x</groupId><artifactId>mid'
                 '</artifactId><version>1</version><exclusions><exclusion><groupId>x</groupId>'
                 '<artifactId>${alias}</artifactId></exclusion></exclusions></dependency></dependencies>')
        with self.assertRaisesRegex(ValueError,'profile-dependent runtime selector'):
            self.deps()

    def test_parser_verifier_never_grants_rabbit_transport_readiness(self):
        api = {'removed_or_changed': [], 'missing_native_paths': []}
        entry = {'input_matches_tested_upstream': True}
        self.assertEqual(self.verify.candidate_status('rabbit', entry, [], api),
                         'blocked-compatibility')

    def test_all_java_launches_share_an_allowlisted_environment(self):
        with patch.dict(os.environ,{'LD_AUDIT':'not-real','JAVA_TOOL_OPTIONS':'injection','JDK_AOT_VM_OPTIONS':'injection'}):
            env=self.verify.clean_environment()
            self.assertLessEqual(set(env),{'PATH','LANG','LC_ALL','TMPDIR'})
            self.assertNotIn('LD_AUDIT',env)

    def test_truncated_classfile_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'truncated classfile'):
            self.verify.class_api(bytes.fromhex('cafebabe000000340001'))
