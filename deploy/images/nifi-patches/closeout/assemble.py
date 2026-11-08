"""Qualification overlay only: exact original archives, no removed NARs."""
import hashlib
import importlib.util
import io
import json
import os
import re
import sys
import zipfile
from pathlib import Path

cache=Path(os.environ["CNC_CLOSEOUT_CACHE"])
root=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(root/'hazelcast-jackson'))
spec=importlib.util.spec_from_file_location('writer',root/'hazelcast-jackson/prepare.py')
writer=importlib.util.module_from_spec(spec);spec.loader.exec_module(writer)
writer.PROVENANCE='META-INF/cnc-guard/full-stock-closeout.json'
out=Path(os.environ["CNC_CLOSEOUT_OVERLAY"]);out.mkdir()
def sha(b):return hashlib.sha256(b).hexdigest()
for row in json.loads((cache/'components/downloads.json').read_text()):
    assert sha(Path(row['file']).read_bytes())==row['sha256']
replacements={}
def add(old,path):
    assert path.is_file(),path
    assert old not in replacements,old
    replacements[old]=(path.name,path.read_bytes())
libs=cache/'components/libraries';jackson=cache/'components/jackson'
for a,old,new in [('guava','33.7.1-jre','33.7.2-jre'),('lz4-java','1.11.2','1.11.4'),('amqp-client','5.35.0','5.37.0')]:
    add(a+'-'+old+'.jar',libs/(a+'-'+new+'.jar'))
add('snappy-java-1.1.10.8.jar',cache/'snappy-official-1/snappy-java-1.1.10.12.jar')
for a in ['jackson-core','jackson-databind']:
    for old,new in [('2.21.2','2.21.7'),('2.22.2','2.22.3'),('3.1.2','3.1.7'),('3.2.2','3.2.3')]:
        add(a+'-'+old+'.jar',jackson/(a+'-'+new+'.jar'))
for a in ['api','context','common','sdk','sdk-common','sdk-trace','sdk-metrics','sdk-logs','sdk-extension-autoconfigure-spi']:
    add('opentelemetry-'+a+'-1.62.0.jar',cache/'components/otel'/('opentelemetry-'+a+'-1.67.0.jar'))
for old,path in [
    ('hadoop-common-3.5.0.jar',cache/'wrapper-build-2/hadoop/hadoop-common-3.5.0-cnc-capacity-v3.jar'),
    ('hazelcast-5.7.0.jar',cache/'wrapper-build-2/hazelcast/hazelcast-cnc-closeout.jar'),
    ('parquet-jackson-1.18.1.jar',cache/'wrapper-build-2/parquet/parquet-cnc-closeout.jar'),
    ('iceberg-bundled-guava-1.11.0.jar',cache/'iceberg-guava-1/iceberg-bundled-guava-1.11.0-cnc-guava33.7.2.jar'),
    ('hadoop-shaded-guava-1.5.0.jar',cache/'hadoop-shaded-guava-1.6.0.jar')]:add(old,path)
aws={}
with zipfile.ZipFile(cache/'stock-lib/nifi-aws-nar-2.12.0.nar') as z:
    oldnames=[Path(n).name for n in z.namelist() if n.endswith('.jar')]
newfiles=list((cache/'wire6-closure-jars').glob('*.jar'))
for module in ['build-tools','common','serializer-deserializer']:
    newfiles+=list((cache/'aws-linux-result-6'/module/'target').glob('*cnc-wire6.5.jar'))
assert len(newfiles)==19,len(newfiles)
for path in newfiles:
    artifact=path.name[:-4].split('-1.1.24-cnc')[0] if '-cnc-' in path.name else path.name[:-4].rsplit('-',1)[0]
    old=[n for n in oldnames if n[:-4].rsplit('-',1)[0]==artifact]
    assert len(old)==1,(artifact,old)
    aws[old[0]]=(path.name,path.read_bytes())
changes=[]
def patch(data,location):
    remove=set();replace={};local=[]
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for name in z.namelist():
            if not name.endswith(('.jar','.war','.nar')):continue
            leaf=Path(name).name;payload=z.read(name)
            selected=aws.get(leaf) if 'nifi-aws-nar-2.12.0.nar' in location else None
            if selected is None:selected=replacements.get(leaf)
            # RabbitMQ 5.37's declared Netty closure, confined to AMQP NAR.
            if 'nifi-amqp-nar-2.12.0.nar' in location and leaf.startswith('netty-'):
                artifact=re.split(r'-4\.',leaf)[0]
                fixed=libs/(artifact+'-4.2.18.Final.jar')
                assert fixed.is_file(),leaf
                selected=(fixed.name,fixed.read_bytes())
            if selected:
                newleaf,new=selected
            else:newleaf=leaf;new=patch(payload,location+'!/'+name)
            if new!=payload:
                target=name[:-len(leaf)]+newleaf
                remove.add(name);replace[target]=new
                row={'path':location+'!/'+name,'new_name':newleaf,'before':sha(payload),'after':sha(new)}
                changes.append(row);local.append(row)
    if not remove:return data
    return writer.assemble(data,remove,replace,{'kind':'full-stock qualification; not runtime acceptance','changes':local})
lock=json.loads((root/'stock-occurrences/source-lock.json').read_text())
for row in lock['archives']:
    source=cache/'full-source'/row['path'];data=source.read_bytes()
    assert sha(data)==row['sha256'],row['path']
    leaf=source.name
    if leaf in replacements:
        newleaf,new=replacements[leaf]
        changes.append({'path':row['path'],'new_name':newleaf,'before':sha(data),'after':sha(new)})
    else:newleaf=leaf;new=patch(data,row['path'])
    if new!=data:
        dest=out/Path(row['path']).parent/newleaf;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(new)
(out/'changes.json').write_text(json.dumps(changes,indent=2))
(out/'remove.json').write_text(json.dumps([r['path'] for r in changes if '!/' not in r['path']],indent=2))
print('changed',len(changes),'files',len(list(out.rglob('*.nar'))),'NAR removals 0')
