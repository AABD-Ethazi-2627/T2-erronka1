"""Portable guards for component preparation; no network, Java or services."""
import importlib.util
import io
import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

HERE=Path(__file__).resolve().parents[1]/'deploy/images/nifi-patches/jackson'
spec=importlib.util.spec_from_file_location('cnc_jackson_candidate',HERE/'verify.py')
v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)

class JacksonCandidateTests(unittest.TestCase):
    def setUp(self): self.pins=json.loads((HERE/'pins.json').read_text())
    def occurrence(self,digest,outer):
        return {'sha256':digest,'outer':outer,'members':[],
                'outer_sha256':digest,'chain_sha256':[digest]}
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
    def test_coordinate_path_injection_rejected_even_with_matching_file_and_url(self):
        self.pins[0].update({'coordinate':'g:../../outside:1','file':'../../outside-1.jar',
            'url':'https://repo.maven.apache.org/maven2/g/../../outside/1/../../outside-1.jar'})
        with self.assertRaisesRegex(ValueError,'unsafe Maven coordinate'):v.validate_pins(self.pins)
    def test_shaded_wrapper_never_gets_plain_replacement(self):
        objects=[{'package':'tools.jackson.core:jackson-core','version':'3.1.2','object_paths':['nested/'+('a'*64)+'.jar']}]
        result=v.classify(objects,[self.occurrence('a'*64,'hazelcast.jar')],self.pins)
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
            result=v.classify(objects,[self.occurrence(pin['sha256'],'stock.jar')],self.pins)[0]
            self.assertEqual(result['replacement']['coordinate'],g+':jackson-core:'+new)
            self.assertEqual(old.split('.')[:2],new.split('.')[:2])
            self.assertEqual(result['occurrences'][0]['chain_sha256'],[pin['sha256']])
            self.assertEqual(result['occurrences'][0]['outer_sha256'],pin['sha256'])
    def test_changed_and_linked_artifact_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'jar';p.write_bytes(b'altered')
            with self.assertRaisesRegex(ValueError,'integrity'):v.checked(p,v.sha(b'original'))
            q=Path(t)/'link';q.symlink_to(p)
            with self.assertRaisesRegex(ValueError,'linked'):v.checked(q,v.sha(b'altered'))
    def test_download_rejects_dangling_symlink_before_network_or_write(self):
        with tempfile.TemporaryDirectory() as t:
            outside=Path(t)/'outside';target=Path(t)/'cached';target.symlink_to(outside)
            with patch.object(v.urllib.request,'urlopen') as network:
                with self.assertRaisesRegex(ValueError,'linked download'):
                    v.fetch_checked({'url':'https://repo.maven.apache.org/','sha256':v.sha(b'valid')},target)
                network.assert_not_called()
            self.assertFalse(outside.exists())
    def test_oversized_download_never_publishes_cache_entry(self):
        with tempfile.TemporaryDirectory() as t:
            target=Path(t)/'cached'
            with patch.object(v,'MAX_DOWNLOAD_BYTES',4), patch.object(v.urllib.request,'urlopen',return_value=io.BytesIO(b'12345')), self.assertRaisesRegex(ValueError,'integrity/size'):
                v.fetch_checked({'url':'https://repo.maven.apache.org/','sha256':v.sha(b'12345')},target)
            self.assertFalse(target.exists())
    def test_wrong_download_hash_and_existing_destination_never_publish(self):
        with tempfile.TemporaryDirectory() as t:
            target=Path(t)/'cached';pin={'url':'https://repo.maven.apache.org/','sha256':v.sha(b'valid')}
            with patch.object(v.urllib.request,'urlopen',return_value=io.BytesIO(b'wrong')), self.assertRaises(ValueError):
                v.fetch_checked(pin,target)
            self.assertFalse(target.exists())
            target.write_bytes(b'preserve existing')
            with patch.object(v.urllib.request,'urlopen',return_value=io.BytesIO(b'valid')), self.assertRaises(FileExistsError):
                v.fetch_checked(pin,target)
            self.assertEqual(target.read_bytes(),b'preserve existing')
    def test_every_source_root_is_bound_and_symlinks_or_extra_files_fail(self):
        with tempfile.TemporaryDirectory() as t:
            source=Path(t);(source/'selected.nar').write_bytes(b'selected');(source/'unselected.nar').write_bytes(b'unselected')
            inv={'occurrences':[{'outer':p.name,'outer_sha256':v.sha(p.read_bytes()),'members':[]} for p in source.iterdir()]}
            self.assertEqual(len(v.verify_source(source,inv)),2)
            (source/'unselected.nar').write_bytes(b'drift')
            with self.assertRaisesRegex(ValueError,'integrity'):v.verify_source(source,inv)
            (source/'unselected.nar').unlink();(source/'unselected.nar').symlink_to(source/'selected.nar')
            with self.assertRaisesRegex(ValueError,'linked source'):v.verify_source(source,inv)
            (source/'unselected.nar').unlink()
            with self.assertRaisesRegex(ValueError,'incomplete'):v.verify_source(source,inv)
            (source/'unselected.nar').write_bytes(b'unselected');(source/'extra.py').write_text('unapproved')
            with self.assertRaisesRegex(ValueError,'unexpected source'):v.verify_source(source,inv)
    def test_scan_grouping_requires_exact_nonempty_agreement(self):
        objects=[{'package':'tools.jackson.core:jackson-core','version':'3.2.2','object_paths':['hash.jar']}]
        scan={'Results':[{'Vulnerabilities':[{'PkgName':objects[0]['package'],'InstalledVersion':'3.2.2','PkgPath':'hash.jar'}]}]}
        v.check_grouping(scan,objects)
        with self.assertRaisesRegex(ValueError,'grouping'):v.check_grouping(scan,[])
        with self.assertRaisesRegex(ValueError,'grouping'):v.check_grouping({'Results':[]},[])
    def test_relocated_class_carriers_without_maven_metadata_are_explicitly_blocked(self):
        rows=[]
        for digest,package in [('plain','com/fasterxml/jackson/core'),('aws','software/amazon/awssdk/thirdparty/jackson/core/json'),('azure','com/azure/json/implementation/jackson/core')]:
            rows.append({'outer':digest+'.nar','members':['dependency.jar'],'chain_sha256':['outer',digest],
                         'sha256':digest,'class_packages':[package],'maven':[]})
        carriers=v.jackson_carriers({'occurrences':rows},{'plain'})
        self.assertEqual({c['sha256'] for c in carriers if not c['scanner_mapped']},{'aws','azure'})
        self.assertTrue(all(c['status'].startswith('blocked-') for c in carriers if not c['scanner_mapped']))
    def test_abi_failure_blocks_the_atomic_pair_and_plan_never_approves_runtime(self):
        entries=[{'package':'com.fasterxml.jackson.core:'+artifact,'version':'2.22.2','object_sha256':artifact,
                  'replacement':{'coordinate':artifact},'occurrences':[{'outer':'context.nar','members':[artifact+'.jar']}],
                  'status':'component-candidate-consumer-review-required'} for artifact in ('jackson-core','jackson-databind')]
        results={'2.22.2->2.22.3':{'jackson-core_symbolic_abi':{'removed_or_changed':['removed public class']},
                                  'jackson-databind_symbolic_abi':{'removed_or_changed':[]}}}
        plan=v.finish_plan(entries,results,[])
        self.assertFalse(plan['runtime_approved'])
        self.assertTrue(all(e['status'].startswith('blocked-atomic') for e in plan['entries']))
        self.assertEqual(plan['atomic_replacement_units'][0]['status'],'blocked')
    def test_plan_artifact_still_has_no_wrapper_replacement_or_runtime_approval(self):
        plan=json.loads((HERE/'candidate-plan.json').read_text())
        self.assertFalse(plan['runtime_approved'])
        for entry in plan['entries']:
            if not entry['upstream_old_equal']:self.assertIsNone(entry['replacement'])
            if entry['symbolic_abi_changes']:self.assertTrue(entry['status'].startswith('blocked-'))
    def test_different_namespaces_cannot_supply_each_others_atomic_companion(self):
        entries=[];results={}
        for group,version,artifact,new in [('com.fasterxml.jackson.core','2.22.2','jackson-core','2.22.3'),
                                           ('tools.jackson.core','3.2.2','jackson-databind','3.2.3')]:
            entries.append({'package':group+':'+artifact,'version':version,'object_sha256':artifact,
                            'replacement':{'coordinate':artifact},'occurrences':[{'outer':'context.nar','members':[artifact+'.jar']}],
                            'status':'component-candidate-consumer-review-required'})
            results[version+'->'+new]={artifact+'_symbolic_abi':{'removed_or_changed':[]}}
        plan=v.finish_plan(entries,results,[])
        self.assertEqual(len(plan['atomic_replacement_units']),2)
        self.assertTrue(all(u['status']=='blocked' for u in plan['atomic_replacement_units']))
    def test_java_environment_and_process_limits_cannot_be_bypassed(self):
        with tempfile.TemporaryDirectory() as t, patch.dict(os.environ,{'LD_AUDIT':'not-real','JAVA_TOOL_OPTIONS':'injection'}), patch.object(v.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout=b'',stderr=b'')) as command:
            v.run(['unused'],Path(t)/'log')
            self.assertEqual(command.call_args.kwargs['preexec_fn'],v.limits)
            self.assertNotIn('LD_AUDIT',command.call_args.kwargs['env'])
            self.assertNotIn('JAVA_TOOL_OPTIONS',command.call_args.kwargs['env'])
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
    def test_all_extract_identity_links_and_ambiguity_are_enforced(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)/'source';root.mkdir();payload=io.BytesIO()
            with zipfile.ZipFile(payload,'w') as z:z.writestr('leaf.jar',b'stock')
            data=payload.getvalue();(root/'outer.nar').write_bytes(data)
            (root.parent/'outside.nar').write_bytes(data)
            original={'outer':'outer.nar','outer_sha256':v.sha(data),'members':['leaf.jar'],
                      'chain_sha256':[v.sha(data),v.sha(b'stock')],'sha256':v.sha(b'stock')}
            for mutation in ('escape','absolute','outer','chain-root','leaf'):
                case={**original,'chain_sha256':original['chain_sha256'][:]}
                if mutation=='escape':case['outer']='../outside.nar'
                if mutation=='absolute':case['outer']=str(root.parent/'outside.nar')
                if mutation=='outer':case['outer_sha256']=case['chain_sha256'][0]=v.sha(b'wrong')
                if mutation=='chain-root':case['chain_sha256'][0]=v.sha(b'wrong')
                if mutation=='leaf':case['sha256']=v.sha(b'wrong')
                with self.subTest(mutation=mutation),self.assertRaises(ValueError):v.extract(root,case)
            payload=io.BytesIO()
            with zipfile.ZipFile(payload,'w') as z,self.assertWarns(UserWarning):
                z.writestr('leaf.jar',b'stock');z.writestr('leaf.jar',b'stock')
            data=payload.getvalue();(root/'outer.nar').write_bytes(data)
            original['outer_sha256']=original['chain_sha256'][0]=v.sha(data)
            with self.assertRaisesRegex(ValueError,'ambiguous'):v.extract(root,original)
    def test_bounded_model_namespace_and_tamper_guards(self):
        helper,model=v.support_modules()
        with self.assertRaisesRegex(ValueError,'truncated'):helper.class_api(b'\xca\xfe\xba\xbe')
        import xml.etree.ElementTree as E
        for xml in ['<project/>','<project xmlns="urn:evil"/>','<project xmlns="http://maven.apache.org/POM/4.0.0"><dependencies xmlns=""/></project>']:
            with self.assertRaises(ValueError):model.model_namespace(E.fromstring(xml))

if __name__=='__main__':unittest.main()
