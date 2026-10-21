"""Run the unittest suite twice, catching escaped warnings and unraisables."""

import gc
import io
import sys
import unittest
import warnings
from pathlib import Path


def main():
    sys.path.insert(0, str(Path.cwd()))
    previous_hook = sys.unraisablehook
    escaped = []

    def record_unraisable(info):
        escaped.append(f"{info.exc_type.__name__}: {info.exc_value}")

    try:
        sys.unraisablehook = record_unraisable
        for pass_number in (1, 2):
            suite = unittest.defaultTestLoader.discover("tests")
            output = io.StringIO()
            with warnings.catch_warnings(record=True) as observed:
                warnings.simplefilter("always")
                result = unittest.TextTestRunner(stream=output, verbosity=1).run(suite)
                gc.collect(2)
            print(
                f"pass={pass_number} run={result.testsRun} "
                f"skipped={len(result.skipped)} failures={len(result.failures)} "
                f"errors={len(result.errors)} warnings={len(observed)} "
                f"unraisables={len(escaped)}"
            )
            for warning in observed:
                print(f"warning: {warning.category.__name__}: {warning.message}")
            for exception in escaped:
                print(f"unraisable: {exception}")
            if not result.wasSuccessful() or observed or escaped:
                print(output.getvalue())
                return 1
        return 0
    finally:
        sys.unraisablehook = previous_hook


if __name__ == "__main__":
    raise SystemExit(main())
