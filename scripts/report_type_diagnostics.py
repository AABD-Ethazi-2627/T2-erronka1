import json
from pathlib import Path

import pandas as pd

from scripts.experiment_rf import evaluate

x = pd.read_csv("data/ai4i2020_train.csv")
v = pd.read_csv("outputs/cg08/validation.csv")
v["machine_type"] = x.loc[v.source_row_index, "machine_type"].to_numpy()
t = json.load(open("outputs/cg08/report.json"))["validation_tuning_metrics"][
    "threshold"
]
r = {}
for kind, g in v.groupby("machine_type"):
    r[kind] = {
        "rows": len(g),
        "positives": int(g.label.sum()),
        "metrics": evaluate(g.label, g.rf_score, t),
    }
Path("docs/evidence/CG24_type_diagnostics.json").write_text(
    json.dumps(r, indent=2) + "\n"
)
