"""Isolated #83 research adapters. Never imported by the scoring service."""

import time

import numpy as np
from scipy.linalg import qr
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.covariance import EllipticEnvelope
from sklearn.decomposition import PCA
from sklearn.discriminant_analysis import (
    LinearDiscriminantAnalysis,
    QuadraticDiscriminantAnalysis,
)
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import (
    AdaBoostClassifier,
    GradientBoostingClassifier,
    HistGradientBoostingClassifier,
    IsolationForest,
    RandomForestClassifier,
)
from sklearn.impute import SimpleImputer
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KNeighborsClassifier, LocalOutlierFactor
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, SplineTransformer, StandardScaler
from sklearn.svm import OneClassSVM
from sklearn.tree import DecisionTreeClassifier

from scoring.preparation import SEED, SENSORS, features
from scoring.scope import INPUT_FEATURES


class IndependentColumns(TransformerMixin, BaseEstimator):
    """Remove exact linear redundancy in the training design, preserving its span."""

    def fit(self, X, y=None):
        _, r, order = qr(X, mode="economic", pivoting=True)
        rank = np.linalg.matrix_rank(r)
        self.columns_ = sorted(order[:rank])
        return self

    def transform(self, X):
        return np.asarray(X)[:, self.columns_]


def catalog():
    specs = []

    def add(name, family, **params):
        specs.append(dict(name=name, family=family, params=params, anomaly=False))

    add("rf_reference", "rf")
    add("gb_depth3", "gb")
    add("hist_reference", "hist")
    add("logistic_reference", "logistic")
    add("always0", "dummy", constant=0)
    add("always1", "dummy", constant=1)
    add("rf_no_derived", "rf", physical=False)
    add("gb_no_derived", "gb", physical=False)
    for depth in (3, 5, 8):
        add(f"cart_depth{depth}", "cart", max_depth=depth)
    for smooth in (1e-9, 1e-7):
        add(f"nb_{smooth}", "nb", var_smoothing=smooth)
    add("lda", "lda")
    for reg in (0.1, 0.5):
        add(f"qda_{reg}", "qda", reg_param=reg)
    for k in (5, 15, 35):
        add(f"knn{k}", "knn", n_neighbors=k)
    for depth in (1, 2):
        add(f"ada_depth{depth}", "ada", max_depth=depth)
    for depth in (4, 6):
        for weight in (False, True):
            add(f"cat_d{depth}_{weight}", "cat", depth=depth, balanced=weight)
    for depth in (3, 6):
        for weight in (False, True):
            add(f"xgb_d{depth}_{weight}", "xgb", max_depth=depth, balanced=weight)
    for leaves in (7, 15):
        for weight in (False, True):
            add(f"lgb_{leaves}_{weight}", "lgb", num_leaves=leaves, balanced=weight)
    for interactions in (0, 3):
        add(f"ebm_{interactions}", "ebm", interactions=interactions)
    for knots in (3, 5):
        add(f"gam_{knots}", "gam", n_knots=knots)
    for layers in ((16,), (32,), (32, 16)):
        add("mlp_" + "_".join(map(str, layers)), "mlp", layers=list(layers))
    for name, family, params in [
        ("if_adapted", "if", {}),
        ("lof20_adapted", "lof", {"n_neighbors": 20}),
        ("lof50_adapted", "lof", {"n_neighbors": 50}),
        ("ocsvm_001", "ocsvm", {"nu": 0.01}),
        ("ocsvm_005", "ocsvm", {"nu": 0.05}),
        ("robust_covariance", "cov", {}),
        ("pca2", "pca", {"n_components": 2}),
        ("pca4", "pca", {"n_components": 4}),
        ("ae2", "ae", {"bottleneck": 2}),
        ("ae3", "ae", {"bottleneck": 3}),
    ]:
        specs.append(dict(name=name, family=family, params=params, anomaly=True))
    assert len(specs) == 50
    return specs


CORE = [
    "rf_reference",
    "gb_depth3",
    "always0",
    "always1",
    "cart_depth5",
    "cat_d4_False",
    "xgb_d3_True",
    "lgb_15_False",
    "ebm_0",
    "mlp_32",
]


def estimator(spec, y, device="cpu"):
    f, p = spec["family"], spec["params"]
    if f == "rf":
        return RandomForestClassifier(
            n_estimators=120,
            max_depth=12,
            min_samples_leaf=2,
            random_state=SEED,
            n_jobs=1,
        )
    if f == "gb":
        return GradientBoostingClassifier(
            n_estimators=200,
            learning_rate=0.05,
            max_depth=3,
            min_samples_leaf=5,
            random_state=SEED,
        )
    if f == "hist":
        return HistGradientBoostingClassifier(
            max_iter=250,
            learning_rate=0.07,
            max_leaf_nodes=15,
            l2_regularization=1.0,
            early_stopping=False,
            random_state=SEED,
        )
    if f in {"logistic", "gam"}:
        return LogisticRegression(
            C=1.0,
            class_weight="balanced" if f == "logistic" else None,
            max_iter=3000,
            random_state=SEED,
        )
    if f == "dummy":
        return DummyClassifier(strategy="constant", constant=p["constant"])
    if f == "cart":
        return DecisionTreeClassifier(
            max_depth=p["max_depth"],
            min_samples_leaf=5,
            random_state=SEED,
        )
    if f == "nb":
        return GaussianNB(var_smoothing=p["var_smoothing"])
    if f == "lda":
        return LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto")
    if f == "qda":
        return QuadraticDiscriminantAnalysis(reg_param=p["reg_param"])
    if f == "knn":
        return KNeighborsClassifier(
            n_neighbors=p["n_neighbors"], weights="distance", n_jobs=1
        )
    if f == "ada":
        return AdaBoostClassifier(
            estimator=DecisionTreeClassifier(
                max_depth=p["max_depth"], random_state=SEED
            ),
            n_estimators=100,
            learning_rate=0.5,
            algorithm="SAMME",
            random_state=SEED,
        )
    if f == "cat":
        from catboost import CatBoostClassifier

        return CatBoostClassifier(
            iterations=300,
            depth=p["depth"],
            learning_rate=0.05,
            l2_leaf_reg=3.0,
            auto_class_weights="Balanced" if p["balanced"] else None,
            loss_function="Logloss",
            boosting_type="Plain",
            bootstrap_type="Bernoulli",
            subsample=1.0,
            border_count=128,
            random_strength=0.0,
            score_function="L2",
            leaf_estimation_iterations=10,
            one_hot_max_size=2,
            random_seed=SEED,
            thread_count=1,
            verbose=False,
            allow_writing_files=False,
            task_type="GPU" if device == "cuda" else "CPU",
            **({"devices": "0", "gpu_ram_part": 0.2} if device == "cuda" else {}),
        )
    if f == "xgb":
        from xgboost import XGBClassifier

        ratio = float(np.sum(y == 0) / np.sum(y == 1)) if p["balanced"] else 1.0
        return XGBClassifier(
            n_estimators=300,
            max_depth=p["max_depth"],
            learning_rate=0.05,
            scale_pos_weight=ratio,
            tree_method="hist",
            device=device,
            n_jobs=1,
            random_state=SEED,
            objective="binary:logistic",
            subsample=1.0,
            colsample_bytree=1.0,
            reg_lambda=1.0,
        )
    if f == "lgb":
        from lightgbm import LGBMClassifier

        return LGBMClassifier(
            num_leaves=p["num_leaves"],
            n_estimators=300,
            learning_rate=0.05,
            min_child_samples=20,
            class_weight="balanced" if p["balanced"] else None,
            n_jobs=1,
            random_state=SEED,
            verbosity=-1,
            deterministic=True,
            force_col_wise=True,
        )
    if f == "ebm":
        from interpret.glassbox import ExplainableBoostingClassifier

        return ExplainableBoostingClassifier(
            interactions=p["interactions"],
            max_rounds=1000,
            outer_bags=4,
            inner_bags=0,
            validation_size=0.15,
            early_stopping_rounds=50,
            learning_rate=0.03,
            max_bins=64,
            max_interaction_bins=16,
            n_jobs=1,
            random_state=SEED,
        )
    if f == "mlp":
        return MLPClassifier(
            hidden_layer_sizes=tuple(p["layers"]),
            alpha=1e-3,
            max_iter=200,
            early_stopping=True,
            validation_fraction=0.15,
            n_iter_no_change=20,
            random_state=SEED,
        )
    if f == "if":
        return IsolationForest(n_estimators=200, random_state=SEED, n_jobs=1)
    if f == "lof":
        return LocalOutlierFactor(n_neighbors=p["n_neighbors"], novelty=True, n_jobs=1)
    if f == "ocsvm":
        return OneClassSVM(nu=p["nu"], gamma="scale")
    if f == "cov":
        return EllipticEnvelope(
            contamination=0.01, random_state=SEED, support_fraction=0.8
        )
    if f == "pca":
        return PCA(n_components=p["n_components"], svd_solver="full")
    if f == "ae":
        return MLPRegressor(
            hidden_layer_sizes=(6, p["bottleneck"], 6),
            alpha=1e-3,
            max_iter=1000,
            early_stopping=True,
            validation_fraction=0.15,
            n_iter_no_change=20,
            random_state=SEED,
        )
    raise ValueError(f"Unknown family: {f}")


class StudyModel:
    def __init__(self, spec, device="cpu"):
        self.spec, self.device = spec, device

    def design(self, X):
        # This boundary prevents labels/IDs/raw_record entering any transformer.
        X = X.loc[:, INPUT_FEATURES]
        if self.spec["anomaly"]:
            return X[SENSORS].copy()
        return features(X) if self.spec["params"].get("physical", True) else X.copy()

    def fit(self, X, y):
        begin = time.perf_counter()
        design = self.design(X)
        if self.spec["anomaly"]:
            design = design.loc[np.asarray(y) == 0]
        if self.spec["family"] == "cat":
            self.prep_ = SimpleImputer(strategy="median")
            self.numeric_ = [c for c in design if c != "machine_type"]
            matrix = design.copy()
            matrix[self.numeric_] = self.prep_.fit_transform(design[self.numeric_])
            matrix["machine_type"] = matrix.machine_type.fillna("missing").astype(str)
        elif self.spec["anomaly"]:
            self.prep_ = Pipeline(
                [
                    ("impute", SimpleImputer(strategy="median")),
                    ("scale", StandardScaler()),
                ]
            )
            matrix = self.prep_.fit_transform(design)
        else:
            numeric = [c for c in design if c != "machine_type"]
            steps = [
                ("impute", SimpleImputer(strategy="median")),
                ("scale", StandardScaler()),
            ]
            if self.spec["family"] == "gam":
                steps.append(
                    (
                        "spline",
                        SplineTransformer(
                            n_knots=self.spec["params"]["n_knots"],
                            degree=3,
                            include_bias=False,
                        ),
                    )
                )
            self.prep_ = ColumnTransformer(
                [
                    ("numeric", Pipeline(steps), numeric),
                    (
                        "type",
                        OneHotEncoder(
                            handle_unknown="ignore",
                            sparse_output=False,
                            drop="first"
                            if self.spec["family"] in {"lda", "qda"}
                            else None,
                        ),
                        ["machine_type"],
                    ),
                ]
            )
            matrix = self.prep_.fit_transform(design)
            if self.spec["family"] in {"lda", "qda"}:
                self.rank_ = IndependentColumns().fit(matrix)
                matrix = self.rank_.transform(matrix)
        self.preparation_seconds_ = time.perf_counter() - begin
        self.model_ = estimator(self.spec, np.asarray(y), self.device)
        if self.spec["family"] == "cat":
            self.model_.fit(matrix, y, cat_features=["machine_type"])
        elif self.spec["family"] == "ae":
            self.model_.fit(matrix, matrix)
        elif self.spec["anomaly"]:
            self.model_.fit(matrix)
        else:
            self.model_.fit(matrix, y)
        return self

    def transform(self, X):
        design = self.design(X)
        if self.spec["family"] == "cat":
            design[self.numeric_] = self.prep_.transform(design[self.numeric_])
            design["machine_type"] = design.machine_type.fillna("missing").astype(str)
            return design
        matrix = self.prep_.transform(design)
        return self.rank_.transform(matrix) if hasattr(self, "rank_") else matrix

    def score(self, X):
        matrix = self.transform(X)
        family = self.spec["family"]
        if family == "pca":
            return np.mean(
                (matrix - self.model_.inverse_transform(self.model_.transform(matrix)))
                ** 2,
                axis=1,
            )
        if family == "ae":
            return np.mean((matrix - self.model_.predict(matrix)) ** 2, axis=1)
        if self.spec["anomaly"]:
            return -self.model_.score_samples(matrix)
        if family == "cat":
            return self.model_.predict_proba(matrix, thread_count=1)[:, 1]
        return self.model_.predict_proba(matrix)[:, 1]


class StudyCalibrated:
    """75/25 estimator/calibration split, reconstructed in each training fold."""

    def __init__(self, spec, method):
        self.spec, self.method = spec, method

    def fit(self, X, y):
        from sklearn.calibration import _SigmoidCalibration

        a, b = train_test_split(
            np.arange(len(X)), test_size=0.25, stratify=y, random_state=43
        )
        self.base_ = StudyModel(self.spec).fit(X.iloc[a], np.asarray(y)[a])
        self.preparation_seconds_ = self.base_.preparation_seconds_
        if self.method != "raw75":
            scores = self.base_.score(X.iloc[b])
            self.calibrator_ = (
                _SigmoidCalibration()
                if self.method == "sigmoid"
                else IsotonicRegression(out_of_bounds="clip")
            ).fit(scores, np.asarray(y)[b])
        self.fit_positive_support_ = int(np.sum(np.asarray(y)[a]))
        self.calibration_positive_support_ = int(np.sum(np.asarray(y)[b]))
        return self

    def score(self, X):
        scores = self.base_.score(X)
        return scores if self.method == "raw75" else self.calibrator_.predict(scores)
