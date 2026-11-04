#!/usr/bin/env python3
"""Pinned RabbitMQ transport/closure supplement; never patches or starts NiFi."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import time
import urllib.request
import zipfile
from maven_closure import Closure
from verify import HERE, require, sha, save, run, compare, class_api

JVM=['-Xmx256m','-XX:ActiveProcessorCount=1','-XX:MaxMetaspaceSize=96m','-XX:ReservedCodeCacheSize=48m','-XX:MaxDirectMemorySize=32m','-Xss512k']
EXPECTED_INPUT='c23f1dffc08e2c209035f8d22a48edfd83477b629477e9416a5d25e2c116f3f6'

def inputs(cache,offline):
    pins=json.loads((HERE/'rabbit-pins.json').read_text())
    require(len({x['file'] for x in pins})==len(pins),'duplicate pin name')
    for pin in pins:
        f=cache/pin['file'];require(f.parent==cache and not f.is_symlink(),'unsafe input path')
        if not f.exists():
            require(not offline,'missing offline input '+pin['file'])
            require(pin['url'].startswith('https://repo.maven.apache.org/maven2/'),'non-official Maven URL')
            with urllib.request.urlopen(pin['url'],timeout=30) as r:b=r.read(32*1024*1024+1)
            require(len(b)<=32*1024*1024 and sha(b)==pin['sha256'],'download integrity '+pin['file']);f.write_bytes(b)
        with f.open('rb') as stream:require(hashlib.file_digest(stream,'sha256').hexdigest()==pin['sha256'],'input integrity '+pin['file'])
    return pins

def manifest(data):
    s=data.decode().replace('\r\n','\n').replace('\n ','')
    return dict(line.split(': ',1) for line in s.splitlines() if ': ' in line)

def inventory(cache,proof,pins):
    """Official NAR reference only. Inspect bundled jars and one declared NAR parent."""
    bundled=proof/'official-nar-jars';bundled.mkdir()
    rows=[];native=[];parent=None;netty=[]
    for nar in ['nifi-amqp-nar-2.12.0.nar','nifi-standard-services-api-nar-2.12.0.nar']:
        with zipfile.ZipFile(cache/nar) as z:
            mf=manifest(z.read('META-INF/MANIFEST.MF'))
            if nar.startswith('nifi-amqp-'):
                require(mf.get('Nar-Dependency-Id')=='nifi-standard-services-api-nar' and mf.get('Nar-Dependency-Version')=='2.12.0','unknown NAR parent')
                parent=mf
            else:require('Nar-Dependency-Id' not in mf,'uninspected additional parent NAR')
            for entry in z.infolist():
                if not entry.filename.startswith('META-INF/bundled-dependencies/') or not entry.filename.endswith('.jar'):continue
                require(entry.file_size<=32*1024*1024,'oversized nested input')
                data=z.read(entry);name=Path(entry.filename).name;f=bundled/name
                require(not f.exists(),'duplicate/shadowed official NAR JAR name '+name);f.write_bytes(data)
                with zipfile.ZipFile(f) as jar:
                    natives=[n for n in jar.namelist() if n.endswith(('.so','.dll','.dylib','.jnilib'))]
                rows.append({'nar':nar,'nar_sha256':next(p['sha256'] for p in pins if p['file']==nar),'entry':entry.filename,'sha256':sha(data),'native_paths':natives})
                if name.startswith('netty-'):netty.append(f)
    proc=next(r for r in rows if r['entry'].endswith('/nifi-amqp-processors-2.12.0.jar'))
    require(proc['sha256']==sha((cache/'nifi-amqp-processors-2.12.0.jar').read_bytes()),'bundled processor differs from standalone official reference')
    old=next(r for r in rows if r['entry'].endswith('/amqp-client-5.35.0.jar'))
    require(old['sha256']==EXPECTED_INPUT,'reference NAR RabbitMQ bytes do not match reported scan object')
    require(len(netty)==11 and all(p.name.endswith('-4.2.17.Final.jar') for p in netty),'unexpected reference Netty closure')
    save(proof/'official-nar-inventory.json',{'objects':rows,'amqp_manifest':parent,'docker_nar_match':False,'original_docker_occurrences':None})
    return bundled,sorted(netty),rows

def main():
    p=argparse.ArgumentParser();p.add_argument('--cache',type=Path,required=True);p.add_argument('--offline',action='store_true');p.add_argument('--jdk',type=Path,default=Path('/usr/lib/jvm/java-21-openjdk'));a=p.parse_args()
    c=a.cache.resolve();require(not c.is_relative_to(HERE),'cache must be outside source');c.mkdir(parents=True,exist_ok=True)
    # Never refresh existing JDK pins. javap is separately pinned for this supplement.
    for file in ['toolchain-pins.json','rabbit-tool-pins.json']:
        for n,h in json.loads((HERE/file).read_text()).items():
            with (a.jdk/n).open('rb') as stream:require(hashlib.file_digest(stream,'sha256').hexdigest()==h,'JDK pin mismatch '+n)
    proof=c/('proof-'+str(time.time_ns()));proof.mkdir()
    source_names=['TransportFixture.java','DefaultTransportProbe.java','NettyTransportProbe.java','verify_rabbit.py','maven_closure.py','verify.py','rabbit-pins.json','rabbit-closure-lock.json','rabbit-tool-pins.json','toolchain-pins.json']
    source_at_start={n:sha((HERE/n).read_bytes()) for n in source_names}
    pins=inputs(c,a.offline)
    closure=Closure(c,pins).resolve('com.rabbitmq:amqp-client:5.37.0')
    require(closure['required_coordinates']==json.loads((HERE/'rabbit-closure-lock.json').read_text()),'required closure changed')
    save(proof/'effective-required-closure.json',closure)
    bundled,oldnetty,rows=inventory(c,proof,pins)
    # Log real consumer bytecode; sources are corroborating reference, not runtime evidence.
    run([a.jdk/'bin/javap',*['-J'+x for x in JVM],'-c','-p','-classpath',bundled/'nifi-amqp-processors-2.12.0.jar','org.apache.nifi.amqp.processors.AbstractAMQPProcessor'],proof,'nifi-consumer-bytecode')
    bytecode=(proof/'nifi-consumer-bytecode.log').read_text()
    with zipfile.ZipFile(c/'nifi-amqp-processors-2.12.0-sources.jar') as z:
        source_text='\n'.join(z.read(n).decode() for n in z.namelist() if n.endswith('.java'))
    require('io.netty.' not in source_text and '.useNio(' not in source_text and '.netty(' not in source_text,'uninspected consumer transport source')
    require('ConnectionFactory.newConnection:' in bytecode and 'ConnectionFactory.setAutomaticRecoveryEnabled:' in bytecode,'consumer calls absent')
    require('ConnectionFactory.netty:' not in bytecode and 'ConnectionFactory.useNio:' not in bytecode,'consumer transport changed')
    sources=['TransportFixture.java','DefaultTransportProbe.java','NettyTransportProbe.java']
    classes=proof/'classes';classes.mkdir()
    jars=[c/(coord.split(':')[1]+'-'+coord.split(':')[2]+'.jar') for coord in closure['required_coordinates']]
    cp=':'.join(map(str,jars));run([a.jdk/'bin/javac',*['-J'+x for x in JVM],'-cp',cp,'-d',classes,*[HERE/n for n in sources]],proof,'compile-transports')
    client=c/'amqp-client-5.37.0.jar';slf=c/'slf4j-api-1.7.36.jar'
    # No-Netty JVM is the strongest control against assuming eager loading from a POM.
    tests={}
    for version in ['5.35.0','5.37.0']:
        limited=':'.join(map(str,[classes,c/f'amqp-client-{version}.jar',slf]))
        name='default-no-netty-'+version
        tests[name]=run([a.jdk/'bin/java',*JVM,'-cp',limited,'DefaultTransportProbe'],proof,name,timeout=30)
    nifi_slf=c/'slf4j-api-2.0.19.jar'
    tests['default-no-netty-nifi-slf4j-2.0.19']=run([a.jdk/'bin/java',*JVM,'-cp',':'.join(map(str,[classes,client,nifi_slf])),'DefaultTransportProbe'],proof,'default-no-netty-nifi-slf4j-2.0.19',timeout=30)
    for name,classpath in [('declared-4.2.18',jars),('reference-nar-4.2.17',[client,slf]+oldnetty),('declared-4.2.18-nifi-slf4j',[p for p in jars if p!=slf]+[nifi_slf]),('reference-nar-4.2.17-nifi-slf4j',[client,nifi_slf]+oldnetty)]:
        tests[name]=run([a.jdk/'bin/java',*JVM,'-Dio.netty.allocator.numDirectArenas=1','-Dio.netty.allocator.numHeapArenas=1','-cp',':'.join(map(str,[classes]+classpath)),'NettyTransportProbe'],proof,'netty-'+name,timeout=30)
    abi={'rabbitmq':compare(c/'amqp-client-5.35.0.jar',client),'netty':{}}
    for old in oldnetty:
        new=c/old.name.replace('4.2.17.Final','4.2.18.Final');abi['netty'][old.name]=compare(old,new)
    save(proof/'bounded-abi.json',abi)
    platform=[]
    for jar in jars:
        with zipfile.ZipFile(jar) as z:
            versions={n:int.from_bytes(z.read(n)[6:8],'big') for n in z.namelist() if n.endswith('.class')}
            platform.append({'jar':jar.name,'base_classes_above_java8':{n:v for n,v in versions.items() if not n.startswith('META-INF/') and v>52},'multi_release_classes':{n:v for n,v in versions.items() if n.startswith('META-INF/')},'native_resources':[n for n in z.namelist() if n.endswith(('.so','.dll','.dylib','.jnilib'))]})
    save(proof/'platform-constraints.json',platform)
    clean=not abi['rabbitmq']['removed_or_changed'] and all(not x['removed_or_changed'] and not x['missing_native_paths'] for x in abi['netty'].values())
    usage={'max_child_rss_kib':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,'self_max_rss_kib':int(next(line.split()[1] for line in Path('/proc/self/status').read_text().splitlines() if line.startswith('VmHWM:')))}
    save(proof/'resource-usage.json',usage);require(max(usage.values())<=512*1024,'RSS over budget')
    source={n:sha((HERE/n).read_bytes()) for n in sources+['verify_rabbit.py','maven_closure.py','verify.py','rabbit-pins.json','rabbit-closure-lock.json','rabbit-tool-pins.json','toolchain-pins.json']}
    require(source==source_at_start,'source changed during verification')
    output={'status':'transport-component-tested-nar-mapping-pending' if clean else 'transport-tested-abi-review-pending','component_tests':tests,'required_closure_pinned':True,'required_coordinates':closure['required_coordinates'],'input_rabbitmq_sha256':EXPECTED_INPUT,'replacement_file':client.name,'replacement_url':next(p['url'] for p in pins if p['file']==client.name),'replacement_sha256':sha(client.read_bytes()),'official_reference_nar_sha256':next(p['sha256'] for p in pins if p['file']=='nifi-amqp-nar-2.12.0.nar'),'nifi_managed_slf4j_reference':'2.0.19; API tested, actual logger provider/classloader pending','reference_consumer_uses':'blocking SocketFrameHandlerFactory; automatic recovery disabled','tested_reference_netty_versions':['4.2.17.Final','4.2.18.Final'],'source_sha256':source,'resource_usage':usage,'patched':False,'docker_occurrence_mapping':None,'final_nifi_acceptance':False,'full_image_scan':False,'proof_directory':str(proof)}
    save(proof/'rabbit-transport-result.json',output);print(json.dumps(output,indent=2))
if __name__=='__main__':main()
