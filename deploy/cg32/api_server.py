"""Real scoring API with the pinned bundle plus a server-side timing log (CG32).

The product app is used unchanged: ``create_app(manifest)`` loads and verifies
the bundle. An outer ASGI wrapper records, per request, monotonic start/end of
the whole HTTP exchange and the status. It never logs bodies or headers.

Usage: api_server.py MANIFEST LEDGER TIMING_JSONL HOST[,HOST...] PORT
"""

import json
import socket
import sys
import time
from pathlib import Path

import uvicorn

from scoring.score_api import create_app

manifest, ledger, timing_path = (Path(arg) for arg in sys.argv[1:4])
hosts = sys.argv[4].split(",")
port = int(sys.argv[5])
app = create_app(manifest, ledger_path=ledger)
timing = timing_path.open("x", buffering=1)


async def timed(scope, receive, send):
    if scope["type"] != "http":
        return await app(scope, receive, send)
    start = time.monotonic()
    status = []

    async def capture(message):
        if message["type"] == "http.response.start":
            status.append(message["status"])
        await send(message)

    try:
        await app(scope, receive, capture)
    finally:
        end = time.monotonic()
        timing.write(
            json.dumps(
                {
                    "path": scope["path"],
                    "status": status[0] if status else None,
                    "start_mono": start,
                    "end_mono": end,
                    "ms": (end - start) * 1000,
                }
            )
            + "\n"
        )


sockets = []
for host in hosts:
    listener = socket.socket()
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind((host, port))
    listener.listen(128)
    sockets.append(listener)
uvicorn.Server(
    uvicorn.Config(timed, lifespan="on", log_level="warning", access_log=False)
).run(sockets=sockets)
