"""Portable guards: fixtures/model checks are not ES runtime acceptance."""
import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parents[1] / 'deploy/images/elasticsearch-patches/otel-qualification'


def load(name):
    spec = importlib.util.spec_from_file_location('_es_test_' + name, HERE / (name + '.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


q = load('qualify')
r = load('run_reserved')


def inventory_fixture():
    pins = {p['file']:p for p in json.loads((HERE/'reusable-official-pins.json').read_text())['files']}
    rows = ['JAVA\t25.0.1\t25']
    for realm in q.REALMS:
        module = 'org.elasticsearch.telemetry.apm' if realm == 'apm' else ''
        extensions = 'x-pack-esql,workload-identity' if realm == 'esql-datasource-gcs' else ''
        rows.extend([f'REALM\t{realm}\tconsumer.Plugin\t{module}\t{extensions}\t'+('a'*64),
                     f'POLICY\t{realm}\t'+('b'*64)])
        for artifact in q.TRIO:
            name = f'opentelemetry-{artifact}-1.67.0.jar'
            rows.extend([f'JAR\t{realm}\t{name}\t123\t'+pins[name]['sha256'],
                         f'MODULE\t{realm}\t{name}\tio.opentelemetry.{artifact}\ttrue\t1.67.0'])
        rows.append(f'GRAPH\t{realm}\t{module}\t{extensions}\tfalse\t'+('a'*64))
    for extension in ('x-pack-esql', 'workload-identity'):
        rows.append(f'GRAPH\t{extension}\t\t\ttrue\t'+('c'*64))
    rows.extend(['LOADER\telasticsearch-9.5.5.jar\t'+('d'*64)+'\t'+('e'*64),
                 'STATUS\tinventory-only\treplacement=null\truntime_approved=false'])
    return '\n'.join(rows)+'\n'


class MetadataGuards(unittest.TestCase):
    def test_separate_realms_accept_same_named_api_without_flattening(self):
        result = q.audit_rows(inventory_fixture())
        self.assertEqual(set(result['realms']), set(q.REALMS))
        self.assertEqual(result['java_feature'], 25)
        self.assertEqual(result['realms']['esql-datasource-gcs']['extended_plugins'], ['x-pack-esql','workload-identity'])
        self.assertIsNone(result['replacement'])
        self.assertFalse(result['runtime_approved'])

    def test_truncated_inventory_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'incomplete'):
            q.audit_rows(inventory_fixture().rsplit('STATUS',1)[0])

    def test_duplicate_jar_in_same_realm_is_rejected(self):
        text = inventory_fixture()
        row = next(row for row in text.splitlines() if row.startswith('JAR'))
        with self.assertRaisesRegex(ValueError,'duplicate'):
            q.audit_rows(text.replace(row,row+'\n'+row))

    def test_module_name_collision_is_rejected_per_realm(self):
        with self.assertRaisesRegex(ValueError,'duplicate JPMS'):
            q.audit_rows(inventory_fixture().replace('io.opentelemetry.context','io.opentelemetry.api'))

    def test_missing_extension_boundary_is_not_declared_closed(self):
        text = '\n'.join(x for x in inventory_fixture().splitlines() if not x.startswith('GRAPH\tworkload-identity'))
        with self.assertRaisesRegex(ValueError,'unresolved extension'):
            q.audit_rows(text)

    def test_current_api_bytes_must_match_existing_official_pin(self):
        text = inventory_fixture()
        pin = json.loads((HERE/'reusable-official-pins.json').read_text())['files']
        digest = next(p['sha256'] for p in pin if p['file']=='opentelemetry-api-1.67.0.jar')
        with self.assertRaisesRegex(ValueError,'API trio input mismatch'):
            q.audit_rows(text.replace(digest, '0'*64, 1))

    def test_sdk_selection_refuses_unobserved_and_never_selects_exporters(self):
        data = q.audit_rows(inventory_fixture())
        with self.assertRaisesRegex(ValueError,'unobserved SDK'):
            q.sdk_experiment(data)
        for artifact in q.SDK:
            data['realms']['apm']['jars'][f'opentelemetry-{artifact}-1.62.0.jar'] = {'sha256':'0'*64}
        selected = q.sdk_experiment(data)
        self.assertEqual(len(selected),6)
        self.assertFalse(any('exporter' in name or 'incubator' in name for name in selected))

    def test_official_exporter_metadata_flags_okhttp_closure_change(self):
        data = json.loads((HERE/'exporter-pom-observation.json').read_text())
        sender = next(x for x in data['files'] if 'sender-okhttp' in x['coordinate'])
        dependency = next(x for x in sender['dependencies'] if x['artifactId']=='okhttp-jvm')
        self.assertEqual(dependency['version'],'5.5.0')
        self.assertIsNone(data['replacement'])
        self.assertFalse(data['runtime_approved'])


class RuntimeAndModelGuards(unittest.TestCase):
    def test_command_has_finite_resources_network_and_readonly_inputs(self):
        cmd = r.command('cnc-es-otel-inventory-test', HERE)
        for option,value in [('--memory','512m'),('--memory-swap','512m'),('--cpus','1'),
                             ('--network','none'),('--cap-drop','ALL'),('--user','1000:1000')]:
            self.assertEqual(cmd[cmd.index(option)+1],value)
        self.assertIn('--read-only',cmd)
        self.assertIn('--pull=never',cmd)
        self.assertIn('-Xmx256m',cmd)
        self.assertIn('-XX:MaxMetaspaceSize=96m',cmd)
        self.assertIn('-XX:MaxDirectMemorySize=32m',cmd)
        self.assertTrue(cmd[cmd.index('--mount')+1].endswith(',readonly'))
        self.assertEqual(cmd[cmd.index('--entrypoint')+1],'/usr/share/elasticsearch/jdk/bin/java')
        self.assertNotIn('elasticsearch',cmd)
        self.assertEqual(cmd[-1],'/usr/share/elasticsearch')

    def test_missing_provider_negative_control_detects_real_reference(self):
        key = ('method','method','()V')
        old = {'io/opentelemetry/Api': {'members':{key:1}, 'parents':[]}}
        refs = [('actual.Consumer',('io/opentelemetry/Api','method','()V','method'))]
        broken = q.s.newly_broken(old,{},refs)
        self.assertEqual(len(broken),1)
        with self.assertRaisesRegex(ValueError,'no actual'):
            q.s.newly_broken(old,{},[])

    def test_model_uses_explicit_runtime_feature_for_multi_release(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'fixture.jar'
            with zipfile.ZipFile(path,'w') as archive:
                archive.writestr('META-INF/MANIFEST.MF','Manifest-Version: 1.0\nMulti-Release: true\n')
                archive.writestr('test/A.class',b'base')
                archive.writestr('META-INF/versions/25/test/A.class',b'java25')
                archive.writestr('META-INF/versions/26/test/A.class',b'future')
            original = q.s.parse
            q.s.parse = lambda data: data
            try:
                self.assertEqual(list(q.s.classes(path,25)),[('test/A.class',b'java25')])
                self.assertEqual(list(q.s.classes(path,21)),[('test/A.class',b'base')])
            finally:
                q.s.parse = original

    def test_actual_extracted_file_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'input'
            path.write_bytes(b'fixture')
            link = Path(temp)/'link';link.symlink_to(path)
            with self.assertRaisesRegex(ValueError,'linked'):
                q.safe_file(link)


if __name__ == '__main__':
    unittest.main()
