"""One bounded process, one finite-wait flock; no inherited Java environment."""
import hashlib
import json
import os
import subprocess

try:
    import resource
except ImportError:
    resource = None
from pathlib import Path

LOCK = '/home/tears/.cache/cnc-integration-audit-20261103/candidate-heavy.lock'
JDK = Path('/usr/lib/jvm/java-21-openjdk')
FLAGS = ['-Xmx256m', '-XX:MaxMetaspaceSize=96m', '-XX:ActiveProcessorCount=1',
         '-XX:ReservedCodeCacheSize=48m', '-XX:MaxDirectMemorySize=32m', '-XX:-CreateCoredumpOnCrash']

def digest(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def run(args, output):
    if resource is None:
        raise RuntimeError('bounded execution requires POSIX resource controls')
    def limits():
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
        os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    output=Path(output)
    if output.exists() or output.is_symlink():raise ValueError('existing log')
    home=output.parent/'private-home';home.mkdir(exist_ok=True)
    args=list(map(str,args));prefix='-J' if args[0].endswith('/javac') else ''
    args[1:1]=[prefix+'-Duser.home='+str(home),prefix+'-Djava.io.tmpdir='+str(home)]
    command=['/usr/bin/flock','--no-fork','--timeout','10',LOCK,*args]
    status='finished'
    try:
        p=subprocess.run(command, env={'PATH':'/usr/bin','LANG':'C.UTF-8','LC_ALL':'C.UTF-8',
          'HOME':str(home),'TMPDIR':str(home)},preexec_fn=limits,timeout=40,capture_output=True,check=False)
        code=p.returncode;data=p.stdout+p.stderr
    except subprocess.TimeoutExpired as e:
        code=None;data=(e.stdout or b'')+(e.stderr or b'');status='wall-timeout'
    with output.open('xb') as f:f.write(data)
    with output.with_suffix(output.suffix+'.json').open('x') as f:
        json.dump({'command':command,'exit':code,'status':status,'log_sha256':digest(output),
          'heap_mib':256,'metaspace_mib':96,'direct_mib':32,'wall_seconds':40,'cpu_seconds':30,
          'lock_wait_seconds':10,'cpus':1,'cores':False},f,indent=2)
    if code!=0:raise RuntimeError('bounded command failed; see '+str(output))
