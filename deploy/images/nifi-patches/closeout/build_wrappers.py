"""Execute the existing raw-record-preserving wrapper algorithms with measured host JDK21."""
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

cache=Path(os.environ["CNC_CLOSEOUT_CACHE"])
root=Path(__file__).resolve().parent.parent
out=cache/'wrapper-build-2';out.mkdir()
jdk=Path(os.environ["CNC_CLOSEOUT_JAVA_BIN"])
flags=['-Xmx256m','-XX:MaxMetaspaceSize=96m','-XX:ActiveProcessorCount=1','-XX:ReservedCodeCacheSize=48m','-XX:MaxDirectMemorySize=32m','-XX:-CreateCoredumpOnCrash']
def sha(data):return hashlib.sha256(data).hexdigest()
def load(folder):
    sys.modules.pop('bounded',None)
    sys.path.insert(0,str(root/folder))
    spec=importlib.util.spec_from_file_location(folder.replace('-','_'),root/folder/'prepare.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    sys.path.pop(0)
    return module
commands=[]
def execute(tool,args,label):
    argv=[str(jdk/(tool+('.exe' if os.name=='nt' else '')))]+(['-J'+v for v in flags] if tool in ['javac','javap'] else flags)+list(map(str,args))
    p=subprocess.run(argv,capture_output=True,text=True,timeout=60,check=False)
    (out/(label+'.log')).write_bytes((p.stdout+p.stderr).encode())
    commands.append({'argv':argv,'rc':p.returncode,'log_sha256':sha((p.stdout+p.stderr).encode())})
    (out/'commands.json').write_text(json.dumps(commands,indent=2))
    if p.returncode:raise RuntimeError(label+' failed; see log')
    return p.stdout

outputs={}
for family in ['hazelcast','parquet']:
    folder=family+'-jackson';module=load(folder);inputs=cache/'components'/family
    proof=out/family;proof.mkdir()
    cp=os.pathsep.join(str(inputs/name) for name in module.TOOLS)
    execute('javac',['-cp',cp,'-d',proof,root/folder/'Shade.java'],'compile-'+family)
    original=(inputs/('hazelcast-5.7.0.jar' if family=='hazelcast' else 'parquet-jackson-1.18.1.jar')).read_bytes()
    if sha(original)!=module.OLD:raise ValueError('wrapper original drift')
    stock=module.entries(io.BytesIO(original))
    removed=set();replacement={};baselines=[]
    for old,new in module.PAIRS:
        components=['core','databind'] if family=='hazelcast' else ['all']
        for component in components:
            generated={}
            for version in [old,new]:
                target=proof/(component+'-'+version+'.jar')
                if family=='hazelcast':
                    args=[inputs/('jackson-'+component+'-'+version+'.jar'),target]
                else:
                    args=[target,inputs/('jackson-core-'+version+'.jar'),inputs/'jackson-annotations-2.22.jar',inputs/('jackson-databind-'+version+'.jar')]
                execute('java',['-cp',str(proof)+os.pathsep+cp,'Shade',*args],family+'-'+component+'-'+version)
                generated[version]=module.payload(target)
            previous=generated[old];fixed=generated[new]
            mismatches=[n for n,b in previous.items() if stock.get(n)!=b]
            (proof/('baseline-'+component+'-'+old+'.json')).write_text(json.dumps({'entries':len(previous),'mismatches':mismatches},indent=2))
            if mismatches:raise ValueError('official old shade baseline mismatch: '+str(mismatches[:4]))
            if family=='parquet':
                module.check_baseline(stock,previous)
                removed.update(n for n,b in previous.items() if fixed.get(n)!=b)
                replacement.update({n:b for n,b in fixed.items() if previous.get(n)!=b})
            else:
                removed.update(previous);replacement.update(fixed)
            baselines.append({'component':component,'old':old,'new':new,'equal_old_entries':len(previous)})
    provenance={'kind':'CNC closeout local wrapper reconstruction; not an upstream release',
                'original_sha256':module.OLD,'runtime_approved':False,'baselines':baselines,
                'tool_java_sha256':sha((jdk/('java.exe' if os.name=='nt' else 'java')).read_bytes()),
                'shader_source_sha256':sha((root/folder/'Shade.java').read_bytes())}
    candidate=module.assemble(original,removed,replacement,provenance)
    target=proof/(family+'-cnc-closeout.jar');target.write_bytes(candidate)
    outputs[family]={'file':str(target),'sha256':sha(candidate),'baselines':baselines,'removed':len(removed),'replacements':len(replacement)}

module=load('hadoop-snappy');proof=out/'hadoop';proof.mkdir()
acquired=cache/'components/hadoop';libs=cache/'components/libraries'
original=(acquired/'hadoop-common-3.5.0.jar').read_bytes()
if sha(original)!=module.HADOOP:raise ValueError('Hadoop original drift')
original_path=proof/'original.jar';original_path.write_bytes(original)
with zipfile.ZipFile(acquired/'hadoop-common-3.5.0-sources.jar') as source:text=source.read(module.SOURCE).decode()
cp=os.pathsep.join(map(str,[original_path,libs/'snappy-java-1.1.10.9.jar',cache/'stock-lib/slf4j-api-2.0.19.jar']))
for mode in ['unmodified','fixed','capacity-only','limit-only']:
    target=proof/mode;target.mkdir();java=target/'SnappyCompressor.java'
    java.write_bytes((text if mode=='unmodified' else module.patch_source(text,mode)).encode())
    execute('javac',['--release','17','-g','-proc:none','-implicit:none','-d',target,'-cp',cp,java],'hadoop-compile-'+mode)
    abi=execute('javap',['-p','-s','-cp',target,'org.apache.hadoop.io.compress.snappy.SnappyCompressor'],'hadoop-abi-'+mode)
    original_abi=execute('javap',['-p','-s','-cp',original_path,'org.apache.hadoop.io.compress.snappy.SnappyCompressor'],'hadoop-original-abi-'+mode)
    if abi!=original_abi:raise ValueError('Hadoop ABI drift')
oldcode=execute('javap',['-c','-p','-cp',original_path,'org.apache.hadoop.io.compress.snappy.SnappyCompressor'],'hadoop-original-instructions')
compiled=execute('javap',['-c','-p','-cp',proof/'unmodified','org.apache.hadoop.io.compress.snappy.SnappyCompressor'],'hadoop-recompiled-instructions')
if oldcode!=compiled:raise ValueError('Hadoop original source instruction drift')
replacement=(proof/'fixed'/module.CLASS).read_bytes()
with zipfile.ZipFile(io.BytesIO(original)) as old:previous=old.read(module.CLASS)
prov={'kind':'CNC Guard local source correction, NOT an upstream release','upstream_version':'3.5.0',
      'input_sha256':module.HADOOP,'source_jar_sha256':sha((acquired/'hadoop-common-3.5.0-sources.jar').read_bytes()),
      'patched_source_sha256':sha((proof/'fixed/SnappyCompressor.java').read_bytes()),'changed_entry':module.CLASS,
      'original_class_sha256':sha(previous),'replacement_class_sha256':sha(replacement),
      'snappy_unchanged_sha256':module.SNAPPY,'approval':False}
candidate=module.rebuild(original,replacement,prov)
module.verify_candidate(candidate,prov)
target=proof/'hadoop-common-3.5.0-cnc-snappy-buffer-v2.jar';target.write_bytes(candidate)
outputs['hadoop']={'file':str(target),'sha256':sha(candidate),'matches_historical_verified_pin':True}
# Snappy 1.1.10.12 contains upstream #766's capacity-based output guard.
# Keep its limit semantics and retain only Hadoop's insufficient-capacity fix.
replacement=(proof/'capacity-only'/module.CLASS).read_bytes()
prov={**prov,'kind':'CNC Hadoop capacity-only correction with official Snappy 1.1.10.12',
      'patched_source_sha256':sha((proof/'capacity-only/SnappyCompressor.java').read_bytes()),
      'replacement_class_sha256':sha(replacement),
      'snappy_upstream_fix':'https://github.com/xerial/snappy-java/pull/766',
      'snappy_unchanged_sha256':sha((cache/'snappy-official-1/snappy-java-1.1.10.12.jar').read_bytes())}
candidate=module.rebuild(original,replacement,prov)
target=proof/'hadoop-common-3.5.0-cnc-capacity-v3.jar';target.write_bytes(candidate)
outputs['hadoop_capacity']={'file':str(target),'sha256':sha(candidate),'delta':'capacity only; original limit retained'}
(out/'artifacts.json').write_text(json.dumps(outputs,indent=2))
print(json.dumps(outputs,indent=2))
