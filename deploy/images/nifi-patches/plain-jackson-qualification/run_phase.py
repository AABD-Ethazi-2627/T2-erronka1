#!/usr/bin/env python3
"""VM-only bounded orchestrator; caller holds remote-heavy.lock.

No NiFi process is started. Only the exact candidate image runs Python/Java.
"""
import argparse
import hashlib
import json
import re
import subprocess
import time
import uuid
from pathlib import Path

BASE=Path('/opt/cnc-guard/evidence/plain-jackson-qualification-20261106')
IMAGE='sha256:03f3e9a19dbce166304ec63a685c44f2da07239e5659d843c798c7f32f7012d5'
PYHOME=Path('/opt/cnc-guard/venvs/py311/bin/python').resolve().parent.parent
PYTHON=PYHOME/'bin/python3.11'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2,sort_keys=True)+'\n')
def main():
 global BASE
 p=argparse.ArgumentParser();p.add_argument('mode');p.add_argument('--context',type=int);p.add_argument('--proof-root',type=Path,default=BASE);a=p.parse_args()
 if not re.fullmatch(r'[a-z][a-z0-9-]{0,63}',a.mode):raise ValueError('invalid phase label')
 if not a.proof_root.is_dir() or a.proof_root.is_symlink():raise ValueError('proof root must be an existing directory')
 BASE=a.proof_root.resolve()
 label=a.mode+('-v2' if a.mode=='inventory' else '')+('-jdk21' if a.mode=='analyze' and (BASE/'jdk-classes').exists() else '')+('-'+str(a.context) if a.context is not None else '')
 out=BASE/(label+'.json')
 for existing in (out,BASE/(label+'.stdout'),BASE/(label+'.stderr'),BASE/(label+'-execution.json')):
  if existing.exists() or existing.is_symlink():raise ValueError('phase evidence already exists: '+str(existing))
 cmd=['docker','run','--rm','--pull=never','--name','plain-jackson-'+uuid.uuid4().hex[:10],'--read-only','--network','none','--cpus','1','--cpuset-cpus','0','--memory','512m','--memory-swap','512m','--pids-limit','64','--cap-drop','ALL','--security-opt','no-new-privileges','--user','1000:1000','--ulimit','core=0:0','--tmpfs','/tmp:rw,nosuid,nodev,size=64m','--mount',f'type=bind,src={PYHOME},dst={PYHOME},readonly','--mount',f'type=bind,src={BASE},dst=/proof','--mount','type=bind,src=/usr/lib/jvm/java-21-openjdk-amd64,dst=/jdk,readonly','--mount','type=bind,src=/etc/java-21-openjdk,dst=/etc/java-21-openjdk,readonly','--mount',f'type=bind,src={BASE}/tools,dst=/proof/tools,readonly','--mount',f'type=bind,src={BASE}/pins.json,dst=/proof/pins.json,readonly','--mount',f'type=bind,src={BASE}/cache,dst=/proof/cache,readonly','--env','PYTHONDONTWRITEBYTECODE=1','--entrypoint',str(PYTHON),IMAGE,'-B']
 if a.mode in ('inventory','analyze'):
  cmd+=['/proof/tools/qualify.py',a.mode,'--pins','/proof/pins.json','--output','/proof/'+out.name]
  if a.mode=='analyze' and (BASE/'jdk-classes').exists():cmd+=['--jdk-classes','/proof/jdk-classes']
  if a.mode=='analyze':cmd+=['--inventory','/proof/inventory.json','--cache','/proof/cache','--context',str(a.context)]
 else:cmd+=['/proof/tools/runtime.py','--output','/proof/'+out.name]
 tool_before={p.name:sha(p) for p in (BASE/'tools').glob('*') if p.is_file()}
 start=time.monotonic();name=cmd[cmd.index('--name')+1];inspection=None
 with (BASE/(label+'.stdout')).open('w') as so,(BASE/(label+'.stderr')).open('w') as se:
  proc=subprocess.Popen(cmd,stdout=so,stderr=se)
  try:
   time.sleep(.15)
   q=subprocess.run(['docker','inspect',name],capture_output=True,text=True,timeout=8,check=False)
   if q.returncode==0:inspection=json.loads(q.stdout)[0]
   rc=proc.wait(timeout=max(1,165-(time.monotonic()-start)))
  except subprocess.TimeoutExpired:proc.kill();proc.wait();rc=124
  finally:
   cleanup=subprocess.run(['docker','rm','-f','-v',name],capture_output=True,text=True,timeout=8,check=False)
 record={'command':cmd,'returncode':rc,'elapsed_seconds':round(time.monotonic()-start,3),'timeout_seconds':165,'cleanup_returncode':cleanup.returncode,'cleanup_stdout':cleanup.stdout,'cleanup_stderr':cleanup.stderr,'inspection':inspection,'tool_inputs_before':tool_before,'tool_inputs_after':{p.name:sha(p) for p in (BASE/'tools').glob('*') if p.is_file()},'pins_sha256':sha(BASE/'pins.json'),'image_id':IMAGE,'runtime_approved':False}
 save(BASE/(label+'-execution.json'),record)
 print(json.dumps({k:record[k] for k in ('returncode','elapsed_seconds','image_id')}))
 if rc:print((BASE/(label+'.stderr')).read_text()[-1200:])
 raise SystemExit(rc)
if __name__=='__main__':main()
