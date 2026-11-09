#!/usr/bin/env python3
"""Download pinned upstream bytes and emit a conditional plan, never patch archives."""
import argparse
import hashlib
import io
import json
import os
import resource
import subprocess
import time
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPORTS = {'image-scan.json': '602ee0ca740c3cd2ca3a9ad2f8b06c74145edd944edafa01f3502eb36d427137',
           'nested-archive-scan.json': 'd06b864d28cd7c3c027bd66098934b3a65ffd482cf346ac235b952e54bfd7c18'}
OBJECTS_SHA256 = 'f11af68b9381ca4b64f341cd3bb4baf82a86cc32499cc46d244d4682b12e9abb'
FAMILIES = {
 'com.google.guava:guava': ('guava', ['33.4.8-jre', '33.6.0-jre', '33.7.1-jre'], '33.7.2-jre'),
 'com.rabbitmq:amqp-client': ('rabbit', ['5.35.0'], '5.37.0'),
 'at.yawk.lz4:lz4-java': ('lz4', ['1.11.2'], '1.11.4'),
 'org.xerial.snappy:snappy-java': ('snappy', ['1.1.10.8'], '1.1.10.9'),
}
NS={'m': 'http://maven.apache.org/POM/4.0.0'}
def require(ok, message="verification failed"):
    if not ok: raise ValueError(message)
def sha(b): return hashlib.sha256(b).hexdigest()
def save(p, value): p.write_text(json.dumps(value, indent=2)+'\n')
def clean_environment():
    return {key:os.environ[key] for key in ('PATH','LANG','LC_ALL','TMPDIR') if key in os.environ}
def limits():
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    # RLIMIT_AS cannot cap JVM RSS (JVM reserves much more virtual memory).
    # Heap/metaspace/code-cache/direct-memory bounds plus single CPU constrain probes.
    resource.setrlimit(resource.RLIMIT_CPU,(60,60))
    os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
def run(cmd, cache, name, timeout=60, expected_timeout=False):
    env=clean_environment()
    try:
        p=subprocess.run(list(map(str,cmd)),capture_output=True,check=False,timeout=timeout,env=env,preexec_fn=limits)
    except subprocess.TimeoutExpired as e:
        (cache/(name+'.log')).write_bytes((e.stdout or b'')+(e.stderr or b'')+b'\nTIMEOUT\n')
        if expected_timeout:
            require(b'ENTERING_EOF_COMMENT_PARSER' in (e.stdout or b''), 'timeout before parser entry')
            return 'expected-timeout'
        raise
    (cache/(name+'.log')).write_bytes(p.stdout+p.stderr)
    if p.returncode or expected_timeout: raise RuntimeError(f'{name}: unexpected exit {p.returncode}; see log')
    return 'passed'

def class_api(data):
    """Classfile public/protected symbolic surface; not a full JVM linkage proof."""
    s=io.BytesIO(data)
    def read(n):
        result=s.read(n)
        require(len(result)==n, 'truncated classfile')
        return result
    def u(n):return int.from_bytes(read(n),'big')
    require(u(4)==0xcafebabe)
    _minor,major=u(2),u(2); n=u(2);cp=[None]*n;i=1
    while i<n:
        tag=u(1)
        if tag==1:cp[i]=read(u(2)).decode('utf8','replace')
        elif tag in (7,8,16,19,20):cp[i]=u(2)
        elif tag in (3,4,9,10,11,12,17,18):read(4)
        elif tag in (5,6):read(8);i+=1
        elif tag==15:read(3)
        else:raise ValueError(f'constant pool {tag}')
        i+=1
    access=u(2);u(2);sup=u(2)
    interfaces=tuple(cp[cp[u(2)]] for _ in range(u(2)))
    def attrs():
        for _ in range(u(2)):u(2);read(u(4))
    members=set()
    for kind in ('field','method'):
        for _ in range(u(2)):
            a,name,desc=u(2),cp[u(2)],cp[u(2)]
            if a&5 and name!='<clinit>':members.add((kind,name,desc,a&0x41d))
            attrs()
    attrs()
    require(s.tell()==len(data), 'trailing classfile data')
    return {'public':bool(access&5), 'major':major, 'header':(access&0x611,cp[cp[sup]] if sup else '',interfaces), 'members':members}
def compare(old,new):
    with zipfile.ZipFile(old) as a,zipfile.ZipFile(new) as b:
        removals=[];count=0
        for n in a.namelist():
            if not n.endswith('.class') or n.startswith('META-INF/'):continue
            x=class_api(a.read(n))
            if not x['public']:continue
            count+=1
            if n not in b.namelist():removals.append(n+': class removed');continue
            y=class_api(b.read(n))
            if not y['public'] or x['header']!=y['header']:removals.append(n+': hierarchy/access changed')
            for m in sorted(x['members']-y['members']):removals.append(n+': '+str(m))
        natives=[n for n in b.namelist() if n.endswith(('.so','.dll','.dylib','.jnilib'))]
        oldn=[n for n in a.namelist() if n.endswith(('.so','.dll','.dylib','.jnilib'))]
        missing=sorted(set(oldn)-set(natives))
        return {'public_classes': count,'removed_or_changed': removals,'native_resources': len(natives),'missing_native_paths': missing,
                    'candidate_max_base_class_major': max((class_api(b.read(n))['major'] for n in b.namelist() if n.endswith('.class') and not n.startswith('META-INF/')),default=None)}

def deps(cache, file, pins=None):
    # The same namespace/hash-bound model is shared with transport verification.
    # This returns inspected direct requirements; callers still track missing
    # transitive POMs/JARs and must never infer executed transport from pin names.
    from maven_closure import Closure
    pins = json.loads((HERE/'pins.json').read_text()) if pins is None else pins
    byfile = {entry['file']: entry for entry in pins}
    require(file in byfile and 'coordinate' in byfile[file], 'unpinned POM '+file)
    model = Closure(cache, pins).model(byfile[file]['coordinate'])
    return [':'.join(d[k] for k in ('groupId','artifactId','version')) for d in model['required']]


def missing_closure(coordinates, pins):
    byfile = {entry['file']: entry for entry in pins}
    return sorted({coordinate for coordinate in coordinates
        if any(f'{coordinate.split(":")[1]}-{coordinate.split(":")[2]}.{kind}' not in byfile
            or byfile[f'{coordinate.split(":")[1]}-{coordinate.split(":")[2]}.{kind}'].get('coordinate') != coordinate
            for kind in ('jar','pom'))})


def candidate_status(family, entry, missing, api):
    if not entry['input_matches_tested_upstream']:
        return 'blocked-repacked-or-shaded-input'
    # This original verifier only executes RabbitMQ parsers. The separate
    # verify_rabbit.py must supply transport evidence; adding pins cannot do so.
    if family == 'rabbit' or missing or api['removed_or_changed'] or api['missing_native_paths']:
        return 'blocked-compatibility'
    return 'component-tested-candidate'

def main():
    p=argparse.ArgumentParser();p.add_argument('--cache',type=Path,required=True);p.add_argument('--reports',type=Path,required=True);p.add_argument('--objects',type=Path,required=True);p.add_argument('--jdk',type=Path,default=Path('/usr/lib/jvm/java-21-openjdk'));p.add_argument('--offline',action='store_true');a=p.parse_args()
    c=a.cache.resolve()
    source_root=next((p for p in (HERE,*HERE.parents) if (p/'.git').exists()), HERE)
    require(not c.is_relative_to(source_root), 'Build outputs must be outside source tree')
    c.mkdir(parents=True,exist_ok=True)
    proof=c/('proof-'+str(time.time_ns()));proof.mkdir()
    source_names=['verify.py','maven_closure.py','LibraryProbe.java','pins.json','toolchain-pins.json']
    source_at_start={n:sha((HERE/n).read_bytes()) for n in source_names}
    save(proof/'source-before.json',source_at_start)
    for n,h in json.loads((HERE/'toolchain-pins.json').read_text()).items():
        with (a.jdk/n).open('rb') as f: require(hashlib.file_digest(f,'sha256').hexdigest()==h,'JDK pin mismatch '+n)
    pins=json.loads((HERE/'pins.json').read_text());byfile={x['file']:x for x in pins}
    for pin in pins:
        f=c/pin['file']
        require(f.parent==c and not f.is_symlink())
        if not f.exists():
            if a.offline:raise ValueError('missing pinned input '+str(f))
            url=pin['url'];require(url.startswith(('https://repo.maven.apache.org/maven2/','https://github.com/')))
            with urllib.request.urlopen(url,timeout=30) as r:b=r.read(32*1024*1024+1)
            require(len(b)<=32*1024*1024 and sha(b)==pin['sha256'], 'download integrity')
            f.write_bytes(b)
        require(sha(f.read_bytes())==pin['sha256'], 'input integrity '+str(f))
    for name,h in REPORTS.items():require(sha((a.reports/name).read_bytes())==h,'wrong CI report')
    report=json.loads((a.reports/'nested-archive-scan.json').read_text())
    object_bytes=a.objects.read_bytes();require(sha(object_bytes)==OBJECTS_SHA256, 'wrong object grouping')
    objects=json.loads(object_bytes)
    normal=json.loads((a.reports/'image-scan.json').read_text())
    require(not any(r.get('Vulnerabilities') for r in normal['Results']), 'standard scan drift')
    tuples={(v['VulnerabilityID'],v['PkgName'],v['InstalledVersion']) for r in report['Results'] for v in r.get('Vulnerabilities',[])}
    require(len(tuples)==59, 'nested findings drift')
    locations={}
    for r in report['Results']:
        for v in r.get('Vulnerabilities',[]):
            ga=v['PkgName']
            if ga in FAMILIES:
                loc=v.get('PkgPath') or next(q['FilePath'] for q in r['Packages'] if q['Name']==ga and q['Version']==v['InstalledVersion'])
                locations.setdefault((ga,v['InstalledVersion']),set()).add(loc)
    # Cross-check scan object identities against the independently cached grouping.
    grouped={(row['package'],row['version']):set(row['object_paths']) for row in objects if row['package'] in FAMILIES}
    require(grouped==locations, 'incomplete object grouping')
    cp=':'.join(str(c/x['file']) for x in pins if x['file'].endswith('.jar') and not x['file'].endswith('-sources.jar') and not any('-'+v+'.jar' in x['file'] for _,vs,_ in FAMILIES.values() for v in vs) and '5.36.0' not in x['file'])
    classes=proof/'classes';classes.mkdir()
    jvm=['-Xmx256m','-XX:ActiveProcessorCount=1','-XX:MaxMetaspaceSize=96m','-XX:ReservedCodeCacheSize=48m','-XX:MaxDirectMemorySize=32m','-Xss512k']
    run([a.jdk/'bin/javac',*['-J'+x for x in jvm],'-cp',cp,'-d',classes,HERE/'LibraryProbe.java'],proof,'compile')
    plan=[];results={}
    for ga,(family,versions,fixed) in FAMILIES.items():
        artifact=ga.split(':')[1];new=f'{artifact}-{fixed}.jar';entries=[]
        closure=deps(c,f'{artifact}-{fixed}.pom');pending=list(closure);seen=set()
        while pending:
            d=pending.pop()
            if d in seen:continue
            seen.add(d);_,da,dv=d.split(':');pom=da+'-'+dv+'.pom'
            if pom in byfile:
                children=deps(c,pom)
                pending.extend(children)
                closure.extend(x for x in children if x not in closure)
        missing=missing_closure(closure,pins)
        results[family]={'inspected_required_dependencies':closure,'unpinned_required_dependencies':missing,'declared_closure_complete':not missing,'abi':{}}
        for v in versions:
            old=f'{artifact}-{v}.jar';api=compare(c/old,c/new);results[family]['abi'][v]=api
            for loc in sorted(locations[(ga,v)]):
                oldhash=Path(loc).stem
                input_matches = oldhash==byfile[old]['sha256']
                entries.append({'package': ga,'installed_version': v,'input_sha256': oldhash,'scan_object_path': loc,
                                    'original_nar_paths': None,'input_matches_tested_upstream': input_matches,'replacement_file': new,'replacement_sha256': byfile[new]['sha256'],'replacement_url': byfile[new]['url'],'patched': False})
        for v in versions+[fixed]:
            label='fixed' if v==fixed else 'control';jar=f'{artifact}-{v}.jar'
            # Exactly one version of each tested library; dependencies are pinned jars.
            localcp=':'.join([str(classes),str(c/jar)]+[str(c/x['file']) for x in pins if x['file'].endswith('.jar') and not x['file'].endswith('-sources.jar') and x.get('coordinate','').rsplit(':',1)[0] not in FAMILIES])
            tmp=proof/f'tmp-{family}-{v}';tmp.mkdir(mode=0o700)
            base=[a.jdk/'bin/java',*jvm,'-Djava.io.tmpdir='+str(tmp),'-cp',localcp,'LibraryProbe',family,label]
            results[family][v]=run(base,proof,f'{family}-{v}')
            if family=='rabbit':run(base+['comment'],proof,f'rabbit-comment-{v}',timeout=2,expected_timeout=label=='control')
        if family=='rabbit':
            intermediate=[str(x).replace('amqp-client-5.37.0.jar','amqp-client-5.36.0.jar') for x in base]
            run(intermediate+['shortstr'],proof,'rabbit-5.36.0-shortstr')
            run(intermediate+['comment'],proof,'rabbit-5.36.0-comment',timeout=2,expected_timeout=True)
        for e in entries:
            e['status']=candidate_status(family,e,missing,results[family]['abi'][e['installed_version']])
            if not e['input_matches_tested_upstream']:
                for key in ('replacement_file','replacement_sha256','replacement_url'): e[key]=None
            plan.append(e)
    # getrusage(SELF) retains the launching harness high-water mark across exec;
    # /proc VmHWM measures this Python address space, not its launcher.
    usage={'max_child_rss_kib':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,'self_max_rss_kib':int(next(line.split()[1] for line in Path('/proc/self/status').read_text().splitlines() if line.startswith('VmHWM:')))}
    save(proof/'resource-usage.json',usage)
    require(max(usage.values())<=512*1024,'process exceeded 512 MiB RSS: '+str(usage))
    save(proof/'component-results.json',results)
    require({n:sha((HERE/n).read_bytes()) for n in source_names}==source_at_start,'source changed during verification')
    run([a.jdk/'bin/java','-Xmx64m','-XX:ActiveProcessorCount=1','-version'],proof,'java-version')
    save(proof/'toolchain.json',{'java_version':(proof/'java-version.log').read_text(), 'tools':{n:sha((a.jdk/'bin'/n).read_bytes()) for n in ['java','javac']},'platform':os.uname().machine,'source_sha256':source_at_start})
    save(proof/'replacement-plan.json',plan)
    print(json.dumps({'component_tests':'passed','plan':str(proof/'replacement-plan.json'),'results':str(proof/'component-results.json'),'patched':False}))
if __name__=='__main__':main()
