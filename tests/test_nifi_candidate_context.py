"""Candidate-layer provenance, exact scope and all-before-write guards."""
import hashlib
import io
import json
import shutil
import zipfile
from pathlib import Path

import pytest

from scripts import nifi_candidate_context as c


def jar(entries):
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w') as z:
        for name,data in entries:z.writestr(name,data)
    return out.getvalue()


@pytest.fixture
def context(tmp_path,monkeypatch):
    source=tmp_path/'source';library=source/c.SCOPES[0];library.mkdir(parents=True)
    original=jar([('Code.class',b'synthetic original')])
    fixed=jar([('Code.class',b'synthetic fixed')])
    outer=library/'demo.nar';outer.write_bytes(jar([('inner.jar',original),('keep',b'preserve')]))
    replacement=tmp_path/'replacement.jar';replacement.write_bytes(fixed)
    rows=c.writer.inventory(source)
    inv={'schema':1,'inventory_sha256':c.writer.inventory_hash(rows),'occurrences':rows}
    monkeypatch.setattr(c,'STOCK_INVENTORY_HASH',inv['inventory_sha256'])
    leaf=next(r for r in rows if r['members'])
    monkeypatch.setattr(c,'REPLACEMENT_PROFILE',{
        leaf['sha256']:('lz4',c.writer.digest(replacement),1)})
    target={k:leaf[k] for k in ('outer','members','chain_sha256')}
    target|={'family':'lz4','status':'candidate-pending-parent-QA','replacement':str(replacement),
             'replacement_sha256':c.writer.digest(replacement),'expected_occurrences':1}
    candidate={'targets':[target],'counts':{'lz4':1},'inventory_sha256':inv['inventory_sha256']}
    candidate_path=tmp_path/'candidate.json';candidate_path.write_text(json.dumps(candidate))
    plan={'schema':1,'inventory_sha256':inv['inventory_sha256'],'targets':[
        {k:v for k,v in target.items() if k!='family'}|{'status':'approved-exact-occurrence'}]}
    review={'candidate_sha256':c.writer.digest(candidate_path),'families':['lz4'],'decision':'approved',
            'review_reference':'Synthetic bounded candidate assembly only; no runtime approval'}
    paths={}
    for name,value in [('inventory',inv),('plan',plan),('review',review)]:
        paths[name]=tmp_path/(name+'.json');paths[name].write_text(json.dumps(value))
    overlay=tmp_path/'overlay';c.writer.patch(source,overlay,plan,apply=True)
    output=tmp_path/'context'
    result=c.prepare(source,overlay,paths['inventory'],candidate_path,paths['plan'],paths['review'],output)
    assert result['runtime_approved'] is False and result['services_started'] is False
    return source,output,outer,original,fixed


def rebind_metadata(context,name,value):
    path=context/(name+'.json');path.write_text(json.dumps(value))
    manifest=c.load(context/'manifest.json');manifest[name+'_sha256']=c.writer.digest(path)
    (context/'manifest.json').write_text(json.dumps(manifest))


def test_verified_install_changes_only_private_candidate_copy(context,tmp_path):
    source,ctx,outer,original,fixed=context
    copy=tmp_path/'candidate-image';shutil.copytree(source,copy)
    result=c.verify(ctx,copy,install=True)
    assert result=={'mode':'installed-candidate-layer','archives':1,'targets':1,
                    'runtime_approved':False,'services_started':False}
    with zipfile.ZipFile(copy/outer.relative_to(source)) as z:
        assert z.read('inner.jar')==fixed and z.read('keep')==b'preserve'
    with zipfile.ZipFile(outer) as z:assert z.read('inner.jar')==original
    with pytest.raises(ValueError,match='inventory drift'):c.verify(ctx,copy,install=True)


@pytest.mark.parametrize('mutation',['extra-file','payload-drift','base-drift','review','unapproved-plan'])
def test_every_failure_precedes_image_mutation(context,mutation):
    source,ctx,outer,_,_=context;before=outer.read_bytes()
    if mutation=='extra-file':(ctx/'planted.py').write_text('not allowed')
    elif mutation=='payload-drift':(ctx/'payload'/outer.relative_to(source)).write_bytes(b'drift')
    elif mutation=='base-drift':outer.write_bytes(b'drift');before=b'drift'
    elif mutation=='review':
        review=c.load(ctx/'review.json');review['decision']='pending';rebind_metadata(ctx,'review',review)
    else:
        plan=c.load(ctx/'plan.json');plan['targets'][0]['status']='pending';rebind_metadata(ctx,'plan',plan)
    with pytest.raises(ValueError):c.verify(ctx,source,install=True)
    assert outer.read_bytes()==before


def test_added_uninventoried_archive_is_rejected(context):
    source,ctx,outer,_,_=context
    (outer.parent/'new.jar').write_bytes(jar([('X.class',b'fixture')]))
    with pytest.raises(ValueError,match='image library inventory'):c.verify(ctx,source)


def test_symlink_and_duplicate_json_cannot_hide_context_inputs(context):
    source,ctx,_,_,_=context
    (ctx/'link').symlink_to(ctx/'plan.json')
    with pytest.raises(ValueError,match='linked context'):c.verify(ctx,source)
    (ctx/'link').unlink()
    (ctx/'plan.json').write_text('{"schema":1,"schema":1}')
    with pytest.raises(ValueError,match='duplicate context JSON'):c.verify(ctx,source)


def test_bootstrap_replacements_match_the_default_image_recipe():
    docker=(Path(__file__).resolve().parents[1]/'deploy/images/nifi.Dockerfile').read_text()
    assert len(c.BOOTSTRAP)==4
    for old,(new,digest) in c.BOOTSTRAP.items():
        assert old.endswith('-2.22.2.jar') and new.endswith('-2.22.3.jar')
        assert digest in docker


def test_context_output_cannot_alias_the_original_source(context,tmp_path):
    source,_,_,_,_=context
    other=tmp_path/'other';other.mkdir()
    alias=other/'..'/source.name/'planted'
    with pytest.raises(ValueError,match='overlapping context output'):
        c.prepare(source,tmp_path/'overlay',Path('missing'),Path('missing'),Path('missing'),Path('missing'),alias)
    assert not (source/'planted').exists()


def test_self_consistent_forged_inventory_cannot_replace_the_pinned_stock_profile(context):
    source,ctx,outer,_,_=context;before=outer.read_bytes()
    inv=c.load(ctx/'inventory.json');inv['occurrences'][-1]['class_packages']=['forged']
    new=c.writer.inventory_hash(inv['occurrences']);inv['inventory_sha256']=new
    (ctx/'inventory.json').write_text(json.dumps(inv))
    plan=c.load(ctx/'plan.json');plan['inventory_sha256']=new;rebind_metadata(ctx,'plan',plan)
    candidate=c.load(ctx/'candidate.json');candidate['inventory_sha256']=new
    rebind_metadata(ctx,'candidate',candidate)
    review=c.load(ctx/'review.json');review['candidate_sha256']=c.writer.digest(ctx/'candidate.json')
    rebind_metadata(ctx,'review',review)
    manifest=c.load(ctx/'manifest.json');manifest['inventory_sha256']=new
    (ctx/'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='inventory drift'):c.verify(ctx,source,install=True)
    assert outer.read_bytes()==before


def test_stock_profile_matches_the_audited_occurrence_snapshot():
    path=Path(__file__).resolve().parents[1]/'deploy/images/nifi-patches/stock-occurrences/candidate-plan.json'
    assert c.STOCK_INVENTORY_HASH==json.loads(path.read_text())['inventory_sha256']


def forged_context(tmp_path,monkeypatch,original,fixed,*,signed=False,overlap=False):
    """An untrusted producer assembles JSON/payload without using either guard."""
    source=tmp_path/'source';library=source/c.SCOPES[0];library.mkdir(parents=True)
    entries=[('inner.jar',original),('keep',b'unrelated')]
    if signed:entries.append(('META-INF/signature.SF',b'fixture signature'))
    outer=library/'forged.nar';outer.write_bytes(jar(entries))
    rows=c.writer.inventory(source);inv_hash=c.writer.inventory_hash(rows)
    leaf=next(r for r in rows if r['members']==['inner.jar'])
    new_entries=[(name,fixed if name=='inner.jar' else data) for name,data in entries]
    new_outer=jar(new_entries)
    target={k:leaf[k] for k in ('outer','members','chain_sha256')}
    target|={'family':'lz4','status':'candidate-pending-parent-QA','replacement':'not-accessed-host-path.jar',
             'replacement_sha256':hashlib.sha256(fixed).hexdigest(),'expected_occurrences':1}
    targets=[target]
    profile={leaf['sha256']:('lz4',target['replacement_sha256'],1)}
    families=['lz4']
    if overlap:
        root=next(r for r in rows if not r['members'])
        enclosing={k:root[k] for k in ('outer','members','chain_sha256')}
        enclosing|={'family':'hazelcast','status':'candidate-pending-parent-QA','replacement':'not-accessed-host-path.nar',
                    'replacement_sha256':hashlib.sha256(new_outer).hexdigest(),'expected_occurrences':1}
        targets.append(enclosing);profile[root['sha256']]=('hazelcast',enclosing['replacement_sha256'],1)
        families.append('hazelcast')
    candidate={'targets':targets,'counts':{f:1 for f in families},'inventory_sha256':inv_hash}
    plan={'schema':1,'inventory_sha256':inv_hash,'targets':[
        {k:v for k,v in t.items() if k!='family'}|{'status':'approved-exact-occurrence'} for t in targets]}
    ctx=tmp_path/'context';ctx.mkdir()
    for name,value in [('inventory',{'schema':1,'inventory_sha256':inv_hash,'occurrences':rows}),('candidate',candidate),('plan',plan)]:
        (ctx/(name+'.json')).write_text(json.dumps(value))
    review={'candidate_sha256':c.writer.digest(ctx/'candidate.json'),'families':families,'decision':'approved',
            'review_reference':'self-written producer fixture, never independent QA'}
    (ctx/'review.json').write_text(json.dumps(review))
    relative=outer.relative_to(source).as_posix();payload=ctx/'payload'/relative;payload.parent.mkdir(parents=True);payload.write_bytes(new_outer)
    manifest={'schema':1,'inventory_sha256':inv_hash,'files':{relative:{'before':c.writer.digest(outer),'after':c.writer.digest(payload)}}}
    manifest.update({name+'_sha256':c.writer.digest(ctx/(name+'.json')) for name in ('candidate','plan','review')})
    (ctx/'manifest.json').write_text(json.dumps(manifest))
    monkeypatch.setattr(c,'STOCK_INVENTORY_HASH',inv_hash)
    monkeypatch.setattr(c,'REPLACEMENT_PROFILE',profile)
    return source,ctx,outer


@pytest.mark.parametrize('policy',['blocked-input','signed-ancestor','overlap','blocked-injection','atomic-injection-root','atomic-injection-nested'])
def test_untrusted_context_cannot_bypass_shared_writer_policy(tmp_path,monkeypatch,policy):
    original=jar([('Code.class',b'original')]);fixed=jar([('Code.class',b'fixed')])
    forbidden=jar([('Forbidden.class',b'never permitted')])
    forbidden_hash=hashlib.sha256(forbidden).hexdigest()
    if policy=='blocked-injection':
        monkeypatch.setattr(c.writer,'BLOCKED_INPUTS',{forbidden_hash})
        fixed=jar([('Code.class',b'fixed'),('blocked.jar',forbidden)])
    if policy.startswith('atomic-injection'):
        monkeypatch.setattr(c.writer,'ATOMIC_HADOOP_SNAPPY',{
            '0'*64:{'replacement_sha256':forbidden_hash,'count':1}})
        fixed=forbidden if policy.endswith('root') else jar([('atomic.jar',forbidden)])
    source,ctx,outer=forged_context(tmp_path,monkeypatch,original,fixed,
        signed=policy=='signed-ancestor',overlap=policy=='overlap')
    if policy=='blocked-input':monkeypatch.setattr(c.writer,'BLOCKED_INPUTS',{hashlib.sha256(original).hexdigest()})
    before=outer.read_bytes()
    with pytest.raises(ValueError,match='blocked|signed|overlapping|atomic'):
        c.verify(ctx,source,install=True)
    assert outer.read_bytes()==before


def test_self_written_review_cannot_authorize_a_new_family_or_payload(context):
    source,ctx,outer,_,_=context;before=outer.read_bytes()
    candidate=c.load(ctx/'candidate.json');candidate['targets'][0]['family']='guava'
    rebind_metadata(ctx,'candidate',candidate)
    review=c.load(ctx/'review.json');review['families']=['guava'];review['candidate_sha256']=c.writer.digest(ctx/'candidate.json')
    rebind_metadata(ctx,'review',review)
    with pytest.raises(ValueError,match='frozen assembly profile'):c.verify(ctx,source,install=True)
    assert outer.read_bytes()==before


def test_profile_pins_every_current_component_replacement():
    # Independent literal contract from the reviewed 957916e2 candidate, not
    # values read from the implementation or a mutable local proof cache.
    expected = {'1914fed4ed18999ce98ad844aa5d0b09f31027be329ffd82d861d6f7c6f097c7': ('parquet',
                                                                          'bad77fac2682d5441ce19e498056ddaf948e89739d933d302b5cf66c868344cf',
                                                                          1),
     '241ec66cea8491787f68c3336f069ac463877af50bdb7676cd9d538f1940dc33': ('hazelcast',
                                                                          '3c8e5d805a65ce91e2efe586f50fa1b9c482665f4d96c9e2384f066ea26cae85',
                                                                          1),
     '50485d06037fea3d6e40c968386feeca6338cc9872e25549593ff3eb352cefcc': ('snappy',
                                                                          '35228628442e4b9797681c7cbd3b26594f6da3379159dbd0cb07094ed3aece0d',
                                                                          9),
     '796d8e28ac64e83a47c4c5935a8fecc4682650a04bbdead738ef0f5a3a0e6c46': ('guava',
                                                                          'b530942257fb935f8b2cfaa5f8eb5bd59c555fd8e8d01b8ce98912e077ea606c',
                                                                          7),
     '8a7458657938e9b692224db83aac458c13abd7a59ab75c3d3b08bd2233a646a2': ('lz4',
                                                                          '58c8e0b813960d2a248e050c353baea73139b48a2ffc55382d42c69707e17325',
                                                                          3),
     'dad07af66b59454e71b046a2fce0c0fddb9c522eadd146075e6add82aad86ce6': ('hadoop',
                                                                          'e2ff7c642f17743f0816a941d93714a0ae413203112e6a7d2e5f5bcf876329d2',
                                                                          1)}
    assert c.REPLACEMENT_PROFILE == expected
    assert c.writer.ATOMIC_HADOOP_SNAPPY == {'50485d06037fea3d6e40c968386feeca6338cc9872e25549593ff3eb352cefcc': {'count': 9,
                                                                          'replacement_sha256': '35228628442e4b9797681c7cbd3b26594f6da3379159dbd0cb07094ed3aece0d'},
     'dad07af66b59454e71b046a2fce0c0fddb9c522eadd146075e6add82aad86ce6': {'count': 1,
                                                                          'replacement_sha256': 'e2ff7c642f17743f0816a941d93714a0ae413203112e6a7d2e5f5bcf876329d2'}}
    assert c.writer.BLOCKED_INPUTS == {
        '70d5c152622df6fffbf8836af7833215dc7acdd5d9c881af11b8c0fbf30cdc0a',
        '396d48d93ef5735f2ddef0cf9b3d6968ebd67b64b5cfe753d41c429d3f46a2a1',
        'c23f1dffc08e2c209035f8d22a48edfd83477b629477e9416a5d25e2c116f3f6',
    }


def rebind_inventory(ctx,rows,monkeypatch):
    digest=c.writer.inventory_hash(rows)
    monkeypatch.setattr(c,'STOCK_INVENTORY_HASH',digest)
    (ctx/'inventory.json').write_text(json.dumps({'schema':1,'inventory_sha256':digest,'occurrences':rows}))
    for name in ('candidate','plan'):
        data=c.load(ctx/(name+'.json'));data['inventory_sha256']=digest;rebind_metadata(ctx,name,data)
    review=c.load(ctx/'review.json');review['candidate_sha256']=c.writer.digest(ctx/'candidate.json');rebind_metadata(ctx,'review',review)
    manifest=c.load(ctx/'manifest.json');manifest['inventory_sha256']=digest;(ctx/'manifest.json').write_text(json.dumps(manifest))


def test_rebound_payload_and_self_written_review_cannot_change_frozen_replacement(context,tmp_path):
    source,ctx,outer,_,_=context;before=outer.read_bytes()
    actor=tmp_path/'actor.jar';actor.write_bytes(jar([('Code.class',b'unreviewed replacement')]))
    plan=c.load(ctx/'plan.json');plan['targets'][0]['replacement']=str(actor);plan['targets'][0]['replacement_sha256']=c.writer.digest(actor)
    rebind_metadata(ctx,'plan',plan)
    candidate=c.load(ctx/'candidate.json');candidate['targets'][0].update({k:plan['targets'][0][k] for k in ('replacement','replacement_sha256')})
    rebind_metadata(ctx,'candidate',candidate)
    review=c.load(ctx/'review.json');review['candidate_sha256']=c.writer.digest(ctx/'candidate.json');rebind_metadata(ctx,'review',review)
    payload=ctx/'payload'/outer.relative_to(source)
    c.writer.rewrite(outer,payload,plan['targets'])
    manifest=c.load(ctx/'manifest.json');manifest['files'][outer.relative_to(source).as_posix()]['after']=c.writer.digest(payload)
    (ctx/'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='frozen assembly profile'):c.verify(ctx,source,install=True)
    assert outer.read_bytes()==before


@pytest.mark.parametrize('complete',[False,True])
def test_only_complete_pinned_bootstrap_transition_is_accepted(context,monkeypatch,complete):
    source,ctx,outer,_,_=context;before=outer.read_bytes()
    bootstrap={}
    for index in range(4):
        old=c.SCOPES[1]+f'/bootstrap-old-{index}.jar';new=c.SCOPES[1]+f'/bootstrap-new-{index}.jar'
        data=jar([('Bootstrap.class',f'new-{index}'.encode())]);bootstrap[old]=(new,hashlib.sha256(data).hexdigest())
        oldpath=source/old;oldpath.parent.mkdir(parents=True,exist_ok=True);oldpath.write_bytes(jar([('Bootstrap.class',f'old-{index}'.encode())]))
    monkeypatch.setattr(c,'BOOTSTRAP',bootstrap)
    rebind_inventory(ctx,c.writer.inventory(source),monkeypatch)
    for index,(old,(new,_)) in enumerate(bootstrap.items()):
        if not complete and index==3:continue
        (source/old).unlink();(source/new).write_bytes(jar([('Bootstrap.class',f'new-{index}'.encode())]))
    if complete:
        assert c.verify(ctx,source)['targets']==1
    else:
        with pytest.raises(ValueError,match='partial bootstrap'):c.verify(ctx,source,install=True)
    assert outer.read_bytes()==before


def test_install_verifies_copy_result_before_reporting_success(context,monkeypatch):
    source,ctx,outer,_,_=context
    def corrupt_copy(original,destination):Path(destination).write_bytes(b'simulated failed disk copy')
    monkeypatch.setattr(c.shutil,'copyfile',corrupt_copy)
    with pytest.raises(ValueError,match='installed candidate drift'):c.verify(ctx,source,install=True)
    assert outer.read_bytes()==b'simulated failed disk copy'


def test_cli_arms_and_cancels_wall_deadline_on_timeout(monkeypatch):
    import sys
    alarms=[];handlers=[]
    monkeypatch.setattr(c.resource,'setrlimit',lambda *args:None)
    monkeypatch.setattr(c.os,'sched_getaffinity',lambda pid:{0})
    monkeypatch.setattr(c.os,'sched_setaffinity',lambda *args:None)
    monkeypatch.setattr(c.signal,'signal',lambda number,handler:handlers.append(handler))
    monkeypatch.setattr(c.signal,'alarm',alarms.append)
    monkeypatch.setattr(sys,'argv',['context','verify','--source','unused','--context','unused'])
    def deadline_during_verify(*args):handlers[0](c.signal.SIGALRM,None)
    monkeypatch.setattr(c,'verify',deadline_during_verify)
    with pytest.raises(TimeoutError,match='wall deadline'):c.main()
    assert alarms==[180,0]


def test_plain_sibling_corruption_is_rejected_before_install(context):
    source,ctx,outer,_,_=context;before=outer.read_bytes()
    payload=ctx/'payload'/outer.relative_to(source)
    replacement=io.BytesIO()
    with zipfile.ZipFile(payload) as original, zipfile.ZipFile(replacement,'w') as changed:
        for info in original.infolist():
            changed.writestr(info,b'altered plain sibling' if info.filename=='keep' else original.read(info))
    payload.write_bytes(replacement.getvalue())
    manifest=c.load(ctx/'manifest.json')
    manifest['files'][outer.relative_to(source).as_posix()]['after']=c.writer.digest(payload)
    (ctx/'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='post-write sibling content mismatch'):
        c.verify(ctx,source,install=True)
    assert outer.read_bytes()==before


@pytest.mark.parametrize('field', ['candidate_sha256','plan_sha256','review_sha256'])
def test_each_manifest_metadata_digest_is_checked_independently(context,field):
    source,ctx,outer,_,_=context;before=outer.read_bytes()
    manifest=c.load(ctx/'manifest.json');manifest[field]='0'*64
    (ctx/'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='context metadata drift'):
        c.verify(ctx,source,install=True)
    assert outer.read_bytes()==before


def test_review_must_bind_the_actual_candidate_despite_a_rebound_manifest(context):
    source,ctx,outer,_,_=context;before=outer.read_bytes()
    review=c.load(ctx/'review.json');review['candidate_sha256']='0'*64
    rebind_metadata(ctx,'review',review)
    with pytest.raises(ValueError,match='review candidate drift'):
        c.verify(ctx,source,install=True)
    assert outer.read_bytes()==before


def test_candidate_inventory_identity_is_not_merely_advisory(context):
    source,ctx,outer,_,_=context;before=outer.read_bytes()
    candidate=c.load(ctx/'candidate.json');candidate['inventory_sha256']='0'*64
    rebind_metadata(ctx,'candidate',candidate)
    review=c.load(ctx/'review.json');review['candidate_sha256']=c.writer.digest(ctx/'candidate.json')
    rebind_metadata(ctx,'review',review)
    with pytest.raises(ValueError,match='context inventory drift'):
        c.verify(ctx,source,install=True)
    assert outer.read_bytes()==before


def test_only_the_complete_frozen_profile_is_eligible(context,monkeypatch):
    source,ctx,outer,_,_=context;before=outer.read_bytes()
    monkeypatch.setitem(c.REPLACEMENT_PROFILE,'f'*64,('guava','e'*64,1))
    with pytest.raises(ValueError,match='incomplete frozen assembly profile'):
        c.verify(ctx,source,install=True)
    assert outer.read_bytes()==before


def test_candidate_pending_status_cannot_be_removed_by_rebinding_metadata(context):
    source,ctx,outer,_,_=context;before=outer.read_bytes()
    candidate=c.load(ctx/'candidate.json');candidate['targets'][0]['status']='runtime-approved'
    rebind_metadata(ctx,'candidate',candidate)
    review=c.load(ctx/'review.json');review['candidate_sha256']=c.writer.digest(ctx/'candidate.json')
    rebind_metadata(ctx,'review',review)
    with pytest.raises(ValueError,match='unreviewed plan projection'):
        c.verify(ctx,source,install=True)
    assert outer.read_bytes()==before
