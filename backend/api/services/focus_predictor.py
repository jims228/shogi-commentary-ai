"""着目点予測 (Focus Prediction) MLモデル.

局面の特徴量から、プロがどの要素に言及するかを予測する
マルチラベル分類モデル。

Labels: king_safety, piece_activity, attack_pressure,
        positional, tempo, endgame_technique
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

_LOG = logging.getLogger("uvicorn.error")

try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import accuracy_score, f1_score
    from sklearn.model_selection import KFold
    from sklearn.multiclass import OneVsRestClassifier
    from sklearn.preprocessing import MultiLabelBinarizer
    import joblib

    _HAS_SKLEARN = True
except ImportError:
    _HAS_SKLEARN = False

from backend.api.schemas.annotation import FOCUS_LABELS
from backend.api.services.ml_trainer import _FEATURE_KEYS, _features_to_vector

_DEFAULT_DATA_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "data")
)
_DEFAULT_CORPUS_PATH = os.path.join(
    _DEFAULT_DATA_DIR, "annotated", "annotated_corpus.jsonl"
)
_DEFAULT_MODEL_PATH = os.path.join(
    _DEFAULT_DATA_DIR, "models", "focus_predictor.joblib"
)

_MIN_SAMPLES = 50


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def _load_focus_data(
    data_path: Optional[str] = None,
) -> Dict[str, Any]:
    """annotated_corpus.jsonl からマルチラベル分類用データを構築."""
    src = data_path or _DEFAULT_CORPUS_PATH
    if not os.path.exists(src):
        return {"X": [], "y_labels": [], "n_samples": 0, "error": f"not found: {src}"}

    X: List[List[float]] = []
    y_labels: List[List[str]] = []

    with open(src, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                features = obj.get("features")
                ann = obj.get("annotation", {})
                focus = ann.get("focus", [])
                if not features or not focus:
                    continue
                X.append(_features_to_vector(features))
                y_labels.append(focus)
            except Exception:
                continue

    error = None
    if len(X) < _MIN_SAMPLES:
        error = f"insufficient samples ({len(X)} < {_MIN_SAMPLES})"

    return {
        "X": X,
        "y_labels": y_labels,
        "n_samples": len(X),
        "error": error,
    }


# ---------------------------------------------------------------------------
# Rule-based fallback
# ---------------------------------------------------------------------------
def _rule_based_predict_from_features(features: Dict[str, Any]) -> List[str]:
    """特徴量ベースの簡易ルールで focus を予測 (テキストなし時)."""
    labels: List[str] = []
    ks = features.get("king_safety", 50)
    ap = features.get("attack_pressure", 0)
    pa = features.get("piece_activity", 50)
    phase = features.get("phase", "midgame")

    if ks < 30:
        labels.append("king_safety")
    if ap > 50:
        labels.append("attack_pressure")
    if pa > 70:
        labels.append("piece_activity")
    if phase == "endgame":
        labels.append("endgame_technique")

    return labels if labels else ["positional"]


# ---------------------------------------------------------------------------
# FocusPredictor
# ---------------------------------------------------------------------------
class FocusPredictor:
    """局面特徴量から着目点ラベルを予測するマルチラベル分類器."""

    def __init__(self) -> None:
        self._model: Any = None  # OneVsRestClassifier
        self._binarizer: Any = None  # MultiLabelBinarizer

    @property
    def is_trained(self) -> bool:
        return self._model is not None and self._binarizer is not None

    def train(self, data_path: Optional[str] = None) -> Dict[str, Any]:
        """アノテーション済みデータから訓練.

        Returns
        -------
        dict
            {n_samples, n_labels, label_distribution,
             accuracy, f1_samples, f1_macro}
        """
        if not _HAS_SKLEARN:
            return {"error": "scikit-learn not installed", "n_samples": 0}

        data = _load_focus_data(data_path)
        if data.get("error"):
            return {"error": data["error"], "n_samples": data["n_samples"]}

        X = np.array(data["X"])
        y_labels = data["y_labels"]

        binarizer = MultiLabelBinarizer(classes=list(FOCUS_LABELS))
        Y = binarizer.fit_transform(y_labels)

        clf = OneVsRestClassifier(
            RandomForestClassifier(
                n_estimators=100, max_depth=8, random_state=42
            )
        )
        clf.fit(X, Y)

        self._model = clf
        self._binarizer = binarizer

        # Training metrics
        preds = clf.predict(X)
        acc = float(accuracy_score(Y, preds))
        f1_s = float(f1_score(Y, preds, average="samples", zero_division=0))
        f1_m = float(f1_score(Y, preds, average="macro", zero_division=0))

        # Label distribution
        label_dist = {}
        for lbl in FOCUS_LABELS:
            idx = list(binarizer.classes_).index(lbl)
            label_dist[lbl] = int(Y[:, idx].sum())

        return {
            "n_samples": len(X),
            "n_labels": len(FOCUS_LABELS),
            "label_distribution": label_dist,
            "accuracy": round(acc, 4),
            "f1_samples": round(f1_s, 4),
            "f1_macro": round(f1_m, 4),
        }

    def predict(self, features: Dict[str, Any]) -> List[str]:
        """局面特徴量からfocusラベルを予測.

        未訓練時はルールベースにフォールバック。
        """
        if not self.is_trained or not _HAS_SKLEARN:
            return _rule_based_predict_from_features(features)

        try:
            vec = _features_to_vector(features)
            pred = self._model.predict([vec])
            labels = self._binarizer.inverse_transform(pred)
            result = list(labels[0]) if labels[0] else ["positional"]
            return result
        except Exception as e:
            _LOG.warning("[focus_predictor] predict error, fallback: %s", e)
            return _rule_based_predict_from_features(features)

    def save(self, path: Optional[str] = None) -> str:
        """モデルをjoblib保存."""
        if not _HAS_SKLEARN:
            raise RuntimeError("scikit-learn not installed")
        if not self.is_trained:
            raise RuntimeError("model not trained")

        out = path or _DEFAULT_MODEL_PATH
        os.makedirs(os.path.dirname(out), exist_ok=True)
        joblib.dump(
            {"model": self._model, "binarizer": self._binarizer},
            out,
        )
        return out

    def load(self, path: Optional[str] = None) -> bool:
        """保存済みモデルを読み込み."""
        if not _HAS_SKLEARN:
            return False
        src = path or _DEFAULT_MODEL_PATH
        if not os.path.exists(src):
            return False
        try:
            data = joblib.load(src)
            self._model = data["model"]
            self._binarizer = data["binarizer"]
            return True
        except Exception as e:
            _LOG.warning("[focus_predictor] load error: %s", e)
            return False

    def evaluate(
        self,
        data_path: Optional[str] = None,
        n_splits: int = 5,
    ) -> Dict[str, Any]:
        """k-fold交差検証.

        Returns
        -------
        dict
            {mean_accuracy, std_accuracy, mean_f1_samples,
             mean_f1_macro, per_label_f1, confusion_per_label}
        """
        if not _HAS_SKLEARN:
            return {"error": "scikit-learn not installed"}

        data = _load_focus_data(data_path)
        if data.get("error"):
            return {"error": data["error"], "n_samples": data["n_samples"]}

        X = np.array(data["X"])
        y_labels = data["y_labels"]

        binarizer = MultiLabelBinarizer(classes=list(FOCUS_LABELS))
        Y = binarizer.fit_transform(y_labels)

        effective_splits = min(n_splits, len(X))
        if effective_splits < 2:
            effective_splits = 2

        kf = KFold(n_splits=effective_splits, shuffle=True, random_state=42)

        accuracies: List[float] = []
        f1_samples_list: List[float] = []
        f1_macro_list: List[float] = []
        per_label_f1_sums = np.zeros(len(FOCUS_LABELS))
        n_folds = 0

        for train_idx, val_idx in kf.split(X):
            X_train, X_val = X[train_idx], X[val_idx]
            Y_train, Y_val = Y[train_idx], Y[val_idx]

            clf = OneVsRestClassifier(
                RandomForestClassifier(
                    n_estimators=100, max_depth=8, random_state=42
                )
            )
            clf.fit(X_train, Y_train)
            preds = clf.predict(X_val)

            accuracies.append(float(accuracy_score(Y_val, preds)))
            f1_samples_list.append(
                float(f1_score(Y_val, preds, average="samples", zero_division=0))
            )
            f1_macro_list.append(
                float(f1_score(Y_val, preds, average="macro", zero_division=0))
            )

            per_label = f1_score(Y_val, preds, average=None, zero_division=0)
            per_label_f1_sums += per_label
            n_folds += 1

        avg_per_label = per_label_f1_sums / max(n_folds, 1)
        per_label_f1 = {
            lbl: round(float(avg_per_label[i]), 4)
            for i, lbl in enumerate(FOCUS_LABELS)
        }

        return {
            "n_samples": len(X),
            "n_splits": effective_splits,
            "mean_accuracy": round(float(np.mean(accuracies)), 4),
            "std_accuracy": round(float(np.std(accuracies)), 4),
            "mean_f1_samples": round(float(np.mean(f1_samples_list)), 4),
            "mean_f1_macro": round(float(np.mean(f1_macro_list)), 4),
            "per_label_f1": per_label_f1,
        }
