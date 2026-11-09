import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

cache=Path(os.environ["CNC_CLOSEOUT_CACHE"]);root=Path(__file__).resolve().parent.parent
out=cache/'iceberg-guava-1';out.mkdir()
sys.path.insert(0,str(root/'hazelcast-jackson'))
spec=importlib.util.spec_from_file_location('raw_assembler',root/'hazelcast-jackson/prepare.py')
writer=importlib.util.module_from_spec(spec);spec.loader.exec_module(writer)
writer.PROVENANCE='META-INF/cnc-guard/iceberg-guava-fork.json'
inputs=cache/'components/hazelcast';libs=cache/'components/libraries'
cp=os.pathsep.join(str(inputs/name) for name in writer.TOOLS)
jdk=Path(os.environ["CNC_CLOSEOUT_JAVA_BIN"])
flags=['-Xmx256m','-XX:ActiveProcessorCount=1','-XX:MaxMetaspaceSize=96m','-XX:-CreateCoredumpOnCrash']
commands=[]
def sha(data):return hashlib.sha256(data).hexdigest()
def run(tool,args,label):
    argv=[str(jdk/(tool+('.exe' if os.name=='nt' else '')))]+(['-J'+v for v in flags] if tool=='javac' else flags)+list(map(str,args))
    p=subprocess.run(argv,capture_output=True,text=True,timeout=60,check=False)
    (out/(label+'.log')).write_text(p.stdout+p.stderr)
    commands.append({'argv':argv,'rc':p.returncode,'log_sha256':sha((p.stdout+p.stderr).encode())})
    (out/'commands.json').write_text(json.dumps(commands,indent=2))
    if p.returncode:raise RuntimeError(label+' failed')
run('javac',['-cp',cp,'-d',out,root/'closeout/GuavaShade.java'],'compile')
with zipfile.ZipFile(cache/'stock-lib/nifi-iceberg-shared-nar-2.12.0.nar') as z:
    original=z.read('META-INF/bundled-dependencies/iceberg-bundled-guava-1.11.0.jar')
if sha(original)!='396d48d93ef5735f2ddef0cf9b3d6968ebd67b64b5cfe753d41c429d3f46a2a1':raise ValueError('original drift')
stock=writer.entries(io.BytesIO(original))
payload={}
for version in ['33.6.0-jre','33.7.2-jre']:
    target=out/('guava-'+version+'-shaded.jar')
    run('java',['-cp',str(out)+os.pathsep+cp,'GuavaShade',libs/('guava-'+version+'.jar'),target],version)
    with zipfile.ZipFile(target) as z:
        payload[version]={n:z.read(n) for n in z.namelist() if n.startswith((
            'org/apache/iceberg/relocated/com/google/common/',
            'META-INF/maven/com.google.guava/guava/')) and not n.endswith('/')}
old=payload['33.6.0-jre'];new=payload['33.7.2-jre']
selected=set(old)&set(stock)
mismatches=[n for n in selected if old[n]!=stock[n]]
(out/'baseline.json').write_text(json.dumps({'mapped':len(selected),'mismatches':mismatches,
    'minimized_absent_in_original':len(set(old)-set(stock))},indent=2))
if mismatches or len(selected)<1000:raise ValueError('old shade baseline mismatch '+str(mismatches[:5]))
remove={n for n in selected if new.get(n)!=stock[n]}
replacement={n:b for n,b in new.items() if stock.get(n)!=b}
with zipfile.ZipFile(libs/'guava-33.7.2-jre.jar') as z:
    for name in ['META-INF/LICENSE','META-INF/NOTICE']:
        if name in z.namelist():replacement['META-INF/cnc-guard/guava33.7.2/'+Path(name).name]=z.read(name)
provenance={'kind':'CNC Iceberg1.11 bundled Guava33.7.2 fork; not an Apache release',
    'original_sha256':sha(original),'guava_old_sha256':sha((libs/'guava-33.6.0-jre.jar').read_bytes()),
    'guava_fixed_sha256':sha((libs/'guava-33.7.2-jre.jar').read_bytes()),'runtime_approved':False,
    'mapped_equal_old_entries':len(selected),'added_complete_guava_classes':len(set(new)-set(stock)),
    'upstream_relocation_source_sha256':sha((cache/'iceberg-build.gradle').read_bytes())}
candidate=writer.assemble(original,remove,replacement,provenance)
target=out/'iceberg-bundled-guava-1.11.0-cnc-guava33.7.2.jar';target.write_bytes(candidate)
(out/'artifact.json').write_text(json.dumps({'file':str(target),'sha256':sha(candidate),'provenance':provenance,
    'removed':len(remove),'replacement':len(replacement)},indent=2))
print('candidate',sha(candidate),'mapped',len(selected),'new_classes',len(set(new)-set(stock)))
