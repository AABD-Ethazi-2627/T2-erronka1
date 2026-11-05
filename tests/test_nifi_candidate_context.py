"""Candidate-layer provenance, exact scope and all-before-write guards."""
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
def context(tmp_path):
    source=tmp_path/'source';library=source/c.SCOPES[0];library.mkdir(parents=True)
    original=jar([('Code.class',b'synthetic original')])
    fixed=jar([('Code.class',b'synthetic fixed')])
    outer=library/'demo.nar';outer.write_bytes(jar([('inner.jar',original),('keep',b'preserve')]))
    replacement=tmp_path/'replacement.jar';replacement.write_bytes(fixed)
    rows=c.writer.inventory(source)
    inv={'schema':1,'inventory_sha256':c.writer.inventory_hash(rows),'occurrences':rows}
    leaf=next(r for r in rows if r['members'])
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
