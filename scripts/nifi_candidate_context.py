"""Prepare/verify an explicit candidate overlay; never runtime acceptance.

Docker receives only this tool, the writer, and a named immutable build context.
Every input is checked before installing any archive into a disposable layer.
"""
from __future__ import annotations

import argparse
import json
import os
import resource
import shutil
from pathlib import Path

try:
    from scripts import patch_nested_jars as writer
except ModuleNotFoundError:
    import patch_nested_jars as writer

METADATA = {'manifest.json','inventory.json','candidate.json','plan.json','review.json'}
SCOPES = ('opt/nifi/nifi-current/lib','opt/nifi/nifi-toolkit-current/lib')
BOOTSTRAP = {
    scope+'/'+name+'-2.22.2.jar':(scope+'/'+name+'-2.22.3.jar',digest)
    for scope in ('opt/nifi/nifi-current/lib/bootstrap','opt/nifi/nifi-toolkit-current/lib')
    for name,digest in (
        ('jackson-core','8a501126a385b25841915d839508f8a66e2a0dbc8a6709d055ef3b3e852b094c'),
        ('jackson-databind','556db5439e206114346043f68d200497dc96a0bca62a360a81784092ebd0e0a9'))
}


def load(path):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('duplicate context JSON key')
            result[key]=value
        return result
    return json.loads(writer.regular(path).read_text(),object_pairs_hook=pairs)


def require(condition,message):
    if not condition:raise ValueError(message)


def verify(context,source,install=False):
    context,source=Path(context).absolute(),Path(source).absolute()
    manifest=load(context/'manifest.json')
    writer.exact_keys(manifest,'schema inventory_sha256 candidate_sha256 plan_sha256 review_sha256 files')
    require(type(manifest['schema']) is int and manifest['schema']==1,'invalid context schema')
    candidate,plan,review,inv=(load(context/name) for name in ('candidate.json','plan.json','review.json','inventory.json'))
    for name in ('candidate','plan','review'):
        require(writer.digest(context/(name+'.json'))==manifest[name+'_sha256'],'context metadata drift: '+name)
    require(writer.digest(context/'candidate.json')==review.get('candidate_sha256'),'review candidate drift')
    writer.exact_keys(review,'candidate_sha256 families decision review_reference')
    require(review['decision']=='approved' and isinstance(review['review_reference'],str)
            and review['review_reference'].strip(),'missing candidate assembly review')
    require(isinstance(review['families'],list) and review['families']
            and all(isinstance(f,str) for f in review['families'])
            and len(set(review['families']))==len(review['families']),'invalid reviewed families')
    writer.exact_keys(plan,'schema inventory_sha256 targets')
    require(type(plan['schema']) is int and plan['schema']==1,'invalid plan schema')
    require(writer.inventory_hash(inv['occurrences'])==inv['inventory_sha256']
            ==plan['inventory_sha256']==manifest['inventory_sha256'],'context inventory drift')
    selected=[t for t in candidate['targets'] if t['family'] in review['families']]
    require(selected and {t['family'] for t in selected}==set(review['families']),'missing reviewed family')
    projection=[{k:t[k] for k in ('outer','members','chain_sha256','replacement',
                'replacement_sha256','expected_occurrences')}|{'status':'approved-exact-occurrence'} for t in selected]
    require(all(t['status']=='candidate-pending-parent-QA' for t in selected)
            and plan['targets']==projection,'unreviewed plan projection')
    keys=[(t['outer'],tuple(t['members'])) for t in plan['targets']]
    require(len(set(keys))==len(keys),'duplicate candidate target')
    rows={(r['outer'],tuple(r['members'])):r for r in inv['occurrences']}
    require(len(rows)==len(inv['occurrences']),'duplicate inventory occurrence')
    roots={outer:r['sha256'] for (outer,members),r in rows.items() if not members}
    for name in roots:
        writer.canonical(name)
        require(any(name.startswith(scope+'/') for scope in SCOPES),'outside inventoried library scope')
    # The default runtime already updates four bootstrap/toolkit Jackson JARs.
    # Accept exactly the complete original or the complete pinned updated set.
    expected_roots=dict(roots)
    if set(BOOTSTRAP)<=set(roots) and not all((source/name).is_file() for name in BOOTSTRAP):
        for old,(new,digest) in BOOTSTRAP.items():
            require(not (source/old).exists(),'partial bootstrap image migration')
            expected_roots.pop(old);expected_roots[new]=digest
    actual_roots={}
    for scope in SCOPES:
        if (source/scope).exists():
            actual_roots.update({p.relative_to(source).as_posix():writer.digest(p) for p in writer.files(source/scope)})
    require(actual_roots==expected_roots,'image library inventory drift')
    for t,key in zip(plan['targets'],keys):
        require(key in rows and rows[key]['chain_sha256']==t['chain_sha256'],'target preimage drift')
        old=rows[key]['sha256']
        occurrences=[k for k,r in rows.items() if r['sha256']==old]
        require(type(t['expected_occurrences']) is int and len(occurrences)==t['expected_occurrences']
                and set(occurrences)<=set(keys),'incomplete context occurrences')
    writer.validate_atomic_targets(inv['occurrences'],plan['targets'])
    outers={t['outer'] for t in plan['targets']}
    require(isinstance(manifest['files'],dict) and set(manifest['files'])==outers,'context payload scope mismatch')
    expected_files=METADATA|{'payload/'+name for name in outers}
    actual=set()
    for p in context.rglob('*'):
        require(not p.is_symlink(),'linked context path')
        if not p.is_dir():
            writer.regular(p);actual.add(p.relative_to(context).as_posix())
    require(actual==expected_files,'extra/missing context files')
    for name,hashes in manifest['files'].items():
        writer.canonical(name)
        require(name.startswith('opt/nifi/') and Path(name).suffix.lower() in writer.EXTENSIONS,'outside NiFi archive scope')
        writer.exact_keys(hashes,'before after')
        require((name,()) in rows and rows[(name,())]['sha256']==hashes['before'],'context root preimage mismatch')
        require(writer.digest(source/name)==hashes['before'],'image base archive drift')
        require(writer.digest(context/'payload'/name)==hashes['after'],'overlay archive drift')
    post=writer.inventory(context/'payload')
    bykey={(r['outer'],tuple(r['members'])):r for r in post}
    for t,key in zip(plan['targets'],keys):
        require(key in bykey and bykey[key]['sha256']==t['replacement_sha256'],'candidate leaf mismatch')
    require(not any(r['sha256'] in {t['chain_sha256'][-1] for t in plan['targets']} for r in post),
            'selected old library survives overlay')
    for outer in outers:
        writer.verify_rewrite(source/outer,context/'payload'/outer,
                              [t for t in plan['targets'] if t['outer']==outer])
    # All guards precede the first image-layer mutation. Source/context are
    # already private Docker COPY snapshots, not writable host bind mounts.
    if install:
        for name,hashes in manifest['files'].items():
            shutil.copyfile(context/'payload'/name,writer.regular(source/name))
            require(writer.digest(source/name)==hashes['after'],'installed candidate drift')
    return {'mode':'installed-candidate-layer' if install else 'verified-candidate-context',
            'archives':len(outers),'targets':len(keys),'runtime_approved':False,'services_started':False}


def prepare(source,overlay,inventory,candidate,plan,review,output):
    source,overlay,output=Path(source).absolute(),Path(overlay).absolute(),Path(output).absolute()
    for path in (source,overlay,output):
        for part in (path,*path.parents):require(not part.is_symlink(),'linked context input/output')
    source,overlay,output=(Path(os.path.abspath(p)) for p in (source,overlay,output))
    require(not output.exists() and not output.is_symlink(),'context output must be fresh')
    for parent in (output.parent,*output.parent.parents):require(not parent.is_symlink(),'linked output parent')
    for original in (source,overlay):
        require(output!=original and original not in output.parents and output not in original.parents,'overlapping context output')
    repository=Path(__file__).resolve().parents[1]
    require(repository!=output and repository not in output.parents and '.m2' not in output.parts,
            'context must be outside repository and shared Maven cache')
    p=load(plan);outers={t['outer'] for t in p['targets']}
    require({f.relative_to(overlay).as_posix() for f in writer.files(overlay)}==outers,'overlay has extra/missing archives')
    output.mkdir()
    for name,path in [('inventory.json',inventory),('candidate.json',candidate),('plan.json',plan),('review.json',review)]:
        shutil.copyfile(writer.regular(path),output/name)
    inv=load(output/'inventory.json');roots={r['outer']:r['sha256'] for r in inv['occurrences'] if not r['members']}
    files={}
    for name in sorted(outers):
        writer.canonical(name);destination=output/'payload'/name
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(writer.regular(overlay/name),destination)
        files[name]={'before':roots[name],'after':writer.digest(destination)}
    manifest={'schema':1,'inventory_sha256':p['inventory_sha256'],'files':files}
    manifest.update({name+'_sha256':writer.digest(output/(name+'.json')) for name in ('candidate','plan','review')})
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return verify(output,source)


def main():
    resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2))
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=['prepare','verify','install'])
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--context',type=Path,required=True)
    for name in ('overlay','inventory','candidate','plan','review'):p.add_argument('--'+name,type=Path)
    a=p.parse_args()
    if a.mode=='prepare':
        require(all(getattr(a,n) is not None for n in ('overlay','inventory','candidate','plan','review')),'missing preparation inputs')
        result=prepare(a.source,a.overlay,a.inventory,a.candidate,a.plan,a.review,a.context)
    else:result=verify(a.context,a.source,a.mode=='install')
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
