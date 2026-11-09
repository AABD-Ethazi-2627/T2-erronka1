"""Require the tested AWS production payload and the complete original unit suite."""
import argparse
import hashlib
import json
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('build', type=Path)
    args = parser.parse_args()
    lock = json.loads(Path(__file__).with_name('aws-content-lock.json').read_text())
    for module, row in lock.items():
        with zipfile.ZipFile(args.build / module / 'target' / row['file']) as archive:
            actual = {}
            for name in archive.namelist():
                if name.endswith('/'):
                    continue
                data = archive.read(name)
                if name.endswith('/pom.properties'):
                    data = b'\n'.join(line for line in data.splitlines() if not line.startswith(b'#'))
                actual[name] = hashlib.sha256(data).hexdigest()
        if actual != row['entries']:
            raise ValueError('AWS production content differs from runtime-tested source build: ' + module)
    counts = dict.fromkeys(['tests', 'failures', 'errors', 'skipped'], 0)
    for report in args.build.glob('*/target/surefire-reports/TEST-*.xml'):
        suite = ET.parse(report).getroot()
        for key in counts:
            counts[key] += int(suite.get(key, '0'))
    if counts != {'tests': 1445, 'failures': 0, 'errors': 0, 'skipped': 0}:
        raise ValueError('incomplete original AWS suite: ' + str(counts))
    print(json.dumps({'original_unit_suite': counts, 'production_content_matches': True}))


if __name__ == '__main__':
    main()
