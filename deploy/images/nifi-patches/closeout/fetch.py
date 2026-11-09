"""Fetch immutable official inputs; every payload is SHA256 checked before use."""
import argparse
import concurrent.futures
import hashlib
import json
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent


def acquire(cache, rows):
    def fetch(row):
        target = cache / row['destination']
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            data = target.read_bytes()
        else:
            with urllib.request.urlopen(row['url'], timeout=90) as response:
                data = response.read(128 * 1024 * 1024 + 1)
        if len(data) > 128 * 1024 * 1024 or hashlib.sha256(data).hexdigest() != row['sha256']:
            raise ValueError('immutable official input mismatch: ' + row['url'])
        if not target.exists():
            target.write_bytes(data)
        return {**row, 'file': str(target)}

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        return list(pool.map(fetch, rows))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--aws-only', action='store_true')
    args = parser.parse_args()
    if args.aws_only:
        rows = json.loads((HERE / 'aws-inputs.json').read_text())
    else:
        specs = {
            'libraries': ['compatible-libraries/pins.json', 'compatible-libraries/rabbit-pins.json'],
            'hadoop': ['hadoop-snappy/pins.json'], 'hazelcast': ['hazelcast-jackson/pins.json'],
            'parquet': ['parquet-jackson/pins.json'],
            'jackson': ['jackson/pins.json', 'jackson/support-lock.json'],
            'otel': ['otel-qualification/aligned-pins.json', 'otel-qualification/public-pins.json'],
        }
        rows = []
        for family, files in specs.items():
            for filename in files:
                value = json.loads((HERE.parent / filename).read_text())
                if isinstance(value, dict):
                    value = value.get('files', value.get('artifacts', []))
                for row in value:
                    if (isinstance(row, dict) and all(k in row for k in ['file', 'url', 'sha256'])
                            and row['file'].endswith(('.jar', '.pom', '.java', '.patch'))):
                        rows.append({**row, 'destination': 'components/' + family + '/' + row['file']})
        for row in json.loads((HERE / 'additional-pins.json').read_text()):
            name = row['file']
            folder = 'snappy-official-1/' if name.startswith('snappy-') else (
                '' if name.startswith(('hadoop-shaded-', 'iceberg-build.')) else 'wire6-closure-jars/')
            rows.append({**row, 'destination': folder + name})
    acquired = acquire(args.cache, rows)
    output = args.cache / ('aws-downloads.json' if args.aws_only else 'components/downloads.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(acquired, indent=2) + '\n')


if __name__ == '__main__':
    main()
