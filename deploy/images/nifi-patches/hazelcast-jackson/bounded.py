"""Serialized bounded local Java launcher. Lock once, outside every child process."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess

LOCK = '/home/tears/.cache/cnc-integration-audit-20261103/candidate-heavy.lock'
JDK = Path('/usr/lib/jvm/java-21-openjdk')

def digest(path):
    return hashlib.file_digest(Path(path).open('rb'), 'sha256').hexdigest()

def run(args, output):
    def limits():
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
        os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    output = Path(output)
    home = output.parent/'private-home'
    home.mkdir(exist_ok=True)
    args = list(args)
    args.insert(1, ('-J' if str(args[0]).endswith('/javac') else '')+'-Duser.home='+str(home))
    args.insert(1, ('-J' if str(args[0]).endswith('/javac') else '')+'-Djava.io.tmpdir='+str(home))
    with open(LOCK, 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        p = subprocess.run(args, env={'PATH':'/usr/bin', 'LANG':'C.UTF-8', 'LC_ALL':'C.UTF-8', 'HOME':str(home), 'TMPDIR':str(home)},
                           preexec_fn=limits, timeout=40, capture_output=True)
    output = Path(output)
    with output.open('xb') as f:
        f.write(p.stdout + p.stderr)
    with output.with_suffix(output.suffix+'.json').open('x') as f:
        json.dump({'command':list(map(str,args)), 'exit':p.returncode,
                   'log_sha256':digest(output), 'heap_mib':256,'metaspace_mib':96,
                   'wall_seconds':40,'cpu_seconds':30,'cpus':1,'cores':False}, f, indent=2)
    if p.returncode:
        raise RuntimeError('Java failure; see '+str(output))

FLAGS = ['-Xmx256m', '-XX:MaxMetaspaceSize=96m', '-XX:ActiveProcessorCount=1',
         '-XX:ReservedCodeCacheSize=48m', '-XX:MaxDirectMemorySize=32m', '-XX:-CreateCoredumpOnCrash']
