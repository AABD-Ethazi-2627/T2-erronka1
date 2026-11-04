import copy
import hashlib
import importlib.util
import io
import json
import struct
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/patch_nested_jars.py'

def jar(entries):
    b = io.BytesIO()
    with zipfile.ZipFile(b, 'w', zipfile.ZIP_DEFLATED) as z:
        z.comment = b'archive comment'
        for name, data in entries:
            i = zipfile.ZipInfo(name, (2020, 2, 3, 4, 5, 6))
            i.comment = b'entry comment'
            i.external_attr = 0o100644 << 16
            z.writestr(i, data)
    return b.getvalue()

def sha(b):
    return hashlib.sha256(b).hexdigest()

class PatcherTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.exists(), 'patcher implementation missing')
        spec = importlib.util.spec_from_file_location('patcher', SCRIPT)
        self.p = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.p)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.src = self.root / 'src'
        self.src.mkdir()
        self.old = jar([('old.class', b'old')])
        self.new = jar([('META-INF/X.SF', b'signature'), ('native.so', b'new')])
        self.repl = self.root / 'replacement.jar'
        self.repl.write_bytes(self.new)
        nested = jar([('a.jar', self.old), ('b.jar', self.old), ('keep', b'unchanged')])
        self.outer = jar([('inner.nar', nested), ('keep', b'outer')])
        for name in ('one.nar', 'two.nar'):
            (self.src / name).write_bytes(self.outer)

    def inventory(self, **kw):
        return self.p.inventory(self.src, **kw)

    def plan(self):
        inv = self.inventory()
        return {'schema': 1, 'inventory_sha256': self.p.inventory_hash(inv), 'targets': [
            {'outer': r['outer'], 'members': r['members'], 'chain_sha256': r['chain_sha256'],
             'replacement': str(self.repl), 'replacement_sha256': sha(self.new),
             'status': 'approved-exact-occurrence', 'expected_occurrences': 4}
            for r in inv if r['sha256'] == sha(self.old)]}

    def test_occurrences_and_atomic_sibling_replacement(self):
        inv = self.inventory()
        self.assertEqual(sum(r['sha256'] == sha(self.old) for r in inv), 4)
        plan = self.plan()
        out = self.root / 'out'
        self.p.patch(self.src, out, plan)
        self.assertFalse(out.exists())
        self.p.patch(self.src, out, plan, apply=True)
        for name in ('one.nar', 'two.nar'):
            self.assertEqual((self.src / name).read_bytes(), self.outer)
            with zipfile.ZipFile(out / name) as z:
                self.assertEqual(z.read('keep'), b'outer')
                self.assertEqual(z.comment, b'archive comment')
                with zipfile.ZipFile(io.BytesIO(z.read('inner.nar'))) as n:
                    for leaf in ('a.jar', 'b.jar'):
                        self.assertEqual(n.read(leaf), self.new)
                    self.assertEqual(n.read('keep'), b'unchanged')
                    self.assertEqual(n.getinfo('keep').comment, b'entry comment')
                    self.assertEqual(n.getinfo('keep').date_time, (2020, 2, 3, 4, 5, 6))

    def test_plan_failures_leave_no_output(self):
        for mutation in ('hash', 'count', 'blocked', 'unknown', 'missing', 'duplicate'):
            with self.subTest(mutation=mutation):
                plan = self.plan()
                t = plan['targets'][0]
                if mutation == 'hash': t['chain_sha256'][0] = '0' * 64
                if mutation == 'count': t['expected_occurrences'] = 3
                if mutation == 'blocked': t['status'] = 'blocked'
                if mutation == 'unknown': t['surprise'] = True
                if mutation == 'missing': plan['targets'].pop()
                if mutation == 'duplicate': plan['targets'].append(copy.deepcopy(t))
                out = self.root / 'out'
                with self.assertRaises(ValueError): self.p.patch(self.src, out, plan, apply=True)
                self.assertFalse(out.exists())

    def test_unsafe_archives(self):
        for entries in ([('../x', b'x')], [('/x', b'x')], [('x', b'1'), ('x', b'2')], [('x/../y', b'x')]):
            with self.subTest(entries=entries):
                (self.src / 'bad.jar').write_bytes(jar(entries))
                with self.assertRaises(ValueError): self.inventory()
        (self.src / 'bad.jar').write_bytes(b'broken')
        with self.assertRaises(ValueError): self.inventory()

    def test_budgets(self):
        for kw in ({'max_depth': 0}, {'max_entries': 1}, {'max_bytes': 10}, {'max_archive': 10}):
            with self.assertRaises(ValueError): self.inventory(**kw)

    def test_legacy_unset_mode_only_accepts_empty_stored_directory(self):
        info = zipfile.ZipInfo('META-INF/maven/')
        info.create_system = 3
        info.external_attr = 0xffff0010
        payload = io.BytesIO()
        with zipfile.ZipFile(payload, 'w') as z:
            z.writestr(info, b'')
            z.writestr('keep', b'opaque')
        (self.src / 'legacy.jar').write_bytes(payload.getvalue())
        self.assertTrue(self.inventory())
        for mutation in ('nonempty', 'not-directory', 'compressed', 'different-mode'):
            with self.subTest(mutation=mutation):
                changed = copy.copy(info)
                content = b''
                if mutation == 'nonempty': content = b'not a directory'
                if mutation == 'not-directory': changed.filename = 'META-INF/maven'
                if mutation == 'compressed': changed.compress_type = zipfile.ZIP_DEFLATED
                if mutation == 'different-mode': changed.external_attr = 0xfffe0010
                with zipfile.ZipFile(self.src / 'legacy.jar', 'w') as z:
                    z.writestr(changed, content)
                with self.assertRaisesRegex(ValueError, 'special file/symlink'):
                    self.inventory()

    def test_signed_enclosing_and_symlink_and_overlap(self):
        (self.src / 'signed.nar').write_bytes(jar([('META-INF/SIG-X', b'sig'), ('x.jar', self.old)]))
        plan = self.plan()
        # Build an otherwise valid plan for all old-hash occurrences.
        for t in plan['targets']: t['expected_occurrences'] = 5
        with self.assertRaises(ValueError): self.p.patch(self.src, self.root / 'out', plan, apply=True)
        (self.src / 'signed.nar').unlink()
        plan = self.plan()
        with self.assertRaises(ValueError): self.p.patch(self.src, self.src / 'out', plan, apply=True)
        (self.src / 'link.jar').symlink_to(self.repl)
        with self.assertRaises(ValueError): self.inventory()

    def test_rollback_on_write_failure(self):
        from unittest.mock import patch
        plan = self.plan()
        with patch.object(self.p, 'rewrite', side_effect=OSError('disk full')), self.assertRaises(OSError):
            self.p.patch(self.src, self.root / 'out', plan, apply=True)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ['replacement.jar', 'src'])

    def test_loose_jar_maven_and_nar_identity(self):
        payload = jar([('META-INF/MANIFEST.MF', b'Nar-Id: demo\r\nNar-Dependency-Id: parent\r\n'),
                       ('META-INF/maven/g/a/pom.properties', b'groupId=g\nartifactId=a\nversion=1'),
                       ('other/package/X.class', b'opaque')])
        (self.src / 'loose.jar').write_bytes(payload)
        row = next(r for r in self.inventory() if r['outer'] == 'loose.jar')
        self.assertEqual(row['members'], [])
        self.assertEqual(row['manifest']['Nar-Dependency-Id'], 'parent')
        self.assertEqual(row['class_packages'], ['other/package'])
        self.assertIn('artifactId=a', row['maven'][0]['properties'])

    def test_replacement_drift_existing_output_and_source_drift(self):
        plan = self.plan()
        out = self.root / 'out'
        self.repl.write_bytes(self.old)
        with self.assertRaisesRegex(ValueError, 'replacement hash'): self.p.patch(self.src, out, plan, apply=True)
        self.repl.write_bytes(self.new)
        out.mkdir()
        (out / 'keep').write_text('keep')
        with self.assertRaises(ValueError): self.p.patch(self.src, out, plan, apply=True)
        self.assertEqual((out / 'keep').read_text(), 'keep')
        (out / 'keep').unlink()
        out.rmdir()
        (self.src / 'one.nar').write_bytes(jar([('different', b'drift')]))
        with self.assertRaisesRegex(ValueError, 'inventory hash'): self.p.patch(self.src, out, plan, apply=True)
        self.assertFalse(out.exists())

    def test_zip_symlink_encryption_and_crc_corruption(self):
        path = self.src / 'bad.jar'
        b = io.BytesIO()
        with zipfile.ZipFile(b, 'w') as z:
            i = zipfile.ZipInfo('link')
            i.create_system = 3
            i.external_attr = 0o120777 << 16
            z.writestr(i, 'target')
        path.write_bytes(b.getvalue())
        with self.assertRaises(ValueError): self.inventory()
        import struct
        raw = bytearray(jar([('file', b'unique-payload')]))
        local, central = raw.index(b'PK\x03\x04'), raw.index(b'PK\x01\x02')
        struct.pack_into('<H', raw, local + 6, 1)
        struct.pack_into('<H', raw, central + 8, 1)
        path.write_bytes(raw)
        with self.assertRaises(ValueError): self.inventory()
        path.write_bytes(jar([('file', b'unique-payload')]).replace(b'unique-payload', b'corruptpayload'))
        with self.assertRaises(ValueError): self.inventory()

    def test_signed_manifest_and_ancestor_overlap(self):
        (self.src / 'signed.jar').write_bytes(jar([
            ('META-INF/MANIFEST.MF', b'Manifest-Version: 1.0\n\nName: a.jar\nSHA-256-Digest: abc\n'),
            ('a.jar', self.old)]))
        plan = self.plan()
        for t in plan['targets']: t['expected_occurrences'] = 5
        with self.assertRaisesRegex(ValueError, 'signed enclosing'): self.p.patch(self.src, self.root / 'out', plan)

    def test_cli_default_and_duplicate_json(self):
        import subprocess
        planfile = self.root / 'plan.json'
        planfile.write_text(json.dumps(self.plan()))
        out = self.root / 'out'
        args = [sys.executable, str(SCRIPT), str(self.src), '--plan', str(planfile), '--output', str(out)]
        r = subprocess.run(args, capture_output=True, check=False, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)['mode'], 'dry-run')
        self.assertFalse(out.exists())
        planfile.write_text('{"schema":1,"schema":1}')
        r = subprocess.run(args, capture_output=True, check=False, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('duplicate JSON key', r.stderr)

    def test_noncanonical_trailing_slash_and_aliased_overlap(self):
        (self.src / 'bad.jar').write_bytes(jar([('directory//', b'')]))
        with self.assertRaises(ValueError): self.inventory()
        (self.src / 'bad.jar').unlink()
        plan = self.plan()
        alias = self.src / '..' / 'src'
        with self.assertRaisesRegex(ValueError, 'overlapping'):
            self.p.patch(alias, self.src / 'out', plan, apply=True)

    def test_replacement_symlink_and_unknown_zip_mode(self):
        plan = self.plan()
        link = self.root / 'link.jar'
        link.symlink_to(self.repl)
        plan['targets'][0]['replacement'] = str(link)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            self.p.patch(self.src, self.root / 'out', plan, apply=True)
        b = io.BytesIO()
        with zipfile.ZipFile(b, 'w') as z:
            i = zipfile.ZipInfo('META-INF/maven/')
            i.create_system = 3
            i.external_attr = 0xfffe0010
            z.writestr(i, b'')
        (self.src / 'bad.jar').write_bytes(b.getvalue())
        with self.assertRaisesRegex(ValueError, 'special file'):
            self.inventory()

    def test_loose_stock_replacement_is_byte_identical(self):
        source = self.root / 'loose'
        source.mkdir()
        (source / 'old.jar').write_bytes(self.old)
        inv = self.p.inventory(source)
        plan = {'schema': 1, 'inventory_sha256': self.p.inventory_hash(inv), 'targets': [{
            'outer': 'old.jar', 'members': [], 'chain_sha256': [sha(self.old)],
            'replacement': str(self.repl), 'replacement_sha256': sha(self.new),
            'status': 'approved-exact-occurrence', 'expected_occurrences': 1}]}
        self.p.patch(source, self.root / 'out', plan, apply=True)
        self.assertEqual((self.root / 'out/old.jar').read_bytes(), self.new)
        self.assertEqual((source / 'old.jar').read_bytes(), self.old)

    def test_faulty_writer_cannot_drop_or_change_unselected_siblings(self):
        from unittest.mock import patch
        original=self.p.rewrite
        for mutation in ('drop','change'):
            with self.subTest(mutation=mutation):
                def faulty(path,output,targets,depth=0,mutation=mutation):
                    original(path,output,targets,depth)
                    if depth==0:
                        with zipfile.ZipFile(output) as z:
                            entries=[(i.filename,z.read(i)) for i in z.infolist()]
                        entries=[(name,b'changed' if name=='keep' and mutation=='change' else data)
                                 for name,data in entries if name!='keep' or mutation!='drop']
                        Path(output).write_bytes(jar(entries))
                with patch.object(self.p,'rewrite',side_effect=faulty), self.assertRaisesRegex(ValueError,'post-write sibling'):
                    self.p.patch(self.src,self.root/'out',self.plan(),apply=True)
                self.assertFalse((self.root/'out').exists())

    def test_zero_external_attributes_survive_rewrite(self):
        for path in self.src.iterdir():
            raw=bytearray(path.read_bytes())
            with zipfile.ZipFile(path) as z:offset=z.start_dir
            while raw[offset:offset+4]==b'PK\x01\x02':
                length=struct.unpack_from('<H',raw,offset+28)[0]
                extra,comment=struct.unpack_from('<HH',raw,offset+30)
                if raw[offset+46:offset+46+length]==b'keep':
                    struct.pack_into('<I',raw,offset+38,0)
                offset+=46+length+extra+comment
            path.write_bytes(raw)
        self.p.patch(self.src,self.root/'out',self.plan(),apply=True)
        for name in ('one.nar','two.nar'):
            with zipfile.ZipFile(self.root/'out'/name) as z:
                self.assertEqual(z.getinfo('keep').external_attr,0)

    def test_blocked_ancestors_replacements_and_surviving_old_archive_fail(self):
        from unittest.mock import patch
        for blocked in (sha(self.outer),sha(self.new)):
            with self.subTest(blocked=blocked), patch.object(self.p,'BLOCKED_INPUTS',{blocked}), self.assertRaisesRegex(ValueError,'blocked'):
                self.p.patch(self.src,self.root/'out',self.plan(),apply=True)
        for content,message in ((self.old,'no-op'),(jar([('hidden.jar',self.old)]),'selected old archive')):
            with self.subTest(message=message):
                self.repl.write_bytes(content)
                plan=self.plan()
                for t in plan['targets']:t['replacement_sha256']=sha(content)
                with self.assertRaisesRegex(ValueError,message):
                    self.p.patch(self.src,self.root/'out',plan,apply=True)
                self.assertFalse((self.root/'out').exists())

    def test_complete_ancestor_and_descendant_selections_are_rejected(self):
        plan=self.plan()
        for row in self.inventory():
            if not row['members']:
                plan['targets'].append({'outer':row['outer'],'members':[],
                    'chain_sha256':row['chain_sha256'],'replacement':str(self.repl),
                    'replacement_sha256':sha(self.new),'status':'approved-exact-occurrence',
                    'expected_occurrences':2})
        with self.assertRaisesRegex(ValueError,'overlapping ancestor/leaf'):
            self.p.patch(self.src,self.root/'out',plan,apply=True)

    def test_publication_race_preserves_even_an_empty_existing_directory(self):
        import ctypes
        from unittest.mock import patch
        real=ctypes.CDLL(None,use_errno=True)
        out=self.root/'out';identity=[]
        class Race:
            def renameat2(self,*args):
                out.mkdir();identity.append(out.stat().st_ino)
                return real.renameat2(*args)
        with patch('ctypes.CDLL',return_value=Race()), self.assertRaises(OSError):
            self.p.patch(self.src,out,self.plan(),apply=True)
        self.assertEqual(out.stat().st_ino,identity[0])
        self.assertEqual(list(out.iterdir()),[])

    def test_preamble_and_unflagged_nonascii_names_are_refused(self):
        bad=self.src/'bad.jar'
        bad.write_bytes(b'#!/bin/sh\n'+jar([('payload',b'opaque')]))
        with self.assertRaisesRegex(ValueError,'preamble'):self.inventory()
        raw=bytearray(jar([('é',b'opaque')]))
        struct.pack_into('<H',raw,raw.index(b'PK\x03\x04')+6,0)
        struct.pack_into('<H',raw,raw.index(b'PK\x01\x02')+8,0)
        bad.write_bytes(raw)
        with self.assertRaisesRegex(ValueError,'non-ASCII'):self.inventory()

    def test_directory_payload_and_local_header_disagreement_are_refused(self):
        bad=self.src/'bad.jar'
        bad.write_bytes(jar([('evil.jar/',self.old)]))
        with self.assertRaisesRegex(ValueError,'directory has ZIP payload'):self.inventory()
        raw=bytearray(jar([('evil.jar/',self.old)]))
        with zipfile.ZipFile(io.BytesIO(raw)) as z:central=z.start_dir
        for offset in (16,20,24):struct.pack_into('<I',raw,central+offset,0)
        bad.write_bytes(raw)
        with self.assertRaisesRegex(ValueError,'local/central ZIP'):self.inventory()
        raw=bytearray(jar([('normal',b'opaque')]))
        struct.pack_into('<I',raw,raw.index(b'PK\x03\x04')+22,0)
        bad.write_bytes(raw)
        with self.assertRaisesRegex(ValueError,'local/central ZIP'):self.inventory()

    def test_empty_deflated_directory_remains_valid(self):
        with zipfile.ZipFile(self.src/'directory.jar','w',zipfile.ZIP_DEFLATED) as z:
            z.writestr('empty/',b'')
        self.assertTrue(self.inventory())

if __name__ == '__main__': unittest.main()
