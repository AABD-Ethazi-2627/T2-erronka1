"""Run the unittest suite twice, catching escaped warnings and unraisables."""

import argparse
import gc
import io
import sys
import unittest
import warnings
from pathlib import Path


def main(start_directory="tests"):
    sys.path.insert(0, str(Path.cwd()))
    previous_hook = sys.unraisablehook
    escaped = []

    def record_unraisable(info):
        escaped.append(f"{info.exc_type.__name__}: {info.exc_value}")

    try:
        sys.unraisablehook = record_unraisable
        unsuccessful = False
        for pass_number in (1, 2):
            escaped.clear()
            output = io.StringIO()
            with warnings.catch_warnings(record=True) as observed:
                warnings.simplefilter("always")
                # Discovery imports test modules and can finalize abandoned resources.
                # Keep both it and the final collection inside the same capture.
                try:
                    suite = unittest.defaultTestLoader.discover(start_directory)
                    result = unittest.TextTestRunner(stream=output, verbosity=1).run(
                        suite
                    )
                finally:
                    gc.collect(2)
            print(
                f"pass={pass_number} run={result.testsRun} "
                f"skipped={len(result.skipped)} failures={len(result.failures)} "
                f"errors={len(result.errors)} warnings={len(observed)} "
                f"unraisables={len(escaped)}"
            )
            for warning in observed:
                print(
                    f"warning: {warning.filename}:{warning.lineno}: "
                    f"{warning.category.__name__}: {warning.message}"
                )
            for exception in escaped:
                print(f"unraisable: {exception}")
            if not result.wasSuccessful() or observed or escaped:
                print(output.getvalue())
                unsuccessful = True
        return int(unsuccessful)
    finally:
        sys.unraisablehook = previous_hook


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("start_directory", nargs="?", default="tests")
    raise SystemExit(main(parser.parse_args().start_directory))
