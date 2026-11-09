"""Portable guards; no Java, network, build, service or stock modification."""
import importlib.util
import io
import json
import runpy
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

    def class_fixture(self, name, *, parent='', access=1, members=(), references=(), descriptors=()):
        """Small constant-pool fixtures, never loaded by a JVM."""
        pool=[]
        def add(data):
            pool.append(data)
            return len(pool)
        def utf(value):
            data=value.encode()
            return add(b'\x01'+struct.pack('>H',len(data))+data)
        def klass(value):return add(b'\x07'+struct.pack('>H',utf(value)))
        this=klass(name);superclass=klass(parent) if parent else 0
        for descriptor in descriptors:utf(descriptor)
        for owner,member,descriptor,kind in references:
            target=klass(owner)
            pair=add(b'\x0c'+struct.pack('>HH',utf(member),utf(descriptor)))
            add(bytes([9 if kind=='field' else 10])+struct.pack('>HH',target,pair))
        sections=[]
        for kind in ('field','method'):
            selected=[x for x in members if x[0]==kind]
            section=struct.pack('>H',len(selected))
            for _,member,descriptor,flags in selected:
                section+=struct.pack('>HHHH',flags,utf(member),utf(descriptor),0)
            sections.append(section)
        return (struct.pack('>IHHH',0xcafebabe,0,61,len(pool)+1)+b''.join(pool)
                +struct.pack('>HHHH',access,this,superclass,0)+b''.join(sections)+b'\x00\x00')

    def write_classes(self, path, classes):
        with zipfile.ZipFile(path,'w') as archive:
            for name,data in classes.items():archive.writestr(name+'.class',data)

    def test_linkage_checks_external_members_and_descriptors(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);old,new,consumer=[root/name for name in ('old.jar','new.jar','consumer.jar')]
            self.write_classes(old,{'Owner':self.class_fixture('Owner',members=[('field','value','I',1),('method','act','()V',1)]),'Removed':self.class_fixture('Removed')})
            self.write_classes(new,{'Owner':self.class_fixture('Owner')})
            self.write_classes(consumer,{'Use':self.class_fixture('Use',references=[('Owner','value','I','field'),('Owner','act','()V','method')],descriptors=['LRemoved;'])})
            result=linkage.analyze(old,new,[consumer])
            found={tuple(row['reference']) for row in result['direct_references_to_removed_symbols']}
            self.assertTrue({('Owner','value','I','field'),('Owner','act','()V','method'),('Removed','','','descriptor')}<=found)
            self.assertEqual(result['consumer_hashes'],{str(consumer):m.sha(consumer.read_bytes())})
            self.assertEqual(result['base_classes_checked_including_changed_wrapper_and_consumers'],2)

    def test_linkage_reports_changed_headers_and_member_flags(self):
        with tempfile.TemporaryDirectory() as directory:
            old,new=[Path(directory)/name for name in ('old.jar','new.jar')]
            self.write_classes(old,{'Owner':self.class_fixture('Owner',parent='OldParent',members=[('field','value','I',1)])})
            self.write_classes(new,{'Owner':self.class_fixture('Owner',parent='NewParent',access=0,members=[('field','value','I',9)])})
            changes=linkage.analyze(old,new)['access_or_hierarchy_changes']
            self.assertEqual(len(changes),2)
            header=next(x for x in changes if 'old_header' in x)
            self.assertEqual((header['old_header'],header['new_header']),(('OldParent',()),('NewParent',())))
            self.assertEqual((header['old_access'],header['new_access']),(1,0))
            member=next(x for x in changes if 'member' in x)
            self.assertEqual((member['member'],member['old_flags'],member['new_flags']),(('field','value','I'),1,9))

    def test_linkage_cli_fails_on_real_consumer_reference(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);cache=root/'cache';proof=root/'proof';fixture=root/'config'
            for folder in (cache,proof,fixture):folder.mkdir()
            old=cache/'parquet-jackson-1.18.1.jar';candidate=proof/'candidate.jar';consumer=cache/'parquet-hadoop.jar'
            self.write_classes(old,{'Removed':self.class_fixture('Removed')})
            self.write_classes(candidate,{'Kept':self.class_fixture('Kept')})
            self.write_classes(consumer,{'Use':self.class_fixture('Use',descriptors=['LRemoved;'])})
            (fixture/'consumer-pins.json').write_text(json.dumps([{'file':consumer.name,'sha256':m.sha(consumer.read_bytes())}]))
            (proof/'summary.json').write_text(json.dumps({'candidate':candidate.name,'candidate_sha256':m.sha(candidate.read_bytes()),'source':{'fixture':'bound'}}))
            output=root/'linkage.json'
            argv=['linkage.py','--cache',str(cache),'--proof',str(proof),'--output',str(output)]
            with mock.patch.dict(sys.modules,{'prepare':m}),mock.patch.object(m,'HERE',fixture),mock.patch.object(m,'OLD',m.sha(old.read_bytes())),mock.patch.object(m,'source_files',return_value={'fixture':'bound'}),mock.patch.object(sys,'argv',argv),self.assertRaisesRegex(SystemExit,'direct consumer references remain'):
                runpy.run_path(str(HERE/'linkage.py'),run_name='__main__')
            result=json.loads(output.read_text())
            self.assertEqual(len(result['consumer_hashes']),1)
            self.assertTrue(result['direct_references_to_removed_symbols'])
            self.assertFalse(result['runtime_approved'])

    def test_launcher_applies_real_preexec_core_cpu_and_affinity_limits(self):
        from types import SimpleNamespace
        def intercept(*args,**kwargs):
            with mock.patch.object(bounded.resource,'setrlimit') as limit,mock.patch.object(bounded.os,'sched_getaffinity',return_value={3,7}),mock.patch.object(bounded.os,'sched_setaffinity') as affinity:
                kwargs['preexec_fn']()
                self.assertEqual(limit.call_args_list,[mock.call(bounded.resource.RLIMIT_CORE,(0,0)),mock.call(bounded.resource.RLIMIT_CPU,(30,30))])
                affinity.assert_called_once_with(0,{3})
            return SimpleNamespace(returncode=0,stdout=b'',stderr=b'')
        with tempfile.TemporaryDirectory() as directory,mock.patch.object(bounded.subprocess,'run',side_effect=intercept):
            bounded.run([bounded.JDK/'bin/java',*bounded.FLAGS,'-version'],Path(directory)/'run.log')

    def prepare_main_fixture(self, root, *, stock_drift=False, source_drift=False, bad_baseline=False):
        """Run the real orchestration with synthetic archives and a data-only Shade stub."""
        cache=root/'cache';source=root/'stock';config=root/'workspace/deploy/images/nifi-patches/parquet-jackson';out=root/'output'
        for folder in (cache,source,config,config.parent/'jackson'):folder.mkdir(parents=True)
        old_payload={'shaded/parquet/com/fasterxml/jackson/Core.class':b'old-code',
                     'shaded/parquet/com/fasterxml/jackson/fdp/v2_22_2/Old.class':b'old-parser',
                     'META-INF/maven/com.fasterxml.jackson.core/jackson-core/pom.properties':b'version=2.22.2'}
        fixed_payload={'shaded/parquet/com/fasterxml/jackson/Core.class':b'fixed-code',
                       'shaded/parquet/com/fasterxml/jackson/fdp/v2_22_3/New.class':b'fixed-parser',
                       'META-INF/maven/com.fasterxml.jackson.core/jackson-core/pom.properties':b'version=2.22.3'}
        def archive_bytes(values):
            data=io.BytesIO()
            with zipfile.ZipFile(data,'w') as archive:
                for name,content in values.items():archive.writestr(name,content)
            return data.getvalue()
        original=archive_bytes({'META-INF/MANIFEST.MF':b'Manifest-Version: 1.0\r\n','service':b'untouched',**old_payload})
        jar=cache/'parquet-jackson-1.18.1.jar';jar.write_bytes(original)
        nar=source/'opt/nifi/nifi-current/lib/nifi-iceberg-parquet-writer-nar-2.12.0.nar'
        nar.parent.mkdir(parents=True);nar.write_bytes(archive_bytes({'META-INF/bundled-dependencies/'+jar.name:original}))
        (config/'pins.json').write_text(json.dumps([{'file':jar.name,'sha256':m.sha(original),'url':'https://repo.maven.apache.org/maven2/fixture.jar'}]))
        (config/'support-lock.json').write_text('{}');(config.parent/'jackson/jdk21-pins.json').write_text('{}')
        def shade(command,log):
            Path(log).write_bytes(b'synthetic Shade fixture; no Java executed')
            if 'Shade' in command:
                target=Path(command[command.index('Shade')+1])
                values=old_payload if '2.22.2-' in target.name else fixed_payload
                if bad_baseline and '2.22.2-' in target.name:values=values|{'shaded/parquet/com/fasterxml/jackson/Core.class':b'wrong-baseline'}
                target.write_bytes(archive_bytes(values))
        stock_values=[{'root':'before'},{'root':'after' if stock_drift else 'before'}]
        source_values=[{'fixture':'before'},{'fixture':'after' if source_drift else 'before'}]
        argv=['prepare.py','--cache',str(cache),'--source',str(source),'--output',str(out)]
        with mock.patch.object(m,'HERE',config),mock.patch.object(m,'OLD',m.sha(original)),mock.patch.object(m,'stock',side_effect=stock_values),mock.patch.object(m,'source_files',side_effect=source_values),mock.patch.object(m,'run',side_effect=shade),mock.patch.object(sys,'argv',argv):
            m.main()
        return out,fixed_payload,old_payload

    def test_prepare_main_checks_stock_source_and_baseline_before_publication(self):
        for kwargs,message in [({'stock_drift':True},'stock changed'),({'source_drift':True},'source changed'),({'bad_baseline':True},'baseline mismatch')]:
            with self.subTest(kwargs=kwargs),tempfile.TemporaryDirectory() as directory:
                root=Path(directory)
                with self.assertRaisesRegex(ValueError,message):self.prepare_main_fixture(root,**kwargs)
                self.assertFalse((root/'output/parquet-jackson-1.18.1-cnc-jackson.jar').exists())

    def test_prepare_main_removes_obsolete_classes_and_replaces_version_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            out,fixed,old=self.prepare_main_fixture(Path(directory))
            actual=m.entries(out/'parquet-jackson-1.18.1-cnc-jackson.jar')
            self.assertFalse((set(old)-set(fixed)) & set(actual))
            for name,value in fixed.items():self.assertEqual(actual[name],value)
            self.assertEqual(actual['service'],b'untouched')
            self.assertFalse(json.loads(actual[m.PROVENANCE])['runtime_approved'])

    def test_rejects_faulty_writer_entry_content_raw_and_central_changes(self):
        base_zip=zipfile.ZipFile
        for fault,message in [('drop','entry-set drift'),('content','preserved content drift'),('raw','preserved raw record drift'),('central','preserved central metadata drift')]:
            with self.subTest(fault=fault):
                class FaultyWriter(base_zip):
                    def close(writer, fault=fault):
                        writing=writer.mode=='w' and writer.fp is not None
                        output=writer.fp
                        super().close()
                        if not writing:return
                        data=output.getvalue()
                        if fault=='central':
                            data=bytearray(data)
                            with base_zip(io.BytesIO(data)) as archive:offset=archive.start_dir
                            self.assertEqual(data[offset:offset+4],b'PK\x01\x02')
                            value=struct.unpack_from('<I',data,offset+38)[0]
                            struct.pack_into('<I',data,offset+38,value^0x10000)
                        else:
                            changed=io.BytesIO()
                            with base_zip(io.BytesIO(data)) as acquired,base_zip(changed,'w') as rewritten:
                                rewritten.comment=acquired.comment
                                for info in acquired.infolist():
                                    if info.filename=='native/lib.so' and fault=='drop':continue
                                    content=acquired.read(info)
                                    if info.filename=='native/lib.so':
                                        if fault=='content':content=b'writer changed preserved bytes'
                                        elif fault=='raw':info.compress_type=zipfile.ZIP_STORED
                                    rewritten.writestr(info,content)
                            data=changed.getvalue()
                        output.seek(0);output.truncate();output.write(data)
                original=self.jar()
                with mock.patch.object(m.zipfile,'ZipFile',FaultyWriter),self.assertRaisesRegex(ValueError,message):
                    self.rebuild(original)

    def test_probe_orchestration_rejects_native_loader_before_summary(self):
        with mock.patch.dict(sys.modules,{'prepare':m,'bounded':bounded}):
            probe=load('parquet_probe_test','probes.py')
        for native in (False,True):
            with self.subTest(native=native),tempfile.TemporaryDirectory() as directory:
                root=Path(directory);cache=root/'cache';proof=root/'proof';out=root/'output'
                config=root/'workspace/deploy/images/nifi-patches/parquet-jackson'
                for folder in (cache,proof,config,config.parent/'jackson'):folder.mkdir(parents=True)
                original=cache/'parquet-jackson-1.18.1.jar';original.write_bytes(b'fixture')
                candidate=proof/'candidate.jar';candidate.write_bytes(b'fixture-candidate')
                pin={'file':original.name,'sha256':m.sha(original.read_bytes()),'url':'https://repo.maven.apache.org/maven2/fixture.jar'}
                (config/'pins.json').write_text(json.dumps([pin]));(config/'consumer-pins.json').write_text('[]')
                (config/'support-lock.json').write_text('{}');(config.parent/'jackson/jdk21-pins.json').write_text('{}')
                (config/'JacksonProbe.java.in').write_text('// data-only fixture; no Java executed')
                (proof/'summary.json').write_text(json.dumps({'candidate':candidate.name,'candidate_sha256':m.sha(candidate.read_bytes()),'source':{'fixture':'same'}}))
                def java_stub(command,log,native=native):
                    Path(log).write_bytes(b'data-only Java orchestration fixture')
                    for argument in command:
                        if str(argument).startswith('-Xlog:class+load=info:file='):
                            Path(str(argument).split('file=',1)[1]).write_text('org.apache.hadoop.util.NativeCodeLoader' if native else 'fixture class loading')
                argv=['probes.py','--cache',str(cache),'--proof',str(proof),'--output',str(out)]
                with mock.patch.object(probe,'HERE',config),mock.patch.object(probe,'source_files',return_value={'fixture':'same'}),mock.patch.object(probe,'run',side_effect=java_stub),mock.patch.object(sys,'argv',argv):
                    if native:
                        with self.assertRaisesRegex(ValueError,'unexpected native Hadoop loader path'):probe.main()
                        self.assertFalse((out/'summary.json').exists())
                    else:
                        probe.main()
                        self.assertFalse(json.loads((out/'summary.json').read_text())['runtime_approved'])

if __name__=='__main__':unittest.main()
