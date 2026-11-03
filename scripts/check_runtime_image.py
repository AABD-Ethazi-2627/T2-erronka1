"""Exercise the actual serving closure offline under the API container limits."""

import argparse
import subprocess

PROBE = r"""
import json
import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
import httpx
from scripts.duckdb_output import to_pandas_utc
assert pa.__version__ == "23.0.1"
assert httpx.__version__ == "0.28.1"
assert duckdb.__version__ == "2.0.0"
connection = duckdb.connect(config={
    "memory_limit": "128MB", "threads": "1", "temp_directory": "/tmp/duckdb",
    "autoinstall_known_extensions": "false", "autoload_known_extensions": "false",
})
# JSON must be bundled; LOAD may not download or write an extension.
connection.execute("LOAD json")
pq.write_table(pa.table({"payload_json": ['{"machine":"CNC-004","torque":42.5}']}), '/tmp/probe.parquet')
row = connection.execute("SELECT json_extract_string(payload_json, '$.machine'), CAST(json_extract(payload_json, '$.torque') AS DOUBLE) FROM read_parquet('/tmp/probe.parquet')").fetchall()[0]
assert row == ("CNC-004", 42.5), row
frame = to_pandas_utc(connection.sql("SELECT TIMESTAMPTZ '2026-11-03 00:00:00+00' AS ts"))
assert str(frame.ts.dtype) == "datetime64[us, UTC]", frame.ts.dtype
assert connection.execute("SELECT current_setting('autoinstall_known_extensions')").fetchone() == (False,)
print(json.dumps({"duckdb": duckdb.__version__, "pyarrow": pa.__version__, "httpx": httpx.__version__, "row": row}))
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image")
    args = parser.parse_args()
    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--network=none",
            "--read-only",
            "--memory=512m",
            "--memory-swap=512m",
            "--cpus=1",
            "--pids-limit=64",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--tmpfs=/tmp:rw,noexec,nosuid,size=64m",
            "--env=OPENBLAS_NUM_THREADS=1",
            "--entrypoint=python",
            args.image,
            "-c",
            PROBE,
        ],
        check=True,
        timeout=90,
    )


if __name__ == "__main__":
    main()
