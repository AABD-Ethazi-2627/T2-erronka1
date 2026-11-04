#!/usr/bin/env python3
"""Read-only candidate preparation; no archive mutation or service execution."""
import argparse
import hashlib
import importlib.util
import io
import json
import os
import resource
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUPPORT = HERE.parent / 'compatible-libraries'
PAIRS = [('2.21.2','2.21.7'), ('2.22.2','2.22.3'), ('3.1.2','3.1.7'), ('3.2.2','3.2.3')]
MAX_DOWNLOAD_BYTES = 32 * 1024 * 1024
def sha(data): return hashlib.sha256(data).hexdigest()
def require(ok, message):
    if not ok: raise ValueError(message)
def save(path, data): path.write_text(json.dumps(data, indent=2, sort_keys=True)+'\n')
def checked(path, digest):
    require(path.is_file() and not path.is_symlink(), 'missing/linked input '+str(path))
    data=path.read_bytes(); require(sha(data)==digest, 'integrity '+str(path)); return data

def fetch_checked(pin, target):
    require(not target.is_symlink(), 'linked download target '+str(target))
    with urllib.request.urlopen(pin['url'],timeout=30) as response:
        data=response.read(MAX_DOWNLOAD_BYTES+1)
    require(len(data)<=MAX_DOWNLOAD_BYTES and sha(data)==pin['sha256'],'download integrity/size')
    with target.open('xb') as stream:
        stream.write(data)

def validate_pins(pins):
    require(pins and len({p['file'] for p in pins})==len(pins), 'empty/duplicate pins')
    for p in pins:
        g,a,v=p['coordinate'].split(':');name=p['file']
        require(name in (f'{a}-{v}.pom',f'{a}-{v}.jar',f'{a}-{v}-sources.jar'), 'pin filename')
        require(p['url']==f'https://repo.maven.apache.org/maven2/{g.replace(".","/")}/{a}/{v}/{name}', 'untrusted URL')
        require(len(p['sha256'])==64 and all(x in '0123456789abcdef' for x in p['sha256']), 'pin digest')

def classify(objects, occurrences, pins):
    result=[]
    for o in objects:
        if 'jackson' not in o['package']: continue
        a=o['package'].split(':')[1];v=o['version']; new=dict(PAIRS)[v]
        old=next(p for p in pins if p['coordinate']==o['package']+':'+v and p['file']==f'{a}-{v}.jar')
        replacement=next(p for p in pins if p['coordinate']==o['package']+':'+new and p['file']==f'{a}-{new}.jar')
        for loc in o['object_paths']:
            digest=Path(loc).stem; matches=[x for x in occurrences if x['sha256']==digest]
            require(matches, 'scan object absent from inventory')
            pure=digest==old['sha256']
            result.append({'package':o['package'],'version':v,'object_sha256':digest,
                'occurrences':[{'outer':m['outer'],'members':m['members'],
                    'outer_sha256':m['outer_sha256'],'chain_sha256':m['chain_sha256']} for m in matches],
                'upstream_old_equal':pure, 'replacement':replacement if pure else None,
                'research_candidate':replacement['coordinate'],
                'status':'component-candidate-consumer-review-required' if pure else 'blocked-wrapper-specific-rebuild-required'})
    require(result, 'empty Jackson object set')
    return result

def extract(source, occurrence):
    path=source/occurrence['outer']
    require(path.resolve().is_relative_to(source.resolve()), 'source escape')
    require(len(occurrence['chain_sha256'])==len(occurrence['members'])+1, 'invalid chain length')
    require(occurrence['chain_sha256'][0]==occurrence['outer_sha256'],'invalid outer chain')
    data=checked(path,occurrence['outer_sha256'])
    for member,expected in zip(occurrence['members'],occurrence['chain_sha256'][1:]):
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            require(z.namelist().count(member)==1, 'ambiguous ZIP member')
            data=z.read(member)
        require(sha(data)==expected,'nested chain integrity')
    require(sha(data)==occurrence['sha256'],'occurrence integrity')
    return data

def limits():
    resource.setrlimit(resource.RLIMIT_CORE,(0,0)); resource.setrlimit(resource.RLIMIT_CPU,(30,30))
    os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
def run(cmd, out):
    env={k:v for k,v in os.environ.items() if k not in ('JAVA_TOOL_OPTIONS','JDK_JAVA_OPTIONS','JDK_JAVAC_OPTIONS','_JAVA_OPTIONS','CLASSPATH','LD_PRELOAD','LD_LIBRARY_PATH')}
    p=subprocess.run(list(map(str,cmd)),env=env,preexec_fn=limits,capture_output=True,check=False,timeout=40)
    out.write_bytes(p.stdout+p.stderr); require(p.returncode==0,'probe failed '+str(out))
    return {'command':list(map(str,cmd)), 'log_sha256':sha(out.read_bytes()),'stdout':p.stdout.decode()}

def support_modules():
    # Load existing helpers without changing them or colliding with root test imports.
    for file,digest in json.loads((HERE/'support-lock.json').read_text()).items(): checked(SUPPORT/file,digest)
    spec=importlib.util.spec_from_file_location('_jackson_support',SUPPORT/'verify.py')
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    prior=sys.modules.get('verify');sys.modules['verify']=helper
    try:
        spec=importlib.util.spec_from_file_location('_jackson_closure',SUPPORT/'maven_closure.py')
        closure=importlib.util.module_from_spec(spec);spec.loader.exec_module(closure)
    finally:
        if prior is None:sys.modules.pop('verify',None)
        else:sys.modules['verify']=prior
    return helper,closure

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--cache',type=Path,required=True);ap.add_argument('--proof',type=Path,required=True)
    ap.add_argument('--inputs',type=Path,required=True);ap.add_argument('--source',type=Path,required=True)
    ap.add_argument('--fetch',action='store_true');args=ap.parse_args()
    repo=HERE.parents[3]
    require('.m2' not in args.cache.resolve().parts, 'shared Maven cache forbidden')
    for p in [args.cache,args.proof]:
        require(not p.resolve().is_relative_to(repo),'cache/proof must be outside repository')
        require(not p.resolve().is_relative_to(args.source.resolve()),'cache/proof must be outside source')
    args.proof.mkdir(parents=True,exist_ok=False);args.cache.mkdir(parents=True,exist_ok=True)
    lock=json.loads((HERE/'input-lock.json').read_text())
    srcs=[*HERE.glob('*.py'),*HERE.glob('*.java.in'),*HERE.glob('*.java'), HERE/'pins.json',HERE/'input-lock.json',HERE/'support-lock.json',HERE/'upstream-pins.json',HERE/'README.md',HERE/'coverage.json',repo/'tests/test_nifi_jackson_candidate.py',SUPPORT/'verify.py',SUPPORT/'maven_closure.py']
    before={str(p):sha(p.read_bytes()) for p in srcs}
    java_home=Path(shutil.which('java')).resolve().parents[1]
    require(Path(shutil.which('javac')).resolve().parent==java_home/'bin','mixed JDK tools')
    tool_files=[java_home/f for f in ['bin/java','bin/javac','lib/modules','lib/server/libjvm.so','release']]
    toolchain={str(p):sha(p.read_bytes()) for p in tool_files}
    source_before={str(p.relative_to(args.source)):sha(p.read_bytes()) for p in args.source.rglob('*') if p.is_file()}
    require(len(source_before)==156,'source inventory file count drift')
    pins=json.loads((HERE/'pins.json').read_text());validate_pins(pins)
    for p in pins:
        f=args.cache/p['file']
        if not f.exists() and args.fetch:
            fetch_checked(p,f)
        checked(f,p['sha256'])
    for pin in json.loads((HERE/'upstream-pins.json').read_text()):
        require(Path(pin['file']).name==pin['file'],'upstream pin filename')
        require(pin['url'].startswith(('https://api.github.com/repos/FasterXML/','https://github.com/FasterXML/')),'untrusted upstream source')
        target=args.cache/pin['file']
        if not target.exists() and args.fetch:
            fetch_checked(pin,target)
        checked(target,pin['sha256'])
    inputs={k:checked(args.inputs/v['relative'],v['sha256']) for k,v in lock.items()}
    inv=json.loads(inputs['inventory']);objects=json.loads(inputs['objects']);scan=json.loads(inputs['scan'])
    # Grouping must match the scan for Jackson in both directions.
    scan_set={(v['PkgName'],v['InstalledVersion'],v['PkgPath']) for r in scan['Results'] for v in r.get('Vulnerabilities',[]) if 'jackson' in v['PkgName']}
    grouped={(o['package'],o['version'],p) for o in objects if 'jackson' in o['package'] for p in o['object_paths']}
    require(scan_set==grouped,'scan/grouping disagreement')
    entries=classify(objects,inv['occurrences'],pins)
    touched={e['object_sha256'] for e in entries}
    for o in inv['occurrences']:
        if o['sha256'] in touched: extract(args.source,o)
    consumer=next(p for p in pins if p['file']=='json-community-utils-1.3.0.jar')
    consumer_occ=[o for o in inv['occurrences'] if o['sha256']==consumer['sha256']]
    require(len(consumer_occ)==2,'actual Jolt consumer equality missing')
    for o in consumer_occ: extract(args.source,o)
    module_names=['jackson-dataformat-csv-2.22.2.jar','jackson-datatype-jsr310-2.22.2.jar']
    for name in module_names:
        pin=next(p for p in pins if p['file']==name)
        occurrences=[o for o in inv['occurrences'] if o['sha256']==pin['sha256']]
        require(occurrences,'stock module equality missing '+name)
        for o in occurrences: extract(args.source,o)
    helper,closure=support_modules(); results={}; commands=[]
    for old,new in PAIRS:
        result={};results[old+'->'+new]=result
        for a in ['jackson-core','jackson-databind']:
            result[a+'_symbolic_abi']=helper.compare(args.cache/f'{a}-{old}.jar',args.cache/f'{a}-{new}.jar')
        for v in [old,new]:
            coord=('com.fasterxml.jackson.core' if v[0]=='2' else 'tools.jackson.core')+':jackson-databind:'+v
            result[v+'_closure']=closure.Closure(args.cache,pins).resolve(coord)
        ann={'2.21.2':'2.21','2.22.2':'2.22','3.1.2':'2.21','3.2.2':'2.22'}[old];ns='com.fasterxml.jackson' if old[0]=='2' else 'tools.jackson'
        work=args.proof/old;work.mkdir();java=work/'JacksonProbe.java'
        java.write_text((HERE/'JacksonProbe.java.in').read_text().replace('@NS@',ns))
        def cp(v, annotation_version=ann):
            return os.pathsep.join(str(args.cache/f'{a}-{b}.jar') for a,b in [('jackson-core',v),('jackson-databind',v),('jackson-annotations',annotation_version)])
        opts=['-XX:ActiveProcessorCount=1','-Xmx256m','-XX:MaxMetaspaceSize=96m','-XX:ReservedCodeCacheSize=32m','-XX:MaxDirectMemorySize=32m','-XX:-CreateCoredumpOnCrash']
        commands.append(run(['javac',*['-J'+o for o in opts],'-cp',cp(old),'-d',work,java],work/'compile.log'))
        for v in [old,new]:
            commands.append(run(['java',*opts,'-cp',str(work)+os.pathsep+cp(v)+ (os.pathsep+str(args.cache/consumer['file']) if old=='3.2.2' else ''),'JacksonProbe',str(v==new).lower(),str(old=='3.2.2').lower(),str(v==new or old in ('2.22.2','3.2.2')).lower()],work/(v+'.log')))
        if old=='2.22.2':
            modules=os.pathsep.join(str(args.cache/n) for n in module_names)
            commands.append(run(['javac',*['-J'+o for o in opts],'-cp',cp(old)+os.pathsep+modules,'-d',work,HERE/'ModuleProbe.java'],work/'module-compile.log'))
            for v in [old,new]:
                commands.append(run(['java',*opts,'-cp',str(work)+os.pathsep+cp(v)+os.pathsep+modules,'ModuleProbe'],work/(v+'-modules.log')))
    # Existing NAR/WAR siblings describe candidate consumer contexts only;
    # inherited NAR and webapp delegation are explicitly unapproved.
    contexts=[]
    selected=[o for o in inv['occurrences'] if o['sha256'] in touched]
    for key in sorted({(o['outer'],tuple(o['members'][:-1])) for o in selected}):
        siblings=[o for o in inv['occurrences'] if o['outer']==key[0] and tuple(o['members'][:-1])==key[1] and o['members']]
        contexts.append({'outer':key[0],'archive_parent':key[1],
            'siblings':[{'members':o['members'],'sha256':o['sha256'],'maven':o['maven']} for o in siblings],
            'status':'inherited-NAR-webapp-delegation-and-all-consumers-unverified'})
    for entry in entries:
        pair=entry['version']+'->'+dict(PAIRS)[entry['version']]
        abi=results[pair][entry['package'].split(':')[1]+'_symbolic_abi']
        entry['symbolic_abi_changes']=abi['removed_or_changed']
        if entry['replacement'] and abi['removed_or_changed']:
            entry['status']='blocked-symbolic-ABI-and-consumer-review-required'
    extensions=[{'outer':o['outer'],'members':o['members'],'sha256':o['sha256'],'maven':o['maven'],'status':'existing-extension-full-closure-and-NiFi-linkage-unverified'}
        for o in inv['occurrences'] if any('jackson' in m['path'] for m in o['maven'])]
    save(args.proof/'extension-inventory.json',extensions)
    save(args.proof/'consumer-contexts.json',contexts)
    require(toolchain=={str(p):sha(p.read_bytes()) for p in tool_files},'toolchain changed')
    after={str(p):sha(p.read_bytes()) for p in srcs}
    require(before==after,'verification sources changed')
    source_after={str(p.relative_to(args.source)):sha(p.read_bytes()) for p in args.source.rglob('*') if p.is_file()}
    require(source_before==source_after,'source archives changed')
    save(args.proof/'source-before.json',source_before);save(args.proof/'source-after.json',source_after)
    save(args.proof/'candidate-plan.json',{'status':'component-prepared','entries':entries,'results':results,'runtime_approved':False})
    save(args.proof/'summary.json',{'status':'component-prepared','toolchain_sha256':toolchain,'sources_before':before,'sources_after':after,'commands':commands,'source_archives':len(source_after),'inputs':lock,'plan_sha256':sha((args.proof/'candidate-plan.json').read_bytes()),'proof_artifacts':{str(p.relative_to(args.proof)):sha(p.read_bytes()) for p in args.proof.rglob('*') if p.is_file()}})
    print(args.proof/'summary.json')
if __name__=='__main__':main()
