import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from scripts.expose_nested_jars import expose


def archive(**entries):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as zipped:
        for name, content in entries.items():
            zipped.writestr(name, content)
    return output.getvalue()


class NestedJarAuditTests(unittest.TestCase):
    def test_nested_archives_are_visible_without_trusting_entry_paths(self):
        jar = archive(
            **{
                "META-INF/maven/example/library/pom.properties": b"groupId=example\nartifactId=library\nversion=1.0\n"
            }
        )
        nar = archive(**{"../escape.jar": jar, "same.jar": jar})
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            (source / "bundle.nar").write_bytes(nar)
            inventory = expose(source, root / "audit")
            self.assertEqual(len(inventory), 2)
            self.assertEqual(len(list((root / "audit").glob("*.jar"))), 1)
            self.assertFalse((root / "escape.jar").exists())
            self.assertEqual(next((root / "audit").glob("*.jar")).read_bytes(), jar)

    def test_empty_malformed_and_oversized_archives_fail_closed(self):
        for payload in [b"not-a-zip", archive(**{"nested.jar": b"x" * 100})]:
            with (
                self.subTest(payload=payload[:10]),
                tempfile.TemporaryDirectory() as temporary,
            ):
                root = Path(temporary)
                (root / "bundle.nar").write_bytes(payload)
                with (
                    patch("scripts.expose_nested_jars.MAX_ARCHIVE_BYTES", 50),
                    self.assertRaises((ValueError, zipfile.BadZipFile)),
                ):
                    expose(root, root / "audit")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "empty.nar").write_bytes(archive())
            with self.assertRaisesRegex(ValueError, "No nested"):
                expose(root, root / "audit")
