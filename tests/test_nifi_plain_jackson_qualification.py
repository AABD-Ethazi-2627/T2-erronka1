"""Non-vacuous guards for inherited-member and NAR package access analysis."""
import importlib.util
from pathlib import Path

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
