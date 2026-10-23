"""Export held-row explanations of prefixed interpretable models, without fit."""

import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from scoring.scope import INPUT_FEATURES
from scripts.ml_study import completed_units, read_json, source_train, write_json

UNITS = {
    "air_temp_K": "K",
    "process_temp_K": "K",
    "rpm": "rpm",
    "torque_Nm": "Nm",
    "tool_wear_min": "min",
    "temp_diff": "K",
    "power_W": "W (ideal mechanical power)",
    "wear_torque": "min*Nm (proxy, not measured physical wear)",
}


def feature_description(model, index, value):
    names = model.prep_.get_feature_names_out().tolist()
    name = names[index].split("__", 1)[1]
    scale = model.prep_.named_transformers_["numeric"].named_steps["scale"]
    if index < len(scale.mean_):
        return {
            "name": name,
            "value": float(value * scale.scale_[index] + scale.mean_[index]),
            "unit": UNITS[name],
        }
    return {"name": name, "value": float(value), "unit": "one-hot indicator"}


def explain(root, summary_path, destination):
    summary = read_json(summary_path)
    train, _ = source_train()
    records = completed_units(root)
    result = {
        "scope": "outer0 held rows; fitted solely on outer0 train",
        "manifest_sha256": summary["manifest_sha256"],
        "models": {},
    }
    for name in ("cart_depth5", "ebm_0", "ebm_3", "gam_3", "gam_5"):
        task, path = next(
            (t, p)
            for t, p in records
            if t["model"] == name and t["phase"] == "outer" and t["fold"] == 0
        )
        model = joblib.load(path / "model.joblib")
        rows = pd.read_csv(
            summary_path.parent / (name + "-outer.csv"), float_precision="round_trip"
        )
        rows = rows.loc[rows.outer == 0]
        selected = {}
        for kind, positive, predicted in [
            ("TP", 1, True),
            ("FN", 1, False),
            ("FP", 0, True),
        ]:
            found = rows.loc[
                (rows.label == positive) & (rows.optimized_prediction == predicted)
            ]
            if len(found):
                selected[kind] = found.iloc[0]
        cases = []
        for kind, row in selected.items():
            index = int(row.source_row_index)
            original = train.loc[[index], INPUT_FEATURES]
            transformed = model.transform(original)
            case = {
                "kind": kind,
                "source_row_index": index,
                "label": int(row.label),
                "score": float(row.score),
                "threshold": float(row.threshold),
                "original_inputs": original.iloc[0].to_dict(),
            }
            if name.startswith("cart"):
                tree = model.model_.tree_
                nodes = model.model_.decision_path(transformed).indices
                decisions = []
                for node in nodes:
                    feature = tree.feature[node]
                    if feature < 0:
                        continue
                    desc = feature_description(model, feature, tree.threshold[node])
                    desc["comparison"] = (
                        "<=" if transformed[0, feature] <= tree.threshold[node] else ">"
                    )
                    desc["observed"] = feature_description(
                        model, feature, transformed[0, feature]
                    )["value"]
                    decisions.append(desc)
                case["decision_path_original_units"] = decisions
            elif name.startswith("ebm"):
                contributions = model.model_.eval_terms(transformed)[0]
                intercept = float(np.asarray(model.model_.intercept_).ravel()[0])
                logit = intercept + float(np.sum(contributions))
                probability = float(1 / (1 + np.exp(-logit)))
                np.testing.assert_allclose(probability, row.score, rtol=0, atol=1e-12)
                names = model.prep_.get_feature_names_out().tolist()
                case.update(
                    intercept_log_odds=intercept,
                    terms=[
                        {
                            "features": [names[i] for i in term],
                            "log_odds_contribution": float(value),
                        }
                        for term, value in zip(
                            model.model_.term_features_, contributions, strict=True
                        )
                    ],
                    sum_matches_score=True,
                )
            else:
                contributions = transformed[0] * model.model_.coef_[0]
                intercept = float(model.model_.intercept_[0])
                probability = float(
                    1 / (1 + np.exp(-intercept - np.sum(contributions)))
                )
                np.testing.assert_allclose(probability, row.score, rtol=0, atol=1e-12)
                case.update(
                    intercept_log_odds=intercept,
                    spline_basis_log_odds=dict(
                        zip(
                            model.prep_.get_feature_names_out().tolist(),
                            contributions.tolist(),
                            strict=True,
                        )
                    ),
                    sum_matches_score=True,
                )
            cases.append(case)
        model_result = {
            "cases": cases,
            "missing_case_types": sorted({"TP", "FN", "FP"} - set(selected)),
        }
        if name.startswith("cart"):
            from sklearn.tree import export_text

            model_result["full_tree_standardized_units"] = export_text(
                model.model_,
                feature_names=model.prep_.get_feature_names_out().tolist(),
                show_weights=True,
            )
        elif name.startswith("ebm"):
            effects = []
            for term, values in zip(
                model.model_.term_features_, model.model_.term_scores_, strict=True
            ):
                if len(term) != 1:
                    continue
                i = term[0]
                cuts = np.asarray(model.model_.bins_[i][0], dtype=float)
                effects.append(
                    {
                        "feature": feature_description(model, i, 0)["name"],
                        "unit": feature_description(model, i, 0)["unit"],
                        "cutpoints_original_units": [
                            feature_description(model, i, c)["value"] for c in cuts
                        ],
                        "bin_log_odds": np.asarray(values).tolist(),
                        "bin_semantics": (
                            "first missing; ordered numeric intervals; last unknown"
                        ),
                    }
                )
            model_result["global_effects"] = effects
        else:
            design = model.design(train.loc[task["fit"], INPUT_FEATURES])
            numeric = [c for c in design if c != "machine_type"]
            names = model.prep_.get_feature_names_out().tolist()
            baseline = design.iloc[[0]].copy()
            baseline[numeric] = design[numeric].median().to_numpy()
            effects = []
            for feature in numeric:
                grid = np.linspace(*np.quantile(design[feature], [0.01, 0.99]), 50)
                probes = pd.concat([baseline] * len(grid), ignore_index=True)
                probes[feature] = grid
                matrix = model.prep_.transform(probes)
                columns = [
                    i
                    for i, n in enumerate(names)
                    if n.startswith("numeric__" + feature + "_sp_")
                ]
                if not columns:
                    raise ValueError("Unknown spline feature naming")
                values = matrix[:, columns] @ model.model_.coef_[0, columns]
                effects.append(
                    {
                        "feature": feature,
                        "unit": UNITS[feature],
                        "grid_original_units": grid.tolist(),
                        "additive_log_odds": values.tolist(),
                    }
                )
            model_result["global_effects"] = effects
            model_result["effect_scope"] = (
                "Intrinsic additive spline terms with other design columns fixed; "
                "not a simulated physical intervention or causal counterfactual"
            )
        result["models"][name] = model_result
    result["limits"] = [
        "Explanations describe model decisions, not industrial causality",
        "Cases are descriptive after fixed evaluation; never used for tuning",
        "No invented dates, physical histories or RUL",
        "Machine type is categorical, never a continuous ordinal",
        (
            "CART full export uses standardized cutpoints; local paths and EBM "
            "effects use original units"
        ),
    ]
    write_json(destination, result)
    print(destination)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    explain(args.root, args.summary, args.destination)
