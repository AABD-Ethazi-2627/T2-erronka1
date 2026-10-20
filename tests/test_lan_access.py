"""The opt-in LAN overlay must expose only authenticated gateway ports."""

import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAN_IP = "192.0.2.10"


class LanAccessTests(unittest.TestCase):
    def test_direct_lan_ports_use_gateway(self):
        if shutil.which("docker") is None:
            self.skipTest("Docker Compose unavailable")
        env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("CNC_")
        }
        env.update(
            CNC_LAN_BIND_IP=LAN_IP,
            CNC_LAN_HOST=LAN_IP,
            CNC_LAN_CERT_DIR="/tmp/cnc-lan-cert-fixture",
            CNC_LAN_CERT_UID="1000",
            CNC_LAN_CERT_GID="1000",
            CNC_NIFI_CERT_NAME="localhost",
        )
        result = subprocess.run(
            [
                "docker",
                "compose",
                "--env-file",
                "/dev/null",
                "-f",
                "docker-compose.yml",
                "-f",
                "docker-compose.lan.yml",
                "--profile",
                "dashboard",
                "config",
                "--format",
                "json",
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=20,
            check=True,
        )
        services = json.loads(result.stdout)["services"]
        gateway_ports = {
            port["published"]: port["host_ip"]
            for port in services["lan-gateway"]["ports"]
        }
        self.assertEqual(
            gateway_ports,
            {port: LAN_IP for port in ("18080", "19092", "19200", "15601", "18001")},
        )
        for name, service in services.items():
            if name != "lan-gateway":
                self.assertTrue(
                    all(
                        port["host_ip"] == "127.0.0.1"
                        for port in service.get("ports", [])
                    ),
                    name,
                )
        self.assertIn(
            f"EXTERNAL://{LAN_IP}:19092",
            services["kafka"]["environment"]["KAFKA_ADVERTISED_LISTENERS"],
        )


if __name__ == "__main__":
    unittest.main()
