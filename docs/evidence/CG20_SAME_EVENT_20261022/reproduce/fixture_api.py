"Synthetic in-memory models through the real canonical HTTP/SQLite API."

import asyncio
import json
import socket
import sys
from pathlib import Path

import uvicorn
from test_scoring_replay import AnomalyDouble, RiskDouble, manifest

from scoring.score_api import create_app

root = Path(sys.argv[1])
state = json.loads((root / "state.json").read_text())
app = create_app(root / "absent.json", ledger_path=root / "api.sqlite3")
risk = RiskDouble()
app.state.models = {"rf.pkl": risk, "if.pkl": AnomalyDouble()}
app.state.manifest = manifest()


async def fixture(scope, receive, send):
    if scope["type"] != "http":
        return await app(scope, receive, send)
    mode = (root / "api-mode.txt").read_text().strip()
    if scope["path"] == "/metrics":
        body = json.dumps({"risk_calls": risk.calls}).encode()
        await send({"type": "http.response.start", "status": 200, "headers": []})
        return await send({"type": "http.response.body", "body": body})
    if mode in ("409", "413", "422", "503"):
        await send({"type": "http.response.start", "status": int(mode), "headers": []})
        return await send(
            {
                "type": "http.response.body",
                "body": json.dumps({"fixture_status": int(mode)}).encode(),
            }
        )
    messages = []

    async def capture(message):
        messages.append(message)

    await app(scope, receive, capture)
    with (root / "api-calls.jsonl").open("a") as log:
        log.write(
            json.dumps(
                {
                    "path": scope["path"],
                    "risk_calls": risk.calls,
                    "mode": mode,
                    "status": next(
                        m["status"]
                        for m in messages
                        if m["type"] == "http.response.start"
                    ),
                    "body": "".join(m.get("body", b"").decode() for m in messages),
                }
            )
            + "\n"
        )
    if mode == "lost-after-commit":
        await asyncio.sleep(2)
    for message in messages:
        await send(message)


sockets = []
for address in ("127.0.0.1", state["gateway"]):
    listener = socket.socket()
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind((address, state["api_port"]))
    listener.listen(128)
    sockets.append(listener)
uvicorn.Server(
    uvicorn.Config(fixture, lifespan="off", log_level="error", access_log=False)
).run(sockets=sockets)
