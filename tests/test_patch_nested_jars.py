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
import zlib
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


def layout_zip(*, local_extra=b'', central_extra=b'', tail=b'', descriptor=False,
               zip64=False, false_placeholder=False, descriptor_signature=True):
    name=b'ordinary';payload=b'normal bounded payload'
    encoder=zlib.compressobj(wbits=-15)
    compressed=encoder.compress(payload)+encoder.flush()+tail
    crc=zlib.crc32(payload);flags=8 if descriptor else 0
    size,csize=len(payload),len(compressed)
    if zip64:local_extra=struct.pack('<HHQQ',1,16,size,csize)+local_extra
    local_crc=0 if descriptor else crc
    local_size=0xffffffff if zip64 else (0 if descriptor else size)
    local_compressed=0xffffffff if zip64 else (0 if descriptor else csize)
    if false_placeholder:local_size=2
    header=struct.pack('<4s5H3I2H',b'PK\x03\x04',45 if zip64 else 20,flags,8,0,33,
                       local_crc,local_compressed,local_size,len(name),len(local_extra))
    local=header+name+local_extra+compressed
    if descriptor:
        local+=(b'PK\x07\x08' if descriptor_signature else b'')+struct.pack('<IQQ' if zip64 else '<III',crc,csize,size)
    central=struct.pack('<4s6H3I5H2I',b'PK\x01\x02',3*256+20,45 if zip64 else 20,flags,8,0,33,
                        crc,csize,size,len(name),len(central_extra),0,0,0,0o100644<<16,0)+name+central_extra
    return local+central+struct.pack('<4s4H2IH',b'PK\x05\x06',0,0,1,1,len(central),len(local),0)

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

    def test_eocd_and_deflate_trailing_payloads_are_rejected(self):
        for data in (layout_zip()+b'hidden',layout_zip(tail=b'hidden')):
            with self.subTest(length=len(data)):
                (self.src/'bad.jar').write_bytes(data)
                with self.assertRaisesRegex(ValueError,'EOCD|deflate'):self.inventory()

    def test_local_extra_and_alternative_unicode_paths_are_rejected(self):
        opaque=struct.pack('<HH',0xcafe,6)+b'hidden'
        unicode=struct.pack('<HH',0x7075,13)+b'\x01'+struct.pack('<I',zlib.crc32(b'ordinary'))+b'evil.jar'
        for data in (layout_zip(local_extra=opaque),layout_zip(local_extra=unicode,central_extra=unicode)):
            (self.src/'bad.jar').write_bytes(data)
            with self.assertRaisesRegex(ValueError,'ZIP extra|Unicode ZIP path'):self.inventory()

    def test_typed_extended_timestamps_can_be_inventoried_but_not_dropped_on_rewrite(self):
        left=struct.pack('<HHBII',0x5455,9,3,123,456)
        right=struct.pack('<HHBI',0x5455,5,3,123)
        data=layout_zip(local_extra=left,central_extra=right)
        (self.src/'timestamp.jar').write_bytes(data)
        self.assertTrue(self.inventory())
        with zipfile.ZipFile(io.BytesIO(data)) as z,self.assertRaisesRegex(ValueError,'ZIP extra mismatch'):
            self.p.validate_layout(z,z.infolist(),for_rewrite=True)
        for local,central in ((b'',right),(struct.pack('<HHBI',0x5455,5,1,123),right)):
            (self.src/'timestamp.jar').write_bytes(layout_zip(local_extra=local,central_extra=central))
            self.assertTrue(self.inventory())
        for changed in (left+b'x',struct.pack('<HHBII',0x5455,9,3,999,456)):
            (self.src/'timestamp.jar').write_bytes(layout_zip(local_extra=changed,central_extra=right))
            with self.assertRaises(ValueError):self.inventory()

    def test_descriptor_placeholders_and_both_zip64_size_branches(self):
        for descriptor in (False,True):
            for zip64 in (False,True):
                for signature in (False,True):
                    with self.subTest(descriptor=descriptor,zip64=zip64,signature=signature):
                        (self.src/'descriptor.jar').write_bytes(layout_zip(descriptor=descriptor,zip64=zip64,descriptor_signature=signature))
                        self.assertTrue(self.inventory())
        (self.src/'descriptor.jar').write_bytes(layout_zip(descriptor=True,false_placeholder=True))
        with self.assertRaisesRegex(ValueError,'descriptor placeholder'):self.inventory()

    def test_local_flag_method_name_and_descriptor_signature_cannot_drift(self):
        for mutation in ('flags','method','name','descriptor','gap'):
            with self.subTest(mutation=mutation):
                raw=bytearray(layout_zip(descriptor=True))
                if mutation=='flags':struct.pack_into('<H',raw,6,0)
                elif mutation=='method':struct.pack_into('<H',raw,8,0)
                elif mutation=='name':raw[30]=ord('x')
                elif mutation=='descriptor':raw[raw.index(b'PK\x07\x08')]=0
                elif mutation=='gap':raw.insert(raw.index(b'PK\x01\x02'),0)
                (self.src/'bad.jar').write_bytes(raw)
                with self.assertRaises(ValueError):self.inventory()

    def test_atomic_group_requires_exact_hashes_all_members_and_no_ancestor_shortcut(self):
        from unittest.mock import patch
        inv=[{'outer':'a.nar','members':['h.jar'],'chain_sha256':['outer','old-h'],'sha256':'old-h'},
             {'outer':'a.nar','members':['s.jar'],'chain_sha256':['outer','old-s'],'sha256':'old-s'},
             {'outer':'b.nar','members':['s.jar'],'chain_sha256':['other','old-s'],'sha256':'old-s'}]
        policy={'old-h':{'replacement_sha256':'new-h','count':1},'old-s':{'replacement_sha256':'new-s','count':2}}
        targets=[dict(outer=r['outer'],members=r['members'],chain_sha256=r['chain_sha256'],
                      replacement_sha256=policy[r['sha256']]['replacement_sha256'],expected_occurrences=policy[r['sha256']]['count']) for r in inv]
        with patch.object(self.p,'ATOMIC_HADOOP_SNAPPY',policy):
            self.p.validate_atomic_targets(inv,targets)
            for mutation in ('no-consumer','no-library','wrong-library','wrong-consumer','missing-source','ancestor'):
                changed=copy.deepcopy(targets);rows=copy.deepcopy(inv)
                if mutation=='no-consumer':changed.pop(0)
                elif mutation=='no-library':changed.pop()
                elif mutation=='wrong-library':changed[1]['replacement_sha256']='other'
                elif mutation=='wrong-consumer':changed[0]['replacement_sha256']='other'
                elif mutation=='missing-source':rows.pop()
                else:changed=[dict(changed[0],members=[],chain_sha256=['outer'])]
                with self.subTest(mutation=mutation),self.assertRaisesRegex(ValueError,'atomic Hadoop/Snappy'):
                    self.p.validate_atomic_targets(rows,changed)

    def test_writer_enforces_coupling_before_any_publication(self):
        from unittest.mock import patch
        consumer=jar([('Consumer.class',b'old consumer')])
        fixed=jar([('Consumer.class',b'fixed consumer')])
        (self.src/'consumer.jar').write_bytes(consumer)
        replacement=self.root/'fixed-consumer.jar';replacement.write_bytes(fixed)
        policy={sha(self.old):{'replacement_sha256':sha(self.new),'count':4},
                sha(consumer):{'replacement_sha256':sha(fixed),'count':1}}
        with patch.object(self.p,'ATOMIC_HADOOP_SNAPPY',policy):
            plan=self.plan()
            with self.assertRaisesRegex(ValueError,'atomic Hadoop/Snappy'):
                self.p.patch(self.src,self.root/'out',plan,apply=True)
            self.assertFalse((self.root/'out').exists())
            plan['targets'].append({'outer':'consumer.jar','members':[],
                'chain_sha256':[sha(consumer)],'replacement':str(replacement),
                'replacement_sha256':sha(fixed),'expected_occurrences':1,
                'status':'approved-exact-occurrence'})
            self.p.patch(self.src,self.root/'out',plan,apply=True)
            self.assertEqual((self.root/'out/consumer.jar').read_bytes(),fixed)
            self.assertEqual((self.src/'consumer.jar').read_bytes(),consumer)

if __name__ == '__main__': unittest.main()
