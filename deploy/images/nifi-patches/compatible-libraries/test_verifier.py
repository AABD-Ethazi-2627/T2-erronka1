"""Negative integrity tests. Use the same pinned cache; never mutate its inputs."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE=Path(__file__).resolve().parent
CACHE=Path(os.environ['LIBRARY_CACHE'])
REPORTS=Path(os.environ['LIBRARY_REPORTS'])
OBJECTS=Path(os.environ['LIBRARY_OBJECTS'])
class IntegrityTests(unittest.TestCase):
    def invoke(self,cache,reports=REPORTS,objects=OBJECTS):
        return subprocess.run([sys.executable,'-O',str(HERE/'verify.py'),'--cache',str(cache),'--reports',str(reports),'--objects',str(objects),'--offline'],capture_output=True,check=False,text=True,timeout=20)
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
    def test_empty_object_grouping_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=CACHE) as d:
            objects=Path(d)/'objects.json';objects.write_text('[]')
            p=self.invoke(CACHE,objects=objects)
            self.assertNotEqual(p.returncode,0);self.assertIn('wrong object grouping',p.stderr)
    def test_source_cache_rejected_before_any_output_directory(self):
        with tempfile.TemporaryDirectory(dir=HERE) as d:
            target=Path(d)/'new-output'
            p=self.invoke(target)
            self.assertNotEqual(p.returncode,0);self.assertIn('outside source tree',p.stderr)
            self.assertFalse(target.exists())
if __name__=='__main__':unittest.main()
