"""Non-vacuous guards for inherited-member and NAR package access analysis."""
import importlib.util
import io
import struct
import tracemalloc
import zipfile
from pathlib import Path

import pytest

P=Path(__file__).resolve().parents[1]/'deploy/images/nifi-patches/plain-jackson-qualification/qualify.py'
S=importlib.util.spec_from_file_location('plain_jackson_qualification',P)
q=importlib.util.module_from_spec(S);S.loader.exec_module(q)

def cls(name,parents=(),members=None,flags=1,loader='nar'):
    return {'name':name,'parents':list(parents),'members':members or {},'flags':flags,'loader':loader}

def test_inherited_member_resolves_and_removed_member_fails():
    ref=('tools/jackson/Child','read','()V','method')
    index={'tools/jackson/Child':cls('tools/jackson/Child',['tools/jackson/Base']),
           'tools/jackson/Base':cls('tools/jackson/Base',members={('method','read','()V'):1}),
           'Consumer':cls('Consumer')}
    assert q.check(ref,'Consumer',index)==(None,('tools/jackson/Base',1))
    index['tools/jackson/Base']['members'].clear()
    assert q.check(ref,'Consumer',index)==('missing-member',None)

def test_protected_access_requires_subclass():
    key=('method','read','()V');ref=('tools/jackson/Base','read','()V','method')
    index={'tools/jackson/Base':cls('tools/jackson/Base',members={key:4}),
           'app/Child':cls('app/Child',['tools/jackson/Base']),
           'app/Unrelated':cls('app/Unrelated')}
    assert q.check(ref,'app/Child',index)[0] is None
    assert q.check(ref,'app/Unrelated',index)[0]=='inaccessible-member'

def test_same_package_different_nar_is_not_package_access():
    index={'p/Base':cls('p/Base',flags=0,loader='parent'),
           'p/Consumer':cls('p/Consumer',loader='child')}
    assert q.check(('p/Base','','','class'),'p/Consumer',index)[0]=='inaccessible-class'
    index['p/Consumer']['loader']='parent'
    assert q.check(('p/Base','','','class'),'p/Consumer',index)[0] is None

def test_constructor_is_not_inherited_and_field_searches_interfaces():
    key=('field','VALUE','I')
    index={'C':cls('C',['S','I']),
           'S':cls('S',members={key:1,('method','<init>','()V'):1}),
           'I':cls('I',members={key:9})}
    assert q.resolve('C',key,index)==('I',9)
    assert q.resolve('C',('method','<init>','()V'),index) is None

def test_scope_keeps_only_four_existing_pinned_pairs():
    import json
    pins={p['file']:p for p in json.loads((P.parent.parent/'jackson/pins.json').read_text())}
    assert len(q.OLD_NEW)==4
    assert set(q.OLD_NEW.values())=={'jackson-core-2.22.3.jar','jackson-databind-2.22.3.jar','jackson-core-3.2.3.jar','jackson-databind-3.2.3.jar'}
    assert all(n in pins for n in (*q.OLD_NEW,*q.OLD_NEW.values()))


def test_private_nestmates_need_verified_host_and_same_defining_loader():
    key=('method','read','()V');ref=('p/Host','read','()V','method')
    host=cls('p/Host',members={key:2});host.update(nest_host='p/Host',nest_members=['p/Host$Child'])
    child=cls('p/Host$Child');child.update(nest_host='p/Host',nest_members=[])
    index={'p/Host':host,'p/Host$Child':child}
    assert q.check(ref,'p/Host$Child',index)[0] is None
    child['loader']='different-nar'
    assert q.check(ref,'p/Host$Child',index)[0]=='inaccessible-member'


def test_jackson3_probe_cannot_be_injected_into_jackson2_parent():
    # Regression for a real failed probe: parent-first loading found the probe
    # in standard-shared, where its Jackson 3 dependency is intentionally absent.
    assert q.probe_family('nifi-jolt-nar')=='3'
    assert q.probe_family('nifi-standard-nar')=='3'
    assert q.probe_family('nifi-standard-shared-nar')=='2'
    assert q.probe_family('nifi-amqp-nar')=='2'


def classfile(name, methods=(), references=(), flags=0x421, parent='java/lang/Object'):
    """Portable classfile fixture: abstract declarations and real constant-pool refs.

    These bytes exercise the archive reader/parser, not a mocked classes adapter.
    They are not JVM execution evidence.
    """
    pool=[]
    def utf(value):
        value=value.encode();pool.append(b'\x01'+struct.pack('>H',len(value))+value)
        return len(pool)
    def class_entry(value):
        i=utf(value);pool.append(b'\x07'+struct.pack('>H',i));return len(pool)
    this=class_entry(name);parent=class_entry(parent)
    declarations=[]
    for method,access in methods:
        method_i=utf(method);descriptor_i=utf('()V');attributes=b''
        if not access&0x400:
            code=struct.pack('>HHI',0,0 if access&8 else 1,1)+b'\xb1\0\0\0\0'
            attributes=struct.pack('>HI',utf('Code'),len(code))+code
        declarations.append(struct.pack('>HHHH',access,method_i,descriptor_i,bool(attributes))+attributes)
    for owner,method in references:
        owner_i=class_entry(owner);name_i=utf(method);descriptor_i=utf('()V')
        pool.append(b'\x0c'+struct.pack('>HH',name_i,descriptor_i));nt=len(pool)
        pool.append(b'\x0a'+struct.pack('>HH',owner_i,nt))
    return (struct.pack('>IHHH',0xcafebabe,0,65,len(pool)+1)+b''.join(pool)
            +struct.pack('>HHHHH',flags,this,parent,0,0)
            +struct.pack('>H',len(declarations))+b''.join(declarations)+b'\0\0')


def archive(files):
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w') as z:
        for name,data in files.items():z.writestr(name,data)
    return out.getvalue()


def qualification_fixture(tmp_path, candidate='equal', war=False, padding=0):
    lib=tmp_path/'opt/nifi/nifi-current/lib';lib.mkdir(parents=True)
    cache=tmp_path/'cache';cache.mkdir()
    owner='com/fasterxml/jackson/core/Target';stable='com/fasterxml/jackson/core/Stable'
    old=archive({owner+'.class':classfile(owner,[('read',0x401)]),
                 stable+'.class':classfile(stable,[('stable',0x401)])})
    target=classfile(owner,[('read',0x401)])
    if candidate=='removed-member':target=classfile(owner)
    if candidate=='inaccessible-member':target=classfile(owner,[('read',0)])
    if candidate=='static-instance-change':target=classfile(owner,[('read',0x9)])
    if candidate=='inaccessible-class':target=classfile(owner,[('read',0x401)],flags=0x420)
    fixed_files={stable+'.class':classfile(stable,[('stable',0x401)])}
    if candidate!='missing-class':fixed_files[owner+'.class']=target
    fixed=archive(fixed_files);empty=archive({})
    pins={}
    for name,data in [('jackson-core-2.22.2.jar',old),('jackson-core-2.22.3.jar',fixed),
                      ('jackson-databind-2.22.3.jar',empty)]:
        pins[name]={'sha256':q.sha(data)}
        (cache/name).write_bytes(data)
    for relative in ('lib/bootstrap','../nifi-toolkit-current/lib'):
        dest=tmp_path/'opt/nifi/nifi-current'/relative;dest.mkdir(parents=True,exist_ok=True)
        for name in ('jackson-core-2.22.3.jar','jackson-databind-2.22.3.jar'):
            (dest/name).write_bytes((cache/name).read_bytes())
    def nar(nar_id, files, parent=None):
        text='Nar-Id: '+nar_id+'\n'
        if parent:text+='Nar-Dependency-Id: '+parent+'\n'
        (lib/(nar_id+'.nar')).write_bytes(archive({'META-INF/MANIFEST.MF':text.encode(),**files}))
    nar('nifi-jetty-nar',{})
    nar('nifi-framework-nar',{q.BUNDLE+'jackson-core-2.22.2.jar':old})
    consumer='org/apache/nifi/web/api/FlowResource' if war else 'org/apache/nifi/amqp/processors/ConsumeAMQP'
    consumer_bytes=classfile(consumer,references=[(owner,'read'),(stable,'stable')])
    nar_id='nifi-server-nar' if war else 'nifi-amqp-nar'
    war_path=q.BUNDLE+'web-api.war'
    files={q.BUNDLE+'app.jar':archive({consumer+'.class':consumer_bytes})}
    if war:files={war_path:archive({'WEB-INF/classes/'+consumer+'.class':consumer_bytes})}
    if padding:files[q.BUNDLE+'unused-resource.bin']=b'x'*padding
    nar(nar_id,files,'nifi-framework-nar')
    return tmp_path,cache,pins,nar_id,war_path,consumer


def test_inventory_covers_inherited_only_war_and_implicit_jetty_parent(tmp_path):
    root,_,pins,nar_id,war_path,_=qualification_fixture(tmp_path,war=True)
    inv=q.inventory(root,pins)
    assert {'id':nar_id,'war':war_path} in inv['contexts']
    rows={r['manifest']['Nar-Id']:r for r in inv['roots']}
    assert rows[nar_id]['occurrences']==[]
    assert rows[nar_id]['parents']==['nifi-framework-nar','nifi-jetty-nar']
    assert rows['nifi-jetty-nar']['parents']==[]
    assert inv['replacement'] is None and inv['runtime_approved'] is False
    assert inv['promotion_eligible'] is False


def test_historical_inventory_cannot_silently_reuse_missing_war_coverage(tmp_path):
    root,cache,pins,nar_id,_,_=qualification_fixture(tmp_path)
    inv=q.inventory(root,pins)
    inv.pop('inventory_schema')
    with pytest.raises(ValueError,match='obsolete inventory; regenerate WAR and Jetty coverage'):
        q.analyze(root,inv,{'id':nar_id,'war':None},cache,pins)


@pytest.mark.parametrize('broken',['equal','removed-member','inaccessible-member',
                                   'static-instance-change','inaccessible-class','missing-class'])
def test_analyze_real_archives_classifies_differential_and_preserves_guards(tmp_path,broken):
    root,cache,pins,nar_id,_,consumer=qualification_fixture(tmp_path,candidate=broken)
    inv=q.inventory(root,pins)
    result=q.analyze(root,inv,{'id':nar_id,'war':None},cache,pins)
    assert result['minimum_known_consumers_verified']==[consumer]
    assert consumer in result['external_target_consumers']
    assert result['negative_controls']
    assert result['preexisting_unresolved']==[]
    assert result['source_before']==result['source_after']
    assert result['replacement'] is None and result['runtime_approved'] is False
    assert result['promotion_eligible'] is False
    if broken=='equal':
        assert result['regressions']==[]
        assert result['status']=='component-static-no-new-reference-regressions'
    else:
        expected='missing-member' if broken=='removed-member' else broken
        assert any(r['consumer']==consumer and r['old'] is None and r['new']==expected
                   for r in result['regressions'])
        assert result['status']=='component-static-regressions'


def test_analyze_scans_web_inf_classes_and_marks_war_model_provisional(tmp_path):
    root,cache,pins,nar_id,war_path,consumer=qualification_fixture(tmp_path,war=True)
    inv=q.inventory(root,pins)
    result=q.analyze(root,inv,{'id':nar_id,'war':war_path},cache,pins)
    assert consumer in result['external_target_consumers']
    assert result['external_target_consumers'][consumer]['jar']=='WEB-INF/classes/'
    assert result['negative_controls'] and not result['regressions']
    assert result['status']=='component-static-war-model-unverified'
    assert result['replacement'] is None and result['runtime_approved'] is False
    assert result['promotion_eligible'] is False


def test_missing_implicit_jetty_fails_closed(tmp_path):
    root,_,pins,_,_,_=qualification_fixture(tmp_path)
    (root/'opt/nifi/nifi-current/lib/nifi-jetty-nar.nar').unlink()
    with pytest.raises(ValueError,match='missing parent nifi-jetty-nar'):q.inventory(root,pins)


def test_explicit_dependency_cycle_fails_closed(tmp_path):
    root,_,pins,_,_,_=qualification_fixture(tmp_path)
    p=root/'opt/nifi/nifi-current/lib/nifi-framework-nar.nar'
    with zipfile.ZipFile(p) as z:files={n:z.read(n) for n in z.namelist()}
    files['META-INF/MANIFEST.MF']=b'Nar-Id: nifi-framework-nar\nNar-Dependency-Id: nifi-amqp-nar\n'
    p.write_bytes(archive(files))
    with pytest.raises(ValueError,match='parent cycle'):q.inventory(root,pins)


def test_analyze_memory_does_not_scale_with_unused_outer_archive_bytes(tmp_path):
    root,cache,pins,nar_id,_,_=qualification_fixture(tmp_path,padding=8*1024**2)
    inv=q.inventory(root,pins)
    tracemalloc.start()
    try:
        result=q.analyze(root,inv,{'id':nar_id,'war':None},cache,pins)
        _,peak=tracemalloc.get_traced_memory()
    finally:tracemalloc.stop()
    assert result['status']=='component-static-no-new-reference-regressions'
    assert peak<4*1024**2, f'unused outer archive retained/decompressed: {peak} bytes'


def rewrite_nar(root,nar_id,files):
    p=root/'opt/nifi/nifi-current/lib'/(nar_id+'.nar')
    with zipfile.ZipFile(p) as z:manifest=z.read('META-INF/MANIFEST.MF')
    p.write_bytes(archive({'META-INF/MANIFEST.MF':manifest,**files}))


def test_inventory_also_keeps_war_with_own_target_without_inherited_target(tmp_path):
    root,cache,pins,nar_id,war_path,consumer=qualification_fixture(tmp_path,war=True)
    rewrite_nar(root,'nifi-framework-nar',{})
    owner='com/fasterxml/jackson/core/Target'
    war=archive({'WEB-INF/lib/jackson-core-2.22.2.jar':(cache/'jackson-core-2.22.2.jar').read_bytes(),
                 'WEB-INF/classes/'+consumer+'.class':classfile(consumer,references=[(owner,'read')])})
    rewrite_nar(root,nar_id,{war_path:war})
    inv=q.inventory(root,pins)
    assert inv['contexts']==[{'id':nar_id,'war':war_path}]
    result=q.analyze(root,inv,inv['contexts'][0],cache,pins)
    assert consumer in result['external_target_consumers']
    assert not result['preexisting_unresolved'] and not result['regressions']


def test_provisional_war_precedence_is_parent_then_classes_then_lib(tmp_path):
    root,cache,pins,nar_id,war_path,consumer=qualification_fixture(tmp_path,war=True)
    owner='com/fasterxml/jackson/core/Target';local='app/LocalAdapter'
    files={'WEB-INF/classes/'+owner+'.class':classfile(owner),
           'WEB-INF/classes/'+local+'.class':classfile(local,[('read',0x401)],parent=owner),
           'WEB-INF/classes/'+consumer+'.class':classfile(consumer,references=[(local,'read')]),
           'WEB-INF/lib/adapter.jar':archive({local+'.class':classfile(local,[('read',0)],parent=owner)})}
    rewrite_nar(root,nar_id,{war_path:archive(files)})
    inv=q.inventory(root,pins)
    result=q.analyze(root,inv,{'id':nar_id,'war':war_path},cache,pins)
    assert not result['preexisting_unresolved'] and not result['regressions']
    assert consumer in result['external_target_consumers']
    duplicates={r['class']:r for r in result['duplicate_class_precedence']}
    assert duplicates[owner]['winner']=='nifi-framework-nar'
    assert duplicates[local]['winner']==nar_id+'!'+war_path
    assert result['status']=='component-static-war-model-unverified'


def test_consumer_analysis_still_rejects_vacuous_and_missing_known_consumer(tmp_path):
    root,cache,pins,nar_id,_,_=qualification_fixture(tmp_path)
    rewrite_nar(root,nar_id,{})
    inv=q.inventory(root,pins)
    with pytest.raises(AssertionError,match='vacuous consumer analysis'):
        q.analyze(root,inv,{'id':nar_id,'war':None},cache,pins)
    other=classfile('app/Other',references=[('com/fasterxml/jackson/core/Target','read')])
    rewrite_nar(root,nar_id,{q.BUNDLE+'other.jar':archive({'app/Other.class':other})})
    inv=q.inventory(root,pins)
    with pytest.raises(AssertionError,match='known actual consumer missing'):
        q.analyze(root,inv,{'id':nar_id,'war':None},cache,pins)


def test_java21_multi_release_selection_survives_archive_reader_change():
    name='app/Versioned'
    data=archive({'META-INF/MANIFEST.MF':b'Multi-Release: true\n',
                  name+'.class':classfile(name,[('base',0x401)]),
                  'META-INF/versions/17/'+name+'.class':classfile(name,[('java17',0x401)]),
                  'META-INF/versions/22/'+name+'.class':classfile(name,[('java22',0x401)])})
    parsed=dict(q.classes(data))
    assert set(parsed[name+'.class']['members'])=={('method','java17','()V')}


def test_fully_broken_target_still_reports_regression_with_baseline_control(tmp_path):
    root,cache,pins,nar_id,_,consumer=qualification_fixture(tmp_path,candidate='missing-class')
    target='com/fasterxml/jackson/core/Target'
    consumer_bytes=classfile(consumer,references=[(target,'read')])
    rewrite_nar(root,nar_id,{q.BUNDLE+'app.jar':archive({consumer+'.class':consumer_bytes})})
    inv=q.inventory(root,pins)
    result=q.analyze(root,inv,{'id':nar_id,'war':None},cache,pins)
    assert result['status']=='component-static-regressions'
    assert any(r['new']=='missing-class' and r['old'] is None for r in result['regressions'])
    assert result['negative_controls'][0]['variant']=='original'
