"""Train and compare the three candidate models from the proposal (section 3.13-3.14).

Pipeline (matches the proposal):
  * patient-level, temporal partition: patients first seen 2021-2023 -> training,
    2024 -> validation, 2025 -> final test. A woman is never in two partitions.
  * three candidates: multinomial logistic regression, random forest, support vector machine.
  * hyper-parameters tuned by patient-grouped cross-validation INSIDE the training set.
  * the model is selected on VALIDATION macro-F1 only.
  * the TEST set is used once, for the selected model only.
  * reported: macro-F1, class-specific precision/recall/F1, balanced accuracy, confusion
    matrix, one-vs-rest ROC-AUC, multiclass Brier score, patient-level bootstrap CI.

Run from the project root:   python ml/train.py
The data are SYNTHETIC (see ml/generate_synthetic_data.py). The numbers describe the
demo pipeline only and say nothing about performance at MRRH.
"""
import json
import warnings
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (balanced_accuracy_score, confusion_matrix, f1_score,
                             precision_recall_fscore_support, roc_auc_score)
from sklearn.model_selection import GridSearchCV, GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from risk.features import CLASSES, FEATURE_ORDER  # noqa: E402

DATA = ROOT / "ml" / "data" / "synthetic_records.csv"
OUT_DIR = ROOT / "risk" / "artifacts"
SEED = 42
warnings.filterwarnings("ignore", category=FutureWarning)


def load():
    df = pd.read_csv(DATA)
    first = df.groupby("patient_id")["visit_year"].min().rename("first_year")
    df = df.join(first, on="patient_id")
    df["partition"] = np.where(df.first_year <= 2023, "train", np.where(df.first_year == 2024, "validation", "test"))
    return df


def candidates():
    return {
        "Multinomial logistic regression": (
            Pipeline([("scale", StandardScaler()), ("clf", LogisticRegression(max_iter=2000, class_weight="balanced"))]),
            {"clf__C": [0.1, 1.0, 10.0]},
        ),
        "Random forest": (
            Pipeline([("clf", RandomForestClassifier(class_weight="balanced_subsample", random_state=SEED, n_jobs=1))]),
            {"clf__n_estimators": [100, 150], "clf__max_depth": [8, 12], "clf__min_samples_leaf": [3, 8]},
        ),
        "Support vector machine": (
            Pipeline([("scale", StandardScaler()), ("clf", SVC(kernel="rbf", probability=True, class_weight="balanced", random_state=SEED))]),
            {"clf__C": [1.0, 10.0], "clf__gamma": ["scale", 0.02]},
        ),
    }


def metrics(y_true, proba, groups=None):
    idx = proba.argmax(1)
    y_pred = np.array(CLASSES)[idx]
    p, r, f, s = precision_recall_fscore_support(y_true, y_pred, labels=CLASSES, zero_division=0)
    onehot = np.array([[1.0 if y == c else 0.0 for c in CLASSES] for y in y_true])
    aucs = {}
    for i, c in enumerate(CLASSES):
        aucs[c] = float(roc_auc_score(onehot[:, i], proba[:, i])) if 0 < onehot[:, i].sum() < len(onehot) else None
    return {
        "n": int(len(y_true)),
        "macro_f1": float(f1_score(y_true, y_pred, labels=CLASSES, average="macro", zero_division=0)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "accuracy": float((y_pred == np.array(y_true)).mean()),
        "per_class": {c: {"precision": float(p[i]), "recall": float(r[i]), "f1": float(f[i]), "support": int(s[i])} for i, c in enumerate(CLASSES)},
        "high_risk_recall": float(r[CLASSES.index("high")]),
        "confusion_matrix": {"labels": CLASSES, "matrix": confusion_matrix(y_true, y_pred, labels=CLASSES).tolist()},
        "ovr_roc_auc": aucs,
        "brier_multiclass": float(((proba - onehot) ** 2).sum(1).mean()),
    }


def bootstrap_ci(y_true, proba, groups, n=300):
    """Patient-level bootstrap 95% CI for macro-F1."""
    rng = np.random.default_rng(SEED)
    y_true = np.array(y_true)
    pats = np.unique(groups)
    by = {g: np.where(groups == g)[0] for g in pats}
    vals = []
    for _ in range(n):
        pick = rng.choice(pats, size=len(pats), replace=True)
        ix = np.concatenate([by[g] for g in pick])
        yp = np.array(CLASSES)[proba[ix].argmax(1)]
        vals.append(f1_score(y_true[ix], yp, labels=CLASSES, average="macro", zero_division=0))
    return [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]


def export_numpy(model, name):
    """Convert a fitted pipeline to plain arrays so the web app needs only NumPy (no scikit-learn/SciPy).
    Vercel serverless functions have a ~250 MB size limit; scikit-learn + SciPy alone would nearly use it."""
    clf = model.named_steps["clf"]
    classes = [str(c) for c in clf.classes_]
    out = {"classes": np.array(classes)}
    if name == "Multinomial logistic regression":
        sc = model.named_steps["scale"]
        out.update(kind=np.array("logreg"), mean=sc.mean_, scale=sc.scale_, coef=clf.coef_, intercept=clf.intercept_)
    elif name == "Random forest":
        lefts, rights, feats, thrs, vals, roots, off = [], [], [], [], [], [], 0
        for est in clf.estimators_:
            t = est.tree_
            roots.append(off)
            lefts.append(np.where(t.children_left < 0, -1, t.children_left + off))
            rights.append(np.where(t.children_right < 0, -1, t.children_right + off))
            feats.append(t.feature); thrs.append(t.threshold)
            v = t.value[:, 0, :]
            vals.append(v / v.sum(1, keepdims=True))
            off += t.node_count
        out.update(kind=np.array("forest"), left=np.concatenate(lefts), right=np.concatenate(rights),
                   feature=np.concatenate(feats), threshold=np.concatenate(thrs), value=np.concatenate(vals),
                   roots=np.array(roots))
    else:
        raise ValueError("not exportable")
    return out


def main():
    df = load()
    parts = {k: df[df.partition == k] for k in ("train", "validation", "test")}
    for k, d in parts.items():
        print(k, len(d), "encounters,", d.patient_id.nunique(), "patients", d.risk_label.value_counts().to_dict())
    assert not (set(parts["train"].patient_id) & set(parts["validation"].patient_id)), "patient leakage"
    assert not (set(parts["train"].patient_id) & set(parts["test"].patient_id)), "patient leakage"
    assert not (set(parts["validation"].patient_id) & set(parts["test"].patient_id)), "patient leakage"

    Xtr, ytr, gtr = parts["train"][FEATURE_ORDER].to_numpy(float), parts["train"].risk_label.to_numpy(), parts["train"].patient_id.to_numpy()
    Xva, yva = parts["validation"][FEATURE_ORDER].to_numpy(float), parts["validation"].risk_label.to_numpy()
    Xte, yte, gte = parts["test"][FEATURE_ORDER].to_numpy(float), parts["test"].risk_label.to_numpy(), parts["test"].patient_id.to_numpy()

    fitted, comparison = {}, []
    for name, (pipe, grid) in candidates().items():
        gs = GridSearchCV(pipe, grid, scoring="f1_macro", cv=GroupKFold(n_splits=5), n_jobs=1)
        gs.fit(Xtr, ytr, groups=gtr)
        best = gs.best_estimator_
        classes = list(best.classes_)
        proba = best.predict_proba(Xva)[:, [classes.index(c) for c in CLASSES]]
        m = metrics(yva, proba)
        fitted[name] = best
        comparison.append({"model": name, "best_params": {k.split("__")[1]: v for k, v in gs.best_params_.items()},
                           "cv_macro_f1_train": float(gs.best_score_), "validation": m})
        print(f"{name:34s} cv_macro_f1={gs.best_score_:.3f} validation_macro_f1={m['macro_f1']:.3f} high_recall={m['high_risk_recall']:.3f}")

    chosen = max(comparison, key=lambda c: (c["validation"]["macro_f1"], c["validation"]["high_risk_recall"]))
    note = None
    if chosen["model"] == "Support vector machine":
        # An RBF SVM cannot be exported to the NumPy-only runtime, so deploy the best exportable model.
        chosen = max((c for c in comparison if c["model"] != "Support vector machine"),
                     key=lambda c: (c["validation"]["macro_f1"], c["validation"]["high_risk_recall"]))
        note = "The SVM scored highest on validation but is not deployed (cannot run in the NumPy-only serverless runtime); the best exportable model is used."
    model = fitted[chosen["model"]]
    classes = list(model.classes_)
    proba_te = model.predict_proba(Xte)[:, [classes.index(c) for c in CLASSES]]
    test = metrics(yte, proba_te)
    test["macro_f1_ci95_patient_bootstrap"] = bootstrap_ci(yte, proba_te, gte)
    print("SELECTED:", chosen["model"], "| test macro-F1 %.3f" % test["macro_f1"], "CI", test["macro_f1_ci95_patient_bootstrap"])

    version = datetime.now(timezone.utc).strftime("demo-%Y%m%d")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    arrays = export_numpy(model, chosen["model"])
    np.savez_compressed(OUT_DIR / "model.npz", **arrays)
    (OUT_DIR / "model_meta.json").write_text(json.dumps({"version": version, "feature_order": FEATURE_ORDER, "model": chosen["model"]}))
    # parity check: the NumPy runtime must reproduce scikit-learn exactly
    from risk import predictor
    predictor._bundle.cache_clear()
    worst = 0.0
    for row in Xte[:300]:
        _, p, _ = predictor.predict(dict(zip(FEATURE_ORDER, row)))
        ref = model.predict_proba(row.reshape(1, -1))[0]
        ref = dict(zip(classes, ref))
        worst = max(worst, max(abs(p[c] - ref[c]) for c in CLASSES))
    assert worst < 1e-6, f"NumPy runtime differs from scikit-learn by {worst}"
    print("NumPy runtime parity with scikit-learn OK (max difference %.2e)" % worst)
    ref_dir = ROOT / "ml" / "out"; ref_dir.mkdir(exist_ok=True)
    joblib.dump({"pipeline": model, "classes": classes}, ref_dir / "model_sklearn.joblib", compress=3)
    report = {
        "version": version,
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sklearn_version": sklearn.__version__,
        "data": {
            "source": "SYNTHETIC demonstration data (ml/generate_synthetic_data.py). Not MRRH data.",
            "label": "Placeholder scoring rules plus 8% label noise. Not clinical guidance.",
            "split": "patient-level and temporal: first seen 2021-2023 train, 2024 validation, 2025 test",
            "partitions": {k: {"encounters": int(len(d)), "patients": int(d.patient_id.nunique()),
                               "classes": {c: int((d.risk_label == c).sum()) for c in CLASSES}} for k, d in parts.items()},
        },
        "features": FEATURE_ORDER,
        "candidates": comparison,
        "selected_model": chosen["model"],
        "deployment_note": note,
        "selected_on": "validation macro-F1 (ties broken by high-risk recall)",
        "test": test,
        "warning": "These figures describe the demo pipeline on synthetic data only. They are not evidence of performance or clinical validity at MRRH.",
    }
    (OUT_DIR / "metrics.json").write_text(json.dumps(report, indent=2))
    print("saved", OUT_DIR / "model.npz", "and metrics.json")


if __name__ == "__main__":
    main()
