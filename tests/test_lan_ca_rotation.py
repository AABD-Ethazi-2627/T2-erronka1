"""Opt-in real TLS regression for the documented complete-CA emergency rotation.

No production services or certificates are used. CI runs the pinned HAProxy
container; native HAProxy is supported for an isolated developer check.
"""

import json
import os
import re
import shutil
import socket
import socketserver
import ssl
import subprocess
import tempfile
import threading
import time
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Echo(socketserver.BaseRequestHandler):
    def handle(self):
        while data := self.request.recv(1024):
            self.request.sendall(data)


class EchoServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@unittest.skipUnless(
    os.environ.get("CNC_RUN_LAN_TLS_TESTS") == "1",
    "Opt-in isolated TLS test; required by the LAN rotation CI job",
)
class LanCARotationTests(unittest.TestCase):
    def generate(self, destination):
        subprocess.run(
            [
                "bash",
                str(ROOT / "scripts/create_lan_certs.sh"),
                "127.0.0.1",
                str(destination),
            ],
            check=True,
            capture_output=True,
            timeout=120,
        )

    @contextmanager
    def gateway(self, certificates, backend_port):
        production = (ROOT / "lan/haproxy.cfg").read_text()
        binds = re.findall(r"^    bind :\d+ (.+)$", production, re.MULTILINE)
        self.assertEqual(len(binds), 5)
        for bind in binds:
            self.assertIn("ca-file /certs/clients-ca.pem verify required", bind)
        ports = [free_port() for _ in binds]
        config = certificates / "test-haproxy.cfg"
        contents = "global\n    ssl-default-bind-options ssl-min-ver TLSv1.2\n"
        contents += "defaults\n    mode tcp\n    timeout connect 2s\n"
        contents += "    timeout client 1h\n    timeout server 1h\n"
        for index, (port, bind) in enumerate(zip(ports, binds, strict=True)):
            bind = bind.replace("/certs/", str(certificates / "gateway") + "/")
            contents += f"frontend test{index}\n    bind 127.0.0.1:{port} {bind}\n"
            contents += "    default_backend echo\n"
        contents += f"backend echo\n    server echo 127.0.0.1:{backend_port}\n"
        config.write_text(contents)
        backend = os.environ.get("CNC_LAN_TLS_BACKEND", "docker")
        name = "cnc-lan-tls-" + uuid.uuid4().hex[:12]
        if backend == "docker":
            image = json.loads((ROOT / "deploy/images.json").read_text())["haproxy"]
            self.assertIn(
                "image: " + image, (ROOT / "docker-compose.lan.yml").read_text()
            )
            command = [
                "docker",
                "run",
                "--rm",
                "--name",
                name,
                "--network",
                "host",
                "--user",
                f"{os.getuid()}:{os.getgid()}",
                "--volume",
                f"{certificates.parent}:{certificates.parent}:ro",
                image,
                "haproxy",
                "-db",
                "-f",
                str(config),
            ]
        elif backend == "native":
            command = [
                os.environ.get("CNC_HAPROXY", "haproxy"),
                "-db",
                "-f",
                str(config),
            ]
        else:
            self.fail("Unknown TLS test backend")
        with (certificates / "gateway.log").open("wb") as log:
            process = subprocess.Popen(command, stdout=log, stderr=log)
            try:
                deadline = time.monotonic() + 20
                while True:
                    self.assertIsNone(
                        process.poll(), "HAProxy exited; inspect gateway.log"
                    )
                    try:
                        with socket.create_connection(
                            ("127.0.0.1", ports[0]), timeout=0.2
                        ):
                            break
                    except OSError:
                        if time.monotonic() >= deadline:
                            self.fail("HAProxy did not start")
                        time.sleep(0.05)
                yield ports
            finally:
                if backend == "docker":
                    # Like Compose stop, wait for the container to terminate;
                    # image soft-stop must not preserve an old authenticated flow.
                    subprocess.run(
                        ["docker", "stop", "--time", "1", name],
                        check=True,
                        capture_output=True,
                        timeout=15,
                    )
                else:
                    process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
                    raise

    def context(self, trust, client=None, version=None):
        context = ssl.create_default_context(cafile=str(trust / "clients/ca.crt"))
        if client:
            root, number = client
            context.load_cert_chain(
                str(root / f"clients/student-{number}.crt"),
                str(root / f"clients/student-{number}.key"),
            )
        if version:
            context.minimum_version = context.maximum_version = version
        return context

    def connect(self, context, port, session=None):
        plain = socket.create_connection(("127.0.0.1", port), timeout=2)
        try:
            return context.wrap_socket(
                plain, server_hostname="127.0.0.1", session=session
            )
        except BaseException:
            plain.close()
            raise

    def echo(self, context, port, session=None):
        with self.connect(context, port, session) as connection:
            connection.sendall(b"rotation-proof")
            self.assertEqual(connection.recv(1024), b"rotation-proof")

    def assert_rejected(self, context, port, session=None):
        # A TLS1.3 certificate alert may arrive only after wrap_socket returns.
        try:
            with self.connect(context, port, session) as connection:
                connection.sendall(b"must-not-reach-backend")
                self.assertEqual(connection.recv(1024), b"")
        except (ssl.SSLError, ConnectionError):
            return

    def test_all_frontends_retire_old_clients_and_sessions(self):
        self.assertIsNotNone(shutil.which("openssl"))
        with tempfile.TemporaryDirectory(
            dir=os.environ.get("CNC_LAN_TEST_TMP")
        ) as directory:
            root = Path(directory)
            old, new = root / "old", root / "new"
            self.generate(old)
            self.generate(new)
            self.assertNotEqual(
                (old / "clients/ca.crt").read_bytes(),
                (new / "clients/ca.crt").read_bytes(),
            )
            with EchoServer(("127.0.0.1", 0), Echo) as echo:
                thread = threading.Thread(target=echo.serve_forever, daemon=True)
                thread.start()
                try:
                    held, sessions = [], []
                    try:
                        with self.gateway(old, echo.server_address[1]) as old_ports:
                            for port in old_ports:
                                for number in range(1, 5):
                                    with self.subTest(
                                        stage="before", port=port, client=number
                                    ):
                                        self.echo(
                                            self.context(old, (old, number)), port
                                        )
                            for version in (
                                ssl.TLSVersion.TLSv1_2,
                                ssl.TLSVersion.TLSv1_3,
                            ):
                                context = self.context(old, (old, 1), version)
                                context.load_verify_locations(
                                    cafile=str(new / "clients/ca.crt")
                                )
                                connection = self.connect(context, old_ports[0])
                                held.append(connection)
                                connection.sendall(b"before-stop")
                                self.assertEqual(connection.recv(1024), b"before-stop")
                                session = connection.session
                                self.assertTrue(session.has_ticket)
                                with self.connect(
                                    context, old_ports[0], session
                                ) as resumed:
                                    self.assertTrue(resumed.session_reused)
                                    resumed.sendall(b"resumed-before-stop")
                                    self.assertEqual(
                                        resumed.recv(1024), b"resumed-before-stop"
                                    )
                                sessions.append((context, session))
                        for connection in held:
                            try:
                                connection.sendall(b"after-stop")
                                self.assertEqual(connection.recv(1024), b"")
                            except (ssl.SSLError, ConnectionError):
                                pass
                        with self.gateway(new, echo.server_address[1]) as new_ports:
                            for port in new_ports:
                                for number in range(1, 5):
                                    with self.subTest(
                                        stage="new", port=port, client=number
                                    ):
                                        self.echo(
                                            self.context(new, (new, number)), port
                                        )
                                    with self.subTest(
                                        stage="old-rejected", port=port, client=number
                                    ):
                                        self.assert_rejected(
                                            self.context(new, (old, number)), port
                                        )
                                self.assert_rejected(self.context(new), port)
                            for context, session in sessions:
                                self.assert_rejected(context, new_ports[0], session)
                    finally:
                        for connection in held:
                            connection.close()
                finally:
                    echo.shutdown()
                    thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
