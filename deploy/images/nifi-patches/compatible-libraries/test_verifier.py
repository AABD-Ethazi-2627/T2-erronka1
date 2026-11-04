"""Negative integrity tests. Use the same pinned cache; never mutate its inputs."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE=Path(__file__).resolve().parent
CACHE=Path(os.environ['LIBRARY_CACHE'])
REPORTS=Path(os.environ['LIBRARY_REPORTS'])
OBJECTS=Path(os.environ['LIBRARY_OBJECTS'])
class IntegrityTests(unittest.TestCase):
    def invoke(self,cache,reports=REPORTS):
        return subprocess.run([sys.executable,'-O',str(HERE/'verify.py'),'--cache',str(cache),'--reports',str(reports),'--objects',str(OBJECTS),'--offline'],capture_output=True,text=True,timeout=20)
    def test_missing_offline_input_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=CACHE) as d:
            p=self.invoke(d)
            self.assertNotEqual(p.returncode,0);self.assertIn('missing pinned input',p.stderr)
            self.assertFalse(list(Path(d).rglob('replacement-plan.json')))
    def test_changed_bytes_are_rejected_even_with_python_optimization(self):
        with tempfile.TemporaryDirectory(dir=CACHE) as d:
            (Path(d)/'guava-33.4.8-jre.jar').write_bytes(b'wrong artifact')
            p=self.invoke(d)
            self.assertNotEqual(p.returncode,0);self.assertIn('input integrity',p.stderr)
            self.assertFalse(list(Path(d).rglob('replacement-plan.json')))
    def test_symlink_input_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=CACHE) as d:
            (Path(d)/'guava-33.4.8-jre.jar').symlink_to(CACHE/'guava-33.4.8-jre.jar')
            p=self.invoke(d)
            self.assertNotEqual(p.returncode,0);self.assertIn('verification failed',p.stderr)
    def test_changed_ci_report_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=CACHE) as d:
            (Path(d)/'image-scan.json').write_text('{}')
            p=self.invoke(CACHE,Path(d))
            self.assertNotEqual(p.returncode,0);self.assertIn('wrong CI report',p.stderr)
if __name__=='__main__':unittest.main()
