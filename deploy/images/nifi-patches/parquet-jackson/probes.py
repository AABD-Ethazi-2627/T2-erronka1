"""Bounded old/fixed actual-wrapper and real Parquet consumer controls."""
import argparse
import json
from pathlib import Path

from bounded import FLAGS, JDK, digest, run
from prepare import (
    HERE,
    checked,
    fresh_output,
    require,
    save,
    source_files,
    validate_pins,
)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--cache',type=Path,required=True)
    p.add_argument('--proof',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();cache=a.cache.resolve();proof=a.proof.resolve()
    summary=json.loads((proof/'summary.json').read_text())
    require(Path(summary['candidate']).name==summary['candidate'],'unsafe candidate path')
    candidate=proof/summary['candidate'];checked(candidate,summary['candidate_sha256'])
    require(source_files()==summary['source'],'preparation/probe source mismatch')
    out=fresh_output(a.output,[HERE.parents[3],proof,cache])
    source_before=source_files()
    pins=json.loads((HERE/'pins.json').read_text())+json.loads((HERE/'consumer-pins.json').read_text())
    validate_pins(pins)
    before={r['file']:digest(cache/r['file']) for r in pins}
    for r in pins:checked(cache/r['file'],r['sha256'])
    support=json.loads((HERE/'support-lock.json').read_text())
    for n,h in support.items():checked(HERE.parent/n,h)
    jdk=json.loads((HERE.parent/'jackson/jdk21-pins.json').read_text())
    for n,h in jdk.items():checked(JDK/n,h)
    consumers=[cache/r['file'] for r in json.loads((HERE/'consumer-pins.json').read_text())
      if r['file'].endswith('.jar') and not r['file'].endswith('-sources.jar')]
    for label,jar in [('old',cache/'parquet-jackson-1.18.1.jar'),('fixed',candidate)]:
        folder=out/label;folder.mkdir()
        src=(HERE/'JacksonProbe.java.in').read_text().replace('@NS@','shaded.parquet.com.fasterxml.jackson')
        (folder/'JacksonProbe.java').write_text(src)
        run([JDK/'bin/javac',*['-J'+x for x in FLAGS],'-cp',jar,'-d',folder,folder/'JacksonProbe.java'],folder/'compile-jackson.log')
        run([JDK/'bin/java',*FLAGS,'-cp',str(folder)+':'+str(jar),'JacksonProbe',str(label=='fixed').lower(),'false','true'],folder/'run-jackson.log')
        cp=':'.join(map(str,[jar,*consumers]))
        run([JDK/'bin/javac',*['-J'+x for x in FLAGS],'-cp',cp,'-d',folder,HERE/'ParquetProbe.java'],folder/'compile-parquet.log')
        run([JDK/'bin/java',*FLAGS,'-Xlog:class+load=info:file='+str(folder/'classload.log'),'-cp',str(folder)+':'+cp,'ParquetProbe',folder/'normal.parquet'],folder/'run-parquet.log')
        loaded=(folder/'classload.log').read_text()
        require('org.apache.hadoop.util.NativeCodeLoader' not in loaded,'unexpected native Hadoop loader path')
    require(source_files()==source_before,'probe source drift')
    for r in pins:checked(cache/r['file'],r['sha256'])
    for n,h in support.items():checked(HERE.parent/n,h)
    for n,h in jdk.items():checked(JDK/n,h)
    checked(candidate,summary['candidate_sha256'])
    save(out/'summary.json',{'status':'bounded-wrapper-and-Parquet-consumer-probes-passed','runtime_approved':False,
      'candidate_sha256':summary['candidate_sha256'],'source':source_before,'inputs':before,'java_commands':8,
      'consumer_classpath':[p.name for p in consumers], 'file_scope':'three-row UNCOMPRESSED Parquet file/footer; no compressed codec or NiFi acceptance'})
if __name__=='__main__':main()
