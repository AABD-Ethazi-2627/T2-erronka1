#!/usr/bin/env python3
"""Read-only actual-image Jackson qualification; never emits an applicable overlay.

Run inside the pinned image using a mounted Python, one bounded phase per context.
The symbolic check overapproximates constant-pool references. Reflection, method
handle lookup modes, bytecode verification and Jetty delegation remain blockers.
"""
import argparse
import hashlib
import io
import json
import re
import zipfile
from contextlib import contextmanager
from pathlib import Path

OLD_NEW = {f'jackson-{a}-{v}.jar': f'jackson-{a}-{n}.jar'
           for v,n in [('2.22.2','2.22.3'),('3.2.2','3.2.3')]
           for a in ('core','databind')}
PREFIXES = ('com/fasterxml/jackson/', 'tools/jackson/')
TARGET_PREFIXES=('com/fasterxml/jackson/core/','com/fasterxml/jackson/databind/','tools/jackson/core/','tools/jackson/databind/')
BUNDLE='META-INF/bundled-dependencies/'
INVENTORY_SCHEMA=2
JDK_CLASSES=None
JDK_INPUTS={}
def probe_family(nar_id):
    return '3' if nar_id in ('nifi-jolt-nar','nifi-standard-nar') else '2'
def sha(b): return hashlib.sha256(b).hexdigest()
def stream_sha(stream):
    digest=hashlib.sha256()
    for block in iter(lambda:stream.read(1024**2),b''):digest.update(block)
    return digest.hexdigest()
def file_sha(path):
    with Path(path).open('rb') as stream:return stream_sha(stream)
def save(p,x): Path(p).write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')
def manifest(b):
    text=b.decode('utf8').replace('\r\n','\n').replace('\n ','')
    return dict(line.split(': ',1) for line in text.splitlines() if ': ' in line)
def entries(data):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for n in jar_names(z):yield n,z.read(n)
def archive_names(z):
    names=z.namelist()
    if len(names)!=len(set(names)):raise ValueError('duplicate archive names')
    return sorted(names)
def jar_names(z):
    return [n for n in archive_names(z) if n.endswith('.jar') and n.startswith((BUNDLE,'WEB-INF/lib/'))]
@contextmanager
def container(path,war=None):
    # ZipExtFile supplies a seekable view without retaining the whole outer NAR
    # or WAR. Planning reads names only; payloads are read one JAR/class at a time.
    with zipfile.ZipFile(path) as outer:
        if war:
            with outer.open(war) as stream,zipfile.ZipFile(stream) as inner:yield inner
        else:yield outer
def classes(data):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        yield from archive_classes(z)
def archive_classes(z,prefix=''):
    names=archive_names(z)
    mr=not prefix and b'Multi-Release: true' in z.read('META-INF/MANIFEST.MF') if 'META-INF/MANIFEST.MF' in names else False
    chosen={}
    for n in names:
        if not n.startswith(prefix) or not n.endswith('.class'):continue
        ver=0;base=n[len(prefix):]
        if base.startswith('META-INF/versions/'):
            if not mr:continue
            _,_,v,base=base.split('/',3);ver=int(v)
            if ver>21:continue
        if base=='module-info.class':continue
        if base not in chosen or chosen[base][0]<ver:chosen[base]=(ver,n)
    for base,(_,n) in chosen.items():yield base,parse(z.read(n))
def parse(b):
    s=io.BytesIO(b)
    def u(n):
        x=s.read(n)
        if len(x)!=n:raise ValueError('truncated class')
        return int.from_bytes(x,'big')
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
    def cls(i):return cp[cp[i][1]]
    refs=set()
    for x in cp:
        if isinstance(x,tuple) and x[0]==7:
            name=cp[x[1]]
            if name.startswith('['):refs.update((v,'','','class') for v in re.findall(r'L([^;]+);',name))
            else:refs.add((name,'','','class'))
        if isinstance(x,str):refs.update((v,'','','descriptor') for v in re.findall(r'L([^;<>]+)[;<]',x))
        if isinstance(x,tuple) and x[0] in (9,10,11):
            nt=cp[x[2]];refs.add((cls(x[1]),cp[nt[1]],cp[nt[2]],'field' if x[0]==9 else 'method'))
    access=u(2);name=cls(u(2));sup=u(2)
    parents=([cls(sup)] if sup else [])+[cls(u(2)) for _ in range(u(2))]
    members={}
    def attrs():
        for _ in range(u(2)):u(2);s.seek(u(4),1)
    for kind in ('field','method'):
        for _ in range(u(2)):
            flags=u(2);n=cp[u(2)];d=cp[u(2)];members[(kind,n,d)]=flags;attrs()
    nest=name;nest_members=[]
    for _ in range(u(2)):
        aname=cp[u(2)];length=u(4);end=s.tell()+length
        if aname=='NestHost':nest=cls(u(2))
        elif aname=='NestMembers':nest_members=[cls(u(2)) for _ in range(u(2))]
        s.seek(end)
    return {'name':name,'flags':access,'parents':parents,'members':members,'refs':refs,'major':major,'nest_host':nest,'nest_members':nest_members}
def ensure_jdk(name,index):
    if name in index or JDK_CLASSES is None:return
    if not name.startswith(('java/','javax/','jdk/','sun/')):return
    p=JDK_CLASSES/(name+'.class')
    if p.is_file():
        b=p.read_bytes();c=parse(b);c.pop('refs');c['loader']='bootstrap-jdk21';index[name]=c;JDK_INPUTS[name]=sha(b)
def ancestors(name,index,seen=None):
    seen=set() if seen is None else seen
    if name in seen:return seen
    seen.add(name)
    ensure_jdk(name,index)
    for p in index.get(name,{}).get('parents',[]):ancestors(p,index,seen)
    return seen

def resolve(owner,key,index,seen=None):
    seen=set() if seen is None else seen
    ensure_jdk(owner,index)
    if owner in seen or owner not in index:return None
    seen.add(owner);c=index[owner]
    if key in c['members']:return owner,c['members'][key]
    if key[1]=='<init>':return None
    ps=c['parents']
    # JVMS field resolution searches interfaces before superclass.
    if key[0]=='field' and ps:ps=ps[1:]+ps[:1]
    for p in ps:
        r=resolve(p,key,index,seen)
        if r:return r
    return None

def access(owner,flags,consumer,index):
    if flags&1:return True
    # Same textual package is insufficient across different defining NAR loaders.
    if flags&2:
        if owner==consumer:return True
        a,b=index.get(owner,{}),index.get(consumer,{})
        host=a.get('nest_host',owner);h=index.get(host,{})
        members={host,*h.get('nest_members',[])}
        return host==b.get('nest_host',consumer) and owner in members and consumer in members and a.get('loader')==b.get('loader')
    same=(owner.rpartition('/')[0]==consumer.rpartition('/')[0]
          and index.get(owner,{}).get('loader')==index.get(consumer,{}).get('loader'))
    return same or bool(flags&4 and owner in ancestors(consumer,index))
def check(ref,consumer,index):
    owner,n,d,kind=ref
    if owner not in index:return ('missing-class',None)
    c=index[owner]
    if not access(owner,c['flags'],consumer,index):return ('inaccessible-class',None)
    if kind in ('class','descriptor'):return (None,None)
    r=resolve(owner,(kind,n,d),index)
    if r is None:return ('missing-member',None)
    if not access(r[0],r[1],consumer,index):return ('inaccessible-member',r)
    return (None,r)

def inventory(root,pins):
    base=root/'opt/nifi/nifi-current/lib';rows=[];ids={}
    for p in sorted(base.glob('*.nar')):
        with container(p) as z:
            m=manifest(z.read('META-INF/MANIFEST.MF'))
            row={'path':str(p.relative_to(root)),'sha256':file_sha(p),'manifest':m,'occurrences':[],'wars':[]}
            for n in jar_names(z):
                if Path(n).name in OLD_NEW:
                    old=Path(n).name
                    with z.open(n) as stream:oldhash=stream_sha(stream)
                    assert oldhash==pins[old]['sha256']
                    row['occurrences'].append({'chain':[n],'old':old,'old_sha256':oldhash,'fixed':OLD_NEW[old],'fixed_sha256':pins[OLD_NEW[old]]['sha256']})
            for n in archive_names(z):
                if n.startswith(BUNDLE) and n.endswith('.war'):
                    with z.open(n) as stream:warhash=stream_sha(stream)
                    row['wars'].append({'path':n,'sha256':warhash})
                    with container(p,n) as war:
                        for k in jar_names(war):
                            if Path(k).name in OLD_NEW:
                                old=Path(k).name
                                with war.open(k) as stream:oldhash=stream_sha(stream)
                                assert oldhash==pins[old]['sha256']
                                row['occurrences'].append({'chain':[n,k],'old':old,'old_sha256':oldhash,'fixed':OLD_NEW[old],'fixed_sha256':pins[OLD_NEW[old]]['sha256']})
        warhashes={w['path']:w['sha256'] for w in row['wars']}
        for occurrence in row['occurrences']:
            occurrence['carrier_chain']=[{'path':row['path'],'sha256':row['sha256']}]
            occurrence['full_path']=row['path']+'!'+ '!'.join(occurrence['chain'])
            if len(occurrence['chain'])==2:
                warpath=occurrence['chain'][0]
                occurrence['carrier_chain'].append({'path':warpath,'sha256':warhashes[warpath]})
        if m['Nar-Id'] in ids:raise ValueError('duplicate Nar-Id '+m['Nar-Id'])
        ids[m['Nar-Id']]=row;rows.append(row)
    for row in rows:
        chain=[];p=row;seen={row['manifest']['Nar-Id']}
        while True:
            nar_id=p['manifest']['Nar-Id']
            # NarClassLoaders uses Jetty for dependency-free roots; Jetty itself
            # has the system loader as parent (NiFi 2.12.0 bytecode evidence).
            dep=None if nar_id=='nifi-jetty-nar' else p['manifest'].get('Nar-Dependency-Id','nifi-jetty-nar')
            if dep is None:break
            if dep in seen:raise ValueError('parent cycle '+dep)
            if dep not in ids:raise ValueError('missing parent '+dep)
            seen.add(dep);chain.append(dep);p=ids[dep]
        row['parents']=chain
    targets={r['manifest']['Nar-Id'] for r in rows if any(len(o['chain'])==1 for o in r['occurrences'])}
    contexts=[]
    for r in rows:
        affected=bool(targets.intersection([r['manifest']['Nar-Id'],*r['parents']]))
        if affected:contexts.append({'id':r['manifest']['Nar-Id'],'war':None})
        own_wars={o['chain'][0] for o in r['occurrences'] if len(o['chain'])==2}
        for war in r['wars']:
            if affected or war['path'] in own_wars:
                contexts.append({'id':r['manifest']['Nar-Id'],'war':war['path']})
    bootstrap=[]
    for relative in ('opt/nifi/nifi-current/lib/bootstrap','opt/nifi/nifi-toolkit-current/lib'):
        for old,new in OLD_NEW.items():
            if not old.endswith('2.22.2.jar'):continue
            oldpath=root/relative/old;newpath=root/relative/new
            assert not oldpath.exists(),'old bootstrap/toolkit remains'
            assert file_sha(newpath)==pins[new]['sha256']
            bootstrap.append({'old_path':relative+'/'+old,'old_absent':True,'fixed_path':relative+'/'+new,'fixed_sha256':pins[new]['sha256']})
    return {'inventory_schema':INVENTORY_SCHEMA,'already_fixed_bootstrap_toolkit':bootstrap,'image_id':'sha256:03f3e9a19dbce166304ec63a685c44f2da07239e5659d843c798c7f32f7012d5','roots':rows,'contexts':contexts,'replacement':None,'runtime_approved':False,'promotion_eligible':False}

def analyze(root,inv,ctx,cache,pins):
    if inv.get('inventory_schema')!=INVENTORY_SCHEMA:
        raise ValueError('obsolete inventory; regenerate WAR and Jetty coverage')
    rows={r['manifest']['Nar-Id']:r for r in inv['roots']};row=rows[ctx['id']]
    # NAR uses parent-first delegation. WAR uses a provisional parent-first model
    # and cannot pass runtime approval without actual Jetty delegation evidence.
    ordered=list(reversed([row]+[rows[x] for x in row['parents']]))
    before={};jars=[]
    for p in sorted((root/'opt/nifi/nifi-current/lib').glob('*.jar')):
        before[str(p.relative_to(root))]=file_sha(p);jars.append(('system',p.name,(p,'TOP')))
    for r in ordered:
        p=root/r['path'];digest=file_sha(p);assert digest==r['sha256'];before[r['path']]=digest
        with container(p) as z:
            jars.extend((r['manifest']['Nar-Id'],n,(p,None)) for n in jar_names(z))
    if ctx['war']:
        loader=ctx['id']+'!'+ctx['war'];loc=(root/row['path'],ctx['war'])
        # Provisional parent-first WAR model: inherited NARs first, then the
        # WAR's classes directory, then sorted WEB-INF/lib JARs. This ordering
        # is a static hypothesis, not evidence of actual Jetty delegation.
        jars.append((loader,'WEB-INF/classes/',loc))
        with container(*loc) as z:jars.extend((loader,n,loc) for n in jar_names(z))
    indexes=[{},{}];own=[];inputs=[];duplicates=[]
    def readjar(n,loc):
        if loc[1]=='TOP':return Path(loc[0]).read_bytes()
        with container(*loc) as z:return z.read(n)
    def source_classes(n,loc):
        if n=='WEB-INF/classes/':
            with container(*loc) as z:yield from archive_classes(z,n)
        else:yield from classes(readjar(n,loc))
    for loader,n,loc in jars:
        directory=n=='WEB-INF/classes/'
        b=None if directory else readjar(n,loc)
        name=Path(n).name;replacement=None
        if name in OLD_NEW:
            assert sha(b)==pins[name]['sha256'];replacement=(cache/OLD_NEW[name]).read_bytes();assert sha(replacement)==pins[OLD_NEW[name]]['sha256']
        if directory:
            with container(loc[0]) as z,z.open(loc[1]) as stream:digest=stream_sha(stream)
            inputs.append({'loader':loader,'path':n,'sha256':digest,'hash_scope':'containing-war','fixed_sha256':None})
        else:inputs.append({'loader':loader,'path':n,'sha256':sha(b),'fixed_sha256':sha(replacement) if replacement else None})
        for v,blob in enumerate((b,replacement) if replacement is not None else (b,)):
            for _,c in source_classes(n,loc) if directory else classes(blob):
                c.pop('refs');c['loader']=loader
                if c['name'] in indexes[v]:
                    if v==0:duplicates.append({'class':c['name'],'winner':indexes[v][c['name']]['loader'],'shadowed':loader})
                    continue
                indexes[v][c['name']]=c
                if replacement is None and c['name'] not in indexes[1]:indexes[1][c['name']]=c
        # Check every consumer of the effective classpath, not only a hand-picked smoke class.
        if replacement is None:own.append((loader,n,loc))
        del b,replacement,blob
    abi=[]
    for name,old in indexes[0].items():
        if not name.startswith(PREFIXES):continue
        new=indexes[1].get(name)
        if new is None:abi.append({'class':name,'change':'removed-class'});continue
        if old['flags']!=new['flags'] or old['parents']!=new['parents']:
            abi.append({'class':name,'change':'access-or-hierarchy','old_flags':old['flags'],'new_flags':new['flags'],'old_parents':old['parents'],'new_parents':new['parents']})
        for key,flags in old['members'].items():
            found=resolve(name,key,indexes[1])
            if found is None:abi.append({'class':name,'member':key,'change':'removed-member-including-inheritance'})
            elif flags!=found[1]:abi.append({'class':name,'member':key,'change':'member-flags','old':flags,'new':found[1]})
    count=refs=target_refs=0;consumers={};external_target_consumers={};regressions=[];baseline=[];symbol_counts={}
    controls=[]
    for loader,n,loc in own:
        for _,c in source_classes(n,loc):
            count+=1;checked=0
            for ref in c['refs']:
                owner=ref[0]
                if not (owner.startswith(PREFIXES) or any(x.startswith(PREFIXES) for x in ancestors(owner,indexes[0]))):continue
                refs+=1;checked+=1;symbol_counts[owner]=symbol_counts.get(owner,0)+1
                target=owner.startswith(TARGET_PREFIXES) or any(x.startswith(TARGET_PREFIXES) for x in ancestors(owner,indexes[0]))
                external=not c['name'].startswith(PREFIXES)
                if target:target_refs+=1
                if target and external:external_target_consumers[c['name']]={'jar':n,'loader':loader}
                old,om=check(ref,c['name'],indexes[0]);new,nm=check(ref,c['name'],indexes[1])
                issue={'consumer':c['name'],'jar':n,'loader':loader,'reference':ref,'old':old,'new':new}
                if old:baseline.append(issue)
                elif new:regressions.append(issue)
                if not old and not controls and target and external and owner.startswith(TARGET_PREFIXES):
                    # A wholly broken candidate must still produce a regression
                    # report. Its valid original reference supplies the control.
                    variant=0 if new else 1
                    poisoned=dict(indexes[variant]);poisoned.pop(owner)
                    detected,_=check(ref,c['name'],poisoned)
                    assert detected=='missing-class'
                    controls.append({'consumer':c['name'],'reference':ref,'removed_owner':owner,'detected':detected,'variant':'fixed' if variant else 'original'})
                if not old and not new and om and nm and (om[1]&8)!=(nm[1]&8):issue['new']='static-instance-change';regressions.append(issue)
            if checked:consumers[c['name']]={'jar':n,'references':checked,'loader':loader}
    after={p:file_sha(root/p) for p in before};assert before==after
    assert refs>0 and consumers,'vacuous consumer analysis'
    expected={'nifi-amqp-nar':{'org/apache/nifi/amqp/processors/ConsumeAMQP'},'nifi-jolt-nar':{'io/joltcommunity/jolt/JsonUtils','org/apache/nifi/processors/jolt/JoltTransformJSON'}}.get(ctx['id'],set())
    assert expected.issubset(external_target_consumers),'known actual consumer missing'
    assert not external_target_consumers or controls,'no non-vacuous external target control'
    return {'context':ctx,'source_before':before,'source_after':after,'minimum_known_consumers_verified':sorted(expected),'external_target_consumers':external_target_consumers,'target_symbolic_references_checked':target_refs,'effective_jackson_abi_changes':abi,'jdk_api_inputs':JDK_INPUTS,'jars':inputs,'negative_controls':controls,'consumer_classes_scanned':count,'jackson_symbolic_references_checked':refs,'consumer_classes_with_references':consumers,'referenced_owners':symbol_counts,'regressions':regressions,'preexisting_unresolved':baseline,'duplicate_class_precedence':duplicates,'replacement':None,'runtime_approved':False,'promotion_eligible':False,'status':('component-static-regressions' if regressions else ('component-static-war-model-unverified' if ctx['war'] else ('component-static-no-external-target-consumer-evidence' if not external_target_consumers else 'component-static-no-new-reference-regressions'))),'limits':['constant-pool overapproximation, including descriptors and Java21 effective multi-release entries','inheritance and access checked; JVM verification, dynamic linkage, reflection and method-handle access modes not proven','NAR parent-first topology includes implicit Jetty root; WAR parent-first/classes-before-lib model remains unverified against Jetty','all final-image, Maven family guard, independent QA and runtime acceptance gates remain required']}

def main():
    global JDK_CLASSES
    import resource
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    resource.setrlimit(resource.RLIMIT_AS,(400*1024**2,400*1024**2))
    p=argparse.ArgumentParser();p.add_argument('--jdk-classes',type=Path);p.add_argument('mode',choices=['inventory','analyze']);p.add_argument('--root',type=Path,default=Path('/'));p.add_argument('--pins',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--inventory',type=Path);p.add_argument('--context',type=int);p.add_argument('--cache',type=Path);a=p.parse_args()
    JDK_CLASSES=a.jdk_classes
    pins={r['file']:r for r in json.loads(a.pins.read_text())}
    if a.mode=='inventory':result=inventory(a.root,pins)
    else:
        inv=json.loads(a.inventory.read_text());result=analyze(a.root,inv,inv['contexts'][a.context],a.cache,pins)
    save(a.output,result)
if __name__=='__main__':main()
