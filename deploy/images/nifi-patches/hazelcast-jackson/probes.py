"""Old/fixed actual-wrapper probes; no service or cluster startup."""
import argparse
from pathlib import Path
from bounded import run, FLAGS, JDK, digest
from prepare import checked, save, HERE, OLD

def main():
    p=argparse.ArgumentParser();p.add_argument('--cache',type=Path,required=True);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.mkdir();before={str(x):digest(x) for x in [a.candidate,a.cache/'hazelcast-5.7.0.jar',a.cache/'jackson-annotations-2.21.jar']}
    source_before={p.name:digest(p) for p in HERE.iterdir() if p.suffix in ('.py','.java','.in') or p.name=='pins.json'}
    import json
    for r in json.loads((HERE/'pins.json').read_text()):checked(a.cache/r['file'],r['sha256'])
    for n,h in json.loads((HERE.parent/'jackson/jdk21-pins.json').read_text()).items():checked(JDK/n,h)
    for label,jar in [('old',a.cache/'hazelcast-5.7.0.jar'),('fixed',a.candidate)]:
        for family,ns in [('2','com.fasterxml.jackson'),('3','tools.jackson')]:
            folder=a.output/(label+'-'+family);folder.mkdir()
            src=(HERE/'JacksonProbe.java.in').read_text().replace('@NS@','com.hazelcast.shaded.'+ns)
            # Verify actual loaded implementation identity, beyond metadata.
            src=src.replace('boolean fixed = Boolean.parseBoolean(args[0]);', 'System.out.println("code-source="+ObjectMapper.class.getProtectionDomain().getCodeSource().getLocation()+" version="+new JsonMapper().version());\n        boolean fixed = Boolean.parseBoolean(args[0]);')
            (folder/'JacksonProbe.java').write_text(src)
            cp=str(jar)+':'+str(a.cache/'jackson-annotations-2.21.jar')
            run([str(JDK/'bin/javac'),*['-J'+x for x in FLAGS],'-cp',cp,'-d',str(folder),str(folder/'JacksonProbe.java')],folder/'compile.log')
            run([str(JDK/'bin/java'),*FLAGS,'-cp',str(folder)+':'+cp,'JacksonProbe',str(label=='fixed').lower(),'false',str(label=='fixed').lower()],folder/'run.log')
        folder=a.output/(label+'-hazelcast');folder.mkdir()
        cp=str(jar)+':'+str(a.cache/'jackson-annotations-2.21.jar')
        run([str(JDK/'bin/javac'),*['-J'+x for x in FLAGS],'-cp',cp,'-d',str(folder),str(HERE/'HazelcastProbe.java')],folder/'compile.log')
        run([str(JDK/'bin/java'),*FLAGS,'-cp',str(folder)+':'+cp,'HazelcastProbe'],folder/'run.log')
    for n,h in before.items():checked(Path(n),h)
    assert source_before=={p.name:digest(p) for p in HERE.iterdir() if p.suffix in ('.py','.java','.in') or p.name=='pins.json'}, 'probe source drift'
    for n,h in json.loads((HERE.parent/'jackson/jdk21-pins.json').read_text()).items():checked(JDK/n,h)
    save(a.output/'summary.json',{'status':'bounded-wrapper-probes-passed','runtime_approved':False,'inputs':before,'source':source_before,'java_commands':12})
if __name__=='__main__':main()
