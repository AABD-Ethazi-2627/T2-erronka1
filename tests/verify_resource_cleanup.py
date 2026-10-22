"""Run unittest with deterministic GC and fail on ResourceWarning/unraisables.

Unlike -W error alone, this also detects warnings raised from __del__, which
Python reports to sys.unraisablehook without changing the process exit status.
Run from the repository root: python tests/verify_resource_cleanup.py
"""

import argparse
import gc
import json
import sys
import unittest
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class CollectingResult(unittest.TextTestResult):
    def stopTest(self, test):
        super().stopTest(test)
        gc.collect(2)


def test_ids(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from test_ids(test)
        else:
            yield test.id()


def run(pattern="test_*.py", repeat=2):
    unraisables = []
    original_hook = sys.unraisablehook

    def record_unraisable(info):
        # Keep strings, not traceback/object references that would prevent GC.
        unraisables.append(f"{info.exc_type.__name__}: {info.exc_value}")
        original_hook(info)

    summaries = []
    expected_ids = None
    sys.unraisablehook = record_unraisable
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", ResourceWarning)
            for iteration in range(repeat):
                suite = unittest.TestLoader().discover(str(ROOT / "tests"), pattern)
                ids = list(test_ids(suite))
                if expected_ids is None:
                    expected_ids = ids
                elif ids != expected_ids:
                    raise RuntimeError("Test discovery changed between repetitions")
                result = unittest.TextTestRunner(
                    verbosity=2, resultclass=CollectingResult
                ).run(suite)
                summaries.append(
                    {
                        "iteration": iteration + 1,
                        "discovered": len(ids),
                        "run": result.testsRun,
                        "skipped": len(result.skipped),
                        "success": result.wasSuccessful(),
                    }
                )
                del suite, result
                gc.collect(2)
            gc.collect(2)
    finally:
        sys.unraisablehook = original_hook
    summary = {"runs": summaries, "unraisables": unraisables}
    print(json.dumps(summary, indent=2))
    return bool(unraisables) or any(not item["success"] for item in summaries)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pattern", default="test_*.py")
    parser.add_argument("--repeat", type=int, default=2)
    args = parser.parse_args()
    if args.repeat < 1:
        parser.error("--repeat must be positive")
    sys.exit(run(args.pattern, args.repeat))
