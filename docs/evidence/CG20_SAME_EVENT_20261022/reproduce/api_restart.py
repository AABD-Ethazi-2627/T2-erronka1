import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import httpx

E = Path(__file__).resolve().parent
C = E.parents[2] / "_worktrees/t2-cg20-api-kibana-20261022"
root = E / "lab-01"
state = json.loads((root / "state.json").read_bytes())
endpoint = "http://127.0.0.1:" + str(state["api_port"])
with httpx.Client(trust_env=False, timeout=10) as client:
    calls_before = client.get(endpoint + "/metrics").json()["risk_calls"]
pid = state["api_pid"]
command = Path("/proc/" + str(pid) + "/cmdline").read_bytes()
assert str(E / "fixture_api.py").encode() in command and str(root).encode() in command
os.kill(pid, signal.SIGTERM)
for _ in range(60):
    try:
        status = Path("/proc/" + str(pid) + "/stat").read_text().split()[2]
    except FileNotFoundError:
        break
    if status == "Z":
        break
    time.sleep(0.1)
else:
    raise RuntimeError("Own API did not stop")
log = (root / "api-restarted.log").open("xb")
process = subprocess.Popen(
    [sys.executable, "-B", str(E / "fixture_api.py"), str(root)],
    cwd=C,
    env={**os.environ, "PYTHONPATH": str(C) + ":" + str(C / "tests")},
    stdout=log,
    stderr=subprocess.STDOUT,
    start_new_session=True,
)
log.close()
state["api_pid"] = process.pid
(root / "state.json").write_bytes((json.dumps(state, indent=2) + "\n").encode())
with httpx.Client(trust_env=False, timeout=10) as client:
    for _ in range(100):
        try:
            result = client.get(endpoint + "/metrics")
            if result.status_code == 200:
                break
        except httpx.TransportError:
            pass
        time.sleep(0.1)
    else:
        raise RuntimeError("Own API did not restart")
    assert result.json()["risk_calls"] == 0
print("Own API restarted; automatic worker will recover from retained ledger")
