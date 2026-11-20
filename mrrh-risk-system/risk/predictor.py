"""Runs the trained model with NumPy only (no scikit-learn or SciPy at runtime).

ml/train.py trains with scikit-learn and exports the chosen model (logistic regression or random
forest) to plain arrays in risk/artifacts/model.npz. That keeps the Vercel serverless bundle small.
train.py also checks that this code reproduces scikit-learn's probabilities. Inputs are never logged.
"""
import json
from functools import lru_cache
from pathlib import Path

import numpy as np

from .features import CLASSES, FEATURE_ORDER

ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts"


class ModelUnavailable(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _bundle():
    npz, meta = ARTIFACT_DIR / "model.npz", ARTIFACT_DIR / "model_meta.json"
    if not npz.exists() or not meta.exists():
        raise ModelUnavailable("Model files not found. Run `python ml/train.py` first.")
    info = json.loads(meta.read_text())
    if info["feature_order"] != FEATURE_ORDER:
        raise ModelUnavailable("Model features do not match risk/features.py. Retrain the model.")
    arrays = {k: v for k, v in np.load(npz, allow_pickle=False).items()}
    arrays["kind"] = str(arrays["kind"])
    arrays["classes"] = [str(c) for c in arrays["classes"]]
    return {"arrays": arrays, "version": info["version"], "name": info["model"]}


def model_version():
    return _bundle()["version"]


@lru_cache(maxsize=1)
def metrics():
    path = ARTIFACT_DIR / "metrics.json"
    return json.loads(path.read_text()) if path.exists() else None


def _logreg(a, x):
    z = ((x - a["mean"]) / a["scale"]) @ a["coef"].T + a["intercept"]
    z = z - z.max()
    e = np.exp(z)
    return e / e.sum()


def _forest(a, x):
    x32 = x.astype(np.float32)  # scikit-learn compares float32 feature values with the thresholds
    left, right, feat, thr, val = a["left"], a["right"], a["feature"], a["threshold"], a["value"]
    total = np.zeros(val.shape[1])
    for root in a["roots"]:
        node = int(root)
        while left[node] != -1:
            node = int(left[node]) if x32[feat[node]] <= thr[node] else int(right[node])
        total += val[node]
    return total / len(a["roots"])


def predict(values):
    """values: dict keyed by FEATURE_ORDER. Returns (category, {class: probability}, model_version)."""
    b = _bundle()
    a = b["arrays"]
    x = np.array([float(values[f]) for f in FEATURE_ORDER], dtype=np.float64)
    proba = _logreg(a, x) if a["kind"] == "logreg" else _forest(a, x)
    by_class = dict(zip(a["classes"], map(float, proba)))
    ordered = {c: by_class.get(c, 0.0) for c in CLASSES}
    return max(ordered, key=ordered.get), ordered, b["version"]
