#!/usr/bin/env python3
"""Prepare isolated expanded NAR copies and run exact installed NarClassLoader.

Expanded probe trees are evidence only, never returned as deployable candidates.
"""
import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

import qualify as q

p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
BASE=Path('/proof');out=BASE/'runtime-05';out.mkdir(exist_ok=False)
records=[];commands=[];sources={}
def checkedrun(cmd,label,timeout=35):
 with (out/(label+'.stdout')).open('w') as so,(out/(label+'.stderr')).open('w') as se:
  r=subprocess.run(list(map(str,cmd)),stdout=so,stderr=se,timeout=timeout,check=False)
 commands.append({'command':list(map(str,cmd)),'returncode':r.returncode,'label':label})
 q.save(a.output,{'commands':commands,'sources':sources,'runtime_approved':False,'replacement':None})
 if r.returncode:raise ValueError(label+' failed: '+(out/(label+'.stderr')).read_text()[-1000:])
opts=['-Xmx256m','-XX:MaxMetaspaceSize=96m','-XX:MaxDirectMemorySize=32m','-XX:ActiveProcessorCount=1']
jopts=['-J'+x for x in opts]
java=Path('/opt/java/openjdk/bin/java')
if not java.exists():
 java=Path(shutil.which('java')).resolve()
for path in (Path('/jdk/bin/javac'),Path('/jdk/lib/modules'),Path('/jdk/release'),java,java.resolve().parent.parent/'lib/modules'):
 sources[str(path)]=q.sha(path.read_bytes())
checkedrun([java,*opts,'-version'],'actual-image-java-version')
checkedrun(['/jdk/bin/javac',*jopts,'-version'],'javac-version')
top=out/'top';top.mkdir()
for f in sorted(Path('/opt/nifi/nifi-current/lib').glob('*.jar')):
 b=f.read_bytes();(top/f.name).write_bytes(b);sources[str(f)]=q.sha(b)
cp=os.pathsep.join(map(str,top.glob('*.jar')))
classes=out/'classes';classes.mkdir()
checkedrun(['/jdk/bin/javac',*jopts,'-d',classes,'-cp',cp,BASE/'tools/NarProbe.java'],'compile-nar-probe')
if not (BASE/'jdk-classes').exists():
 checkedrun([java,*opts,'-cp',str(classes)+os.pathsep+cp,'NarProbe','jdk',BASE/'jdk-classes'],'export-actual-image-jdk21-base')
checkedrun(['/jdk/bin/javap',*jopts,'-p','-c','-cp',cp,'org.apache.nifi.nar.NarClassLoader','org.apache.nifi.nar.AbstractNativeLibHandlingClassLoader'],'actual-nar-bytecode')
inv=json.loads((BASE/'inventory.json').read_text())
if inv.get('inventory_schema')!=q.INVENTORY_SCHEMA:raise ValueError('obsolete inventory; regenerate WAR and Jetty coverage')
rows={r['manifest']['Nar-Id']:r for r in inv['roots']}
ids=['nifi-amqp-nar','nifi-framework-nar','nifi-jolt-nar','nifi-kafka-to-s3-nar','nifi-standard-nar','nifi-standard-shared-nar']
needed=set(ids)
for id in ids:needed.update(rows[id]['parents'])
parents=out/'parents.tsv';parents.write_text(''.join(id+'\t'+rows[id]['manifest'].get('Nar-Dependency-Id','')+'\n' for id in sorted(needed)))
pins={p['file']:p for p in json.loads((BASE/'pins.json').read_text())}
for variant in ('old','fixed'):
 for id in sorted(needed):
  r=rows[id];f=Path('/')/r['path'];b=f.read_bytes();assert q.sha(b)==r['sha256'];sources[str(f)]=q.sha(b)
  dest=out/variant/id/'NAR-INF/bundled-dependencies';dest.mkdir(parents=True)
  for n,blob in q.entries(b):
   name=Path(n).name;new=None
   if variant=='fixed' and name in q.OLD_NEW:
    new=q.OLD_NEW[name];blob=(BASE/'cache'/new).read_bytes();assert q.sha(blob)==pins[new]['sha256']
   target_name=new if new is not None else name
   assert not (dest/target_name).exists(),'duplicate expanded JAR basename'
   (dest/target_name).write_bytes(blob);records.append({'variant':variant,'context':id,'source_entry':n,'expanded_name':target_name,'sha256':q.sha(blob),'pinned_fixed':new})
q.save(out/'expanded-inputs.json',records)
# Compile probes against the actual original carrier closure; only generated
# probe classes are added to the disposable expanded NAR roots.
template=(BASE/'probe-template.java.in').read_text();sources['probe-template.java.in']=q.sha((BASE/'probe-template.java.in').read_bytes())
for family,id,ns in [('2','nifi-amqp-nar','com.fasterxml.jackson'),('3','nifi-jolt-nar','tools.jackson')]:
 src=out/('Jackson'+family+'Probe.java');src.write_text(template.replace('@NS@',ns).replace('JacksonProbe','Jackson'+family+'Probe'))
 compilecp=[]
 for nar in [id,*rows[id]['parents']]:compilecp.extend((out/'old'/nar/'NAR-INF/bundled-dependencies').glob('*.jar'))
 dest=out/('probe'+family);dest.mkdir()
 checkedrun(['/jdk/bin/javac',*jopts,'-d',dest,'-cp',os.pathsep.join(map(str,compilecp)),src],'compile-jackson'+family)
 for variant in ('old','fixed'):
  for target in ids:
   target_family=q.probe_family(target)
   if family!=target_family:continue
   for f in dest.glob('*.class'):shutil.copyfile(f,out/variant/target/f.name)
consumers={'nifi-amqp-nar':['org.apache.nifi.amqp.processors.ConsumeAMQP'],'nifi-jolt-nar':['org.apache.nifi.processors.jolt.JoltTransformJSON']}
for variant in ('old','fixed'):
 for id in ids:
  family=q.probe_family(id)
  version=('3.2.' if family=='3' else '2.22.')+('3' if variant=='fixed' else '2')
  checkedrun([java,*opts,'-cp',str(classes)+os.pathsep+cp,'NarProbe',out/variant,parents,id,family,version,str(variant=='fixed').lower(),*consumers.get(id,[])],variant+'-'+id)
after={k:q.sha(Path(k).read_bytes()) for k in sources if k.startswith('/')}
assert all(sources[k]==v for k,v in after.items()),'runtime source drift'
q.save(a.output,{'commands':commands,'sources_before':sources,'sources_after':after,'expanded_input_manifest_sha256':q.sha((out/'expanded-inputs.json').read_bytes()),'runtime_approved':False,'replacement':None,'status':'bounded-real-NarClassLoader-component-probes-passed','limits':['not NiFi startup/processor scheduling/service integration','WAR Jetty delegation and consumers remain unproven','full static closure, Maven family guard, final image and QA still required']})
