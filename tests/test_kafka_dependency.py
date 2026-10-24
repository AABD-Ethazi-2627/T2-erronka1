"""Catch warnings on the first Kafka import, independent of discovery order."""

import importlib.metadata
import json
import subprocess
import sys
import unittest


class KafkaDependencyTests(unittest.TestCase):
    def test_fresh_import_and_all_protocol_resources_without_warnings(self):
        try:
            importlib.metadata.version("kafka-python")
        except importlib.metadata.PackageNotFoundError:
            self.skipTest("optional Kafka transport: uv sync --locked --extra kafka")
        source = """
import importlib
import importlib.resources
import json
import kafka
import re
from kafka.net.connection import KafkaConnection
from kafka.net.manager import KafkaConnectionManager
for config in (KafkaConnection.DEFAULT_CONFIG, KafkaConnectionManager.DEFAULT_CONFIG):
    wire_version = config['client_software_version']
    assert re.fullmatch(r'[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?', wire_version)
    assert wire_version == kafka.__version__.replace('+', '-')
loader = importlib.import_module('kafka.protocol.schemas.load_json')
package = importlib.import_module('kafka.protocol.schemas.resources')
resources = importlib.resources.files(package)
names = sorted(p.name for p in resources.iterdir() if p.name.endswith('.json'))
assert len(names) == 108, len(names)
for name in names:
    string_result = loader.load_json(name[:-5], package.__name__)
    module_result = loader.load_json(name[:-5], package)
    assert string_result == module_result
try:
    loader.load_json('nonexistent-cnc-guard-schema')
except FileNotFoundError:
    pass
else:
    raise AssertionError('Missing schema must raise FileNotFoundError')
print(json.dumps({'version': kafka.__version__, 'schemas': len(names)}))
"""
        # -I excludes PYTHONPATH/user site and inherited warning configuration.
        # "always" exposes every warning; "error" independently makes any fatal.
        for mode in ("always", "error"):
            with self.subTest(warnings=mode):
                result = subprocess.run(
                    [sys.executable, "-I", "-B", "-W", mode, "-c", source],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(result.stderr, "")
                self.assertEqual(json.loads(result.stdout)["schemas"], 108)


if __name__ == "__main__":
    unittest.main()
