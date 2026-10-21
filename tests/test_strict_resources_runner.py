"""Exercise discovery-time diagnostics in a fresh interpreter, with real resources."""

import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "tests/run_strict_resources.py"


class StrictResourcesRunnerTests(unittest.TestCase):
    def run_discovery(self, source):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "test_discovery_probe.py").write_text(
                textwrap.dedent(source), encoding="utf-8"
            )
            return subprocess.run(
                [sys.executable, str(RUNNER), directory],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )

    def test_clean_discovery_completes_both_passes(self):
        result = self.run_discovery("import unittest\n")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for pass_number in (1, 2):
            self.assertIn(f"pass={pass_number} run=0", result.stdout)
        self.assertEqual(result.stdout.count("warnings=0 unraisables=0"), 2)
        self.assertEqual(result.stderr, "")

    def test_discovery_and_final_gc_detect_abandoned_anyio_streams(self):
        result = self.run_discovery(
            """
            import gc
            import anyio

            # Finalize one real stream pair during the discovery import itself.
            send, receive = anyio.create_memory_object_stream(1)
            del send, receive
            gc.collect(2)

            # Leave another pair in a cycle for the runner's final collection.
            abandoned = [*anyio.create_memory_object_stream(1)]
            abandoned.append(abandoned)
            del abandoned
            """
        )
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(
            "pass=1 run=0 skipped=0 failures=0 errors=0 warnings=4", result.stdout
        )
        self.assertEqual(result.stdout.count("ResourceWarning:"), 4)
        self.assertIn("Unclosed <MemoryObjectSendStream", result.stdout)
        self.assertIn("Unclosed <MemoryObjectReceiveStream", result.stdout)
        self.assertIn("pass=2", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_discovery_deprecation_is_not_filtered_out(self):
        result = self.run_discovery(
            """
            import warnings
            warnings.warn("discovery deprecation probe", DeprecationWarning)
            """
        )
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("DeprecationWarning: discovery deprecation probe", result.stdout)
        self.assertIn("warnings=1 unraisables=0", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_discovery_unraisable_fails_the_runner(self):
        result = self.run_discovery(
            """
            class Abandoned:
                def __del__(self):
                    raise ValueError("discovery finalizer probe")
            abandoned = Abandoned()
            del abandoned
            """
        )
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("unraisables=1", result.stdout)
        self.assertIn(
            "unraisable: ValueError: discovery finalizer probe", result.stdout
        )
        self.assertEqual(result.stderr, "")
