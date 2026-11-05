"""Conservative direct constant-pool checks, including wrapper-owned classes.

This does not resolve inherited/interface members, reflection or classloaders.
Missing symbols remain an integration block even with no direct reference.
"""
import argparse
import io
from pathlib import Path

from prepare import entries, save, sha


def parse(b, include_surface=False):
    s=io.BytesIO(b)
    def u(n):
        v=s.read(n)
        if len(v)!=n:raise ValueError('truncated class')
        return int.from_bytes(v,'big')
    if u(4)!=0xcafebabe:raise ValueError('class magic')
    u(2);major=u(2);cp=[None]*u(2);i=1
    while i<len(cp):
        t=u(1)
        if t==1:cp[i]=s.read(u(2)).decode('utf8','replace')
        elif t in (7,8,16,19,20):cp[i]=(t,u(2))
        elif t in (9,10,11,12,17,18):cp[i]=(t,u(2),u(2))
        elif t in (3,4):u(4)
        elif t in (5,6):u(8);i+=1
        elif t==15:cp[i]=(t,u(1),u(2))
        else:raise ValueError('constant tag '+str(t))
        i+=1
    def klass(i):return cp[cp[i][1]]
    refs=[]
    import re
    for x in cp:
        if isinstance(x,tuple) and x[0]==7:
            refs.append((cp[x[1]],"","","class"))
        if isinstance(x,str):
            for type_name in re.findall(r"L([^;<>]+)[;<]",x):
                refs.append((type_name,"","","descriptor"))
    for x in cp:
        if isinstance(x,tuple) and x[0] in (9,10,11):
            nt=cp[x[2]];refs.append((klass(x[1]),cp[nt[1]],cp[nt[2]],'field' if x[0]==9 else 'method'))
    access=u(2);name=klass(u(2));sup=u(2)
    hierarchy=(klass(sup) if sup else "",tuple(klass(u(2)) for _ in range(u(2))))
    surface={}
    def attrs():
        for _ in range(u(2)):u(2);s.seek(u(4),1)
    members=set()
    for kind in ('field','method'):
        for _ in range(u(2)):
            flags=u(2);n=cp[u(2)];d=cp[u(2)];members.add((name,n,d,kind));surface[(kind,n,d)]=flags;attrs()
    result=(name,members,refs)
    return (*result,{"access":access,"hierarchy":hierarchy,"major":major,"members":surface}) if include_surface else result

def analyze(original,candidate,consumers=()):
    old,new=entries(original),entries(candidate)
    oa={n:parse(b,True) for n,b in old.items() if n.endswith('.class') and not n.startswith('META-INF/')}
    na={n:parse(b,True) for n,b in new.items() if n.endswith('.class') and not n.startswith('META-INF/')}
    removed_classes={x[0] for n,x in oa.items() if n not in na}
    removed_members=set()
    for n,x in oa.items():
        if n in na:removed_members.update(x[1]-na[n][1])
    changes=[]
    for n,x in oa.items():
        if n not in na:continue
        a,b=x[3],na[n][3]
        if a['hierarchy']!=b['hierarchy'] or a['access']!=b['access']:
            changes.append({'class':n,'old_header':a['hierarchy'],'new_header':b['hierarchy'],'old_access':a['access'],'new_access':b['access']})
        for key,flags in a['members'].items():
            if key in b['members'] and flags!=b['members'][key]:
                changes.append({'class':n,'member':key,'old_flags':flags,'new_flags':b['members'][key]})
    surviving_references=[];external_count=0
    candidates=list(na.items())
    consumer_hashes={}
    for path in consumers:
        data=entries(path);consumer_hashes[str(path)]=sha(Path(path).read_bytes())
        for n,b in data.items():
            if n.endswith('.class') and not n.startswith('META-INF/'):
                candidates.append((str(path)+'!/'+n,parse(b)))
    for n,x in candidates:
        external_count+=1
        for r in x[2]:
            if r[0] in removed_classes or r in removed_members:
                surviving_references.append({'class':n,'reference':r})
    return {'original_sha256':sha(Path(original).read_bytes()),'candidate_sha256':sha(Path(candidate).read_bytes()),
      'access_or_hierarchy_changes':changes,'consumer_hashes':consumer_hashes,
      'removed_classes':sorted(removed_classes),'removed_members':sorted(removed_members),
      'base_classes_checked_including_changed_wrapper_and_consumers':external_count,'direct_references_to_removed_symbols':surviving_references,
      'runtime_approved':False,'limits':['direct symbolic references only','no inherited member resolution','no reflective/resource/classloader proof','multi-release entries excluded from this base-class analysis'],
      'status':'blocked-full-linkage-and-runtime-pending'}
if __name__=='__main__':
    import json

    from prepare import HERE, OLD, checked, require, source_files
    p=argparse.ArgumentParser();p.add_argument('--cache',type=Path,required=True);p.add_argument('--proof',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    summary=json.loads((a.proof/'summary.json').read_text());candidate=a.proof/summary['candidate']
    require(Path(summary['candidate']).name==summary['candidate'],'unsafe candidate name')
    checked(a.cache/'parquet-jackson-1.18.1.jar',OLD);checked(candidate,summary['candidate_sha256'])
    require(source_files()==summary['source'],'linkage source mismatch')
    pins=json.loads((HERE/'consumer-pins.json').read_text())
    for r in pins:checked(a.cache/r['file'],r['sha256'])
    consumers=[a.cache/r['file'] for r in pins if r['file'].startswith('parquet-') and r['file'].endswith('.jar') and not r['file'].endswith('-sources.jar')]
    result=analyze(a.cache/'parquet-jackson-1.18.1.jar',candidate,consumers)
    for r in pins:checked(a.cache/r['file'],r['sha256'])
    checked(candidate,summary['candidate_sha256']);require(source_files()==summary['source'],'linkage source drift')
    save(a.output,result)
    if result['direct_references_to_removed_symbols']:raise SystemExit('direct consumer references remain')
