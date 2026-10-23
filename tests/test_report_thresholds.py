import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from scripts.report_thresholds import run


class ThresholdReportTests(unittest.TestCase):
    def test_csv_threshold_equality_and_adjacent_floats(self):
        threshold = 0.19082281465428477
        below = float(np.nextafter(threshold, -np.inf))
        above = float(np.nextafter(threshold, np.inf))
        for cutoff, expected in [
            (below, [[1, 1], [0, 3]]),
            (threshold, [[1, 1], [1, 2]]),
            (above, [[1, 1], [2, 1]]),
        ]:
            with self.subTest(cutoff=cutoff), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                experiment = root / "outputs/cg08"
                experiment.mkdir(parents=True)
                output = root / "docs/evidence"
                output.mkdir(parents=True)
                pd.DataFrame(
                    {
                        "source_row_index": [7762, 7763, 7764, 0, 1],
                        "label": [1, 1, 1, 0, 0],
                        "rf_score": [below, threshold, above, 0.0, 1.0],
                    }
                ).to_csv(experiment / "validation.csv", index=False)
                # Deliberately stale: the plot must use the same recalculated
                # matrix as JSON, rather than copy a prior report's counts.
                (experiment / "report.json").write_text(
                    json.dumps(
                        {
                            "validation_tuning_metrics": {
                                "threshold": cutoff,
                                "confusion_matrix": [[999, 0], [0, 999]],
                            }
                        }
                    )
                )
                previous = Path.cwd()
                try:
                    os.chdir(root)
                    with patch("matplotlib.axes.Axes.imshow") as imshow:
                        result = run()
                    first = (output / "CG10_results.json").read_bytes()
                    run()
                finally:
                    os.chdir(previous)
                policy = result["policies"][str(cutoff)]
                self.assertEqual(policy["confusion_matrix"], expected)
                self.assertEqual(imshow.call_args.args[0], expected)
                self.assertEqual(json.loads(first), result)
                self.assertEqual(first, (output / "CG10_results.json").read_bytes())
                self.assertEqual(len(result["cost_scenarios"]), 27)
                for scenario in result["cost_scenarios"]:
                    matrix = result["policies"][scenario["threshold"]][
                        "confusion_matrix"
                    ]
                    self.assertEqual(
                        scenario["hypothetical_error_cost_eur"],
                        matrix[0][1] * scenario["inspection_eur"]
                        + matrix[1][0] * scenario["downtime_hours"] * 1200,
                    )


if __name__ == "__main__":
    unittest.main()
