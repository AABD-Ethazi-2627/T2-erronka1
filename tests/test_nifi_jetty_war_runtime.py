"""Portable WAR extraction and source-pin boundaries; no JVM or service claim."""
import importlib.util
import io
import json
import stat
import sys
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

HERE=Path(__file__).resolve().parents[1]/'deploy/images/nifi-patches/plain-jackson-qualification'


def load():
    spec=importlib.util.spec_from_file_location('_jetty_qualify',HERE/'qualify.py')
    qualifier=importlib.util.module_from_spec(spec);spec.loader.exec_module(qualifier)
    spec=importlib.util.spec_from_file_location('_jetty_war',HERE/'war_runtime.py')
    module=importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules,{'qualify':qualifier}):spec.loader.exec_module(module)
    return module


def archive(rows):
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w') as z:
        for name,data in rows:z.writestr(name,data)
    stream.seek(0)
    return zipfile.ZipFile(stream)


@pytest.mark.parametrize('name',['../escape','/absolute','a/../escape','./a','a//b','a\\b'])
def test_noncanonical_member_rejected_without_outside_write(tmp_path,name):
    m=load()
    with archive([(name,b'payload')]) as z,pytest.raises(ValueError,match='ambiguous|escaping|canonical'):
        m.extract_war(z,tmp_path/'output',{},tmp_path,False)
    assert not (tmp_path/'escape').exists()


def test_duplicate_names_rejected_before_partial_extraction(tmp_path):
    m=load()
    with pytest.warns(UserWarning):z=archive([('a',b'first'),('a',b'second')])
    with z,pytest.raises(ValueError,match='ambiguous|duplicate'):
        m.extract_war(z,tmp_path/'output',{},tmp_path,False)
    assert not (tmp_path/'output/a').exists()


def test_symlink_member_and_directory_payload_rejected(tmp_path):
    m=load()
    for index,info in enumerate((zipfile.ZipInfo('link'),zipfile.ZipInfo('directory/'))):
        info.external_attr=((stat.S_IFLNK|0o777) if index==0 else (stat.S_IFDIR|0o755))<<16
        with archive([(info,b'outside')]) as z,pytest.raises(ValueError,match='special|directory'):
            m.extract_war(z,tmp_path/str(index),{},tmp_path,False)


def test_output_parent_symlink_cannot_redirect_extraction(tmp_path):
    m=load();outside=tmp_path/'outside';outside.mkdir();link=tmp_path/'linked';link.symlink_to(outside,target_is_directory=True)
    with archive([('a',b'payload')]) as z,pytest.raises(ValueError,match='link'):
        m.extract_war(z,link/'output',{},tmp_path,False)
    assert not (outside/'output').exists()


def test_existing_output_preserved(tmp_path):
    m=load();output=tmp_path/'output';output.mkdir();(output/'saved').write_bytes(b'evidence')
    with archive([('saved',b'changed')]) as z,pytest.raises(FileExistsError):
        m.extract_war(z,output,{},tmp_path,False)
    assert (output/'saved').read_bytes()==b'evidence'


@pytest.mark.parametrize('fixed',[False,True])
def test_wrong_original_pin_rejected_in_both_variants(tmp_path,fixed):
    m=load();name='jackson-core-2.22.2.jar';pins={name:{'sha256':m.q.sha(b'correct')}}
    with archive([('WEB-INF/lib/'+name,b'wrong')]) as z,pytest.raises(ValueError,match='old WAR JAR pin'):
        m.extract_war(z,tmp_path/'output',pins,tmp_path,fixed)


def test_replacement_is_renamed_pinned_and_other_bytes_preserved(tmp_path):
    m=load();old='jackson-core-2.22.2.jar';new=m.q.OLD_NEW[old]
    (tmp_path/new).write_bytes(b'fixed')
    pins={old:{'sha256':m.q.sha(b'old')},new:{'sha256':m.q.sha(b'fixed')}}
    with archive([('WEB-INF/lib/'+old,b'old'),('WEB-INF/classes/C.class',b'unchanged')]) as z:
        changes=m.extract_war(z,tmp_path/'output',pins,tmp_path,True)
    assert (tmp_path/'output/WEB-INF/lib'/new).read_bytes()==b'fixed'
    assert not (tmp_path/'output/WEB-INF/lib'/old).exists()
    assert (tmp_path/'output/WEB-INF/classes/C.class').read_bytes()==b'unchanged'
    assert changes==[{'old':old,'new':new,'sha256':m.q.sha(b'fixed')}]


def test_bad_or_linked_replacement_refused(tmp_path):
    m=load();old='jackson-core-2.22.2.jar';new=m.q.OLD_NEW[old]
    pins={old:{'sha256':m.q.sha(b'old')},new:{'sha256':m.q.sha(b'fixed')}}
    (tmp_path/new).write_bytes(b'wrong')
    with archive([('WEB-INF/lib/'+old,b'old')]) as z,pytest.raises(ValueError,match='fixed WAR JAR pin'):
        m.extract_war(z,tmp_path/'bad',pins,tmp_path,True)
    (tmp_path/new).unlink();(tmp_path/'actual').write_bytes(b'fixed');(tmp_path/new).symlink_to(tmp_path/'actual')
    with archive([('WEB-INF/lib/'+old,b'old')]) as z,pytest.raises(ValueError,match='link'):
        m.extract_war(z,tmp_path/'linked',pins,tmp_path,True)


def test_budget_rejected_before_reading_large_entry(tmp_path):
    m=load();info=zipfile.ZipInfo('large');info.file_size=97*1024**2
    class FakeArchive:
        def infolist(self):return [info]
        def read(self,entry):raise AssertionError('oversized entry must not be read')
    with pytest.raises(ValueError,match='budget'):
        m.extract_war(FakeArchive(),tmp_path/'output',{},tmp_path,False)


def test_source_pin_rejects_changes_and_links(tmp_path):
    m=load();p=tmp_path/'input';p.write_bytes(b'expected')
    assert m.verify_input_file(p,m.q.sha(b'expected'))==m.q.sha(b'expected')
    with pytest.raises(ValueError,match='input pin'):
        m.verify_input_file(p,m.q.sha(b'other'))
    link=tmp_path/'alias';link.symlink_to(p)
    with pytest.raises(ValueError,match='link'):
        m.verify_input_file(link,m.q.sha(b'expected'))


def test_context_selection_requires_exact_five_actual_wars():
    m=load();contexts=[{'id':id,'war':war} for id,war in m.EXPECTED_CONTEXTS]
    inv={'inventory_schema':2,'contexts':contexts}
    assert m.select_contexts(inv)==contexts
    for changed in [dict(inv,inventory_schema=1),dict(inv,contexts=contexts[:-1]),dict(inv,contexts=contexts+[contexts[0]]),dict(inv,contexts=contexts[:-1]+[{'id':'other','war':'other.war'}])]:
        with pytest.raises(ValueError,match='inventory|WAR denominator'):
            m.select_contexts(changed)


def test_input_metadata_cannot_claim_promotion(tmp_path):
    m=load()
    data={'schema':1,'runtime_approved':True,'replacement':None,'promotion_eligible':False}
    p=tmp_path/'inputs.json';p.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='preparation'):
        m.read_metadata(p)


def test_fixed_rename_collision_and_file_parent_collision_fail_before_writes(tmp_path):
    m=load();old='jackson-core-2.22.2.jar';new=m.q.OLD_NEW[old]
    cases=[([('WEB-INF/lib/'+old,b'old'),('WEB-INF/lib/'+new,b'new')],True),([('parent',b'file'),('parent/child',b'child')],False)]
    for index,(rows,fixed) in enumerate(cases):
        output=tmp_path/str(index)
        with archive(rows) as z,pytest.raises(ValueError,match='duplicate effective|collision'):
            m.extract_war(z,output,{},tmp_path,fixed)
        assert not output.exists()


def test_aggregate_budget_checked_without_reading_payload(tmp_path):
    m=load();infos=[]
    for name in ('one','two','three'):
        info=zipfile.ZipInfo(name);info.file_size=90*1024**2;infos.append(info)
    class FakeArchive:
        def infolist(self):return infos
        def read(self,entry):raise AssertionError('aggregate budget must be checked before reads')
    with pytest.raises(ValueError,match='budget'):
        m.extract_war(FakeArchive(),tmp_path/'output',{},tmp_path,False)
    assert not (tmp_path/'output').exists()
