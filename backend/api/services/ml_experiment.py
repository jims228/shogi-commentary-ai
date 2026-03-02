"""MLモデル実験フレームワーク.

複数モデルのk-fold交差検証、結果の保存・比較を行う。
"""
from __future__ import annotations

import json
import logging
import os
import time
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np

_LOG = logging.getLogger("uvicorn.error")

try:
    from sklearn.tree import DecisionTreeClassifier
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.model_selection import StratifiedKFold
    from sklearn.metrics import accuracy_score, f1_score, confusion_matrix
    _HAS_SKLEARN = True
except ImportError:
    _HAS_SKLEARN = False

from backend.api.services.ml_trainer import (
    STYLES, _FEATURE_KEYS, load_training_data,
)

# -----------------------------------------------------------------------
# Model registry — maps class name strings to sklearn classes safely
# -----------------------------------------------------------------------
_MODEL_REGISTRY: Dict[str, type] = {}
if _HAS_SKLEARN:
    _MODEL_REGISTRY = {
        "DecisionTreeClassifier": DecisionTreeClassifier,
        "RandomForestClassifier": RandomForestClassifier,
        "GradientBoostingClassifier": GradientBoostingClassifier,
    }

_DEFAULT_EXPERIMENTS_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "experiments")
)


class ExperimentRunner:
    """複数モデルのk-fold CVを実行し、結果を比較する."""

    def __init__(self, experiments_dir: Optional[str] = None) -> None:
        self._experiments_dir = experiments_dir or _DEFAULT_EXPERIMENTS_DIR

    def run_experiment(
        self,
        name: str,
        model_configs: List[Dict[str, Any]],
        data_path: Optional[str] = None,
        n_splits: int = 5,
    ) -> Dict[str, Any]:
        """Run k-fold CV experiment with multiple model configurations.

        Parameters
        ----------
        name : str
            Experiment name.
        model_configs : list of dict
            Each: {"name": str, "class": str, "params": dict}
        data_path : str, optional
            Training log directory.
        n_splits : int
            Number of CV folds.

        Returns
        -------
        dict
            Experiment result with per-model metrics and best_model.
        """
        if not _HAS_SKLEARN:
            return {"error": "scikit-learn not installed"}

        data = load_training_data(log_dir=data_path)
        if data.get("error"):
            return {"error": data["error"], "n_samples": data["n_samples"]}

        X = np.array(data["X"])
        y = np.array(data["y"])

        # Validate model configs
        for cfg in model_configs:
            cls_name = cfg.get("class", "")
            if cls_name not in _MODEL_REGISTRY:
                return {
                    "error": f"Unknown model class: {cls_name}. "
                    f"Available: {list(_MODEL_REGISTRY.keys())}",
                }

        # Guard: n_splits must not exceed smallest class count
        class_counts = Counter(int(v) for v in y)
        min_class = min(class_counts.values()) if class_counts else 1
        effective_splits = min(n_splits, min_class)
        if effective_splits < 2:
            effective_splits = 2

        skf = StratifiedKFold(
            n_splits=effective_splits, shuffle=True, random_state=42
        )
        model_results: List[Dict[str, Any]] = []

        for cfg in model_configs:
            result = self._evaluate_model(cfg, X, y, skf)
            model_results.append(result)

        best = max(model_results, key=lambda r: r["f1_macro_mean"])

        return {
            "name": name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data_path": data_path or "(default)",
            "n_samples": len(X),
            "n_splits": effective_splits,
            "style_distribution": data["distribution"],
            "models": model_results,
            "best_model": best["name"],
        }

    def _evaluate_model(
        self,
        cfg: Dict[str, Any],
        X: "np.ndarray",
        y: "np.ndarray",
        skf: Any,
    ) -> Dict[str, Any]:
        """Evaluate a single model config with k-fold CV."""
        cls = _MODEL_REGISTRY[cfg["class"]]
        params = cfg.get("params", {})
        model_name = cfg["name"]

        accuracies: List[float] = []
        f1_scores_list: List[float] = []
        cm_sum = np.zeros((len(STYLES), len(STYLES)), dtype=int)
        importances_sum = np.zeros(len(_FEATURE_KEYS))
        n_folds_with_importance = 0

        start = time.time()

        for train_idx, val_idx in skf.split(X, y):
            X_train, X_val = X[train_idx], X[val_idx]
            y_train, y_val = y[train_idx], y[val_idx]

            model = cls(random_state=42, **params)
            model.fit(X_train, y_train)
            preds = model.predict(X_val)

            accuracies.append(accuracy_score(y_val, preds))
            f1_scores_list.append(
                f1_score(y_val, preds, average="macro", zero_division=0)
            )

            cm = confusion_matrix(
                y_val, preds, labels=list(range(len(STYLES)))
            )
            cm_sum += cm

            if hasattr(model, "feature_importances_"):
                importances_sum += model.feature_importances_
                n_folds_with_importance += 1

        elapsed = time.time() - start

        feat_importance: Dict[str, float] = {}
        if n_folds_with_importance > 0:
            avg_imp = importances_sum / n_folds_with_importance
            feat_importance = {
                _FEATURE_KEYS[i]: round(float(avg_imp[i]), 4)
                for i in range(len(_FEATURE_KEYS))
            }

        return {
            "name": model_name,
            "class": cfg["class"],
            "params": params,
            "accuracy_mean": round(float(np.mean(accuracies)), 4),
            "accuracy_std": round(float(np.std(accuracies)), 4),
            "f1_macro_mean": round(float(np.mean(f1_scores_list)), 4),
            "f1_macro_std": round(float(np.std(f1_scores_list)), 4),
            "confusion_matrix": cm_sum.tolist(),
            "feature_importance": feat_importance,
            "train_time_seconds": round(elapsed, 3),
        }

    def save_experiment(self, result: Dict[str, Any]) -> str:
        """Save experiment result to JSON file. Returns file path."""
        os.makedirs(self._experiments_dir, exist_ok=True)
        name = result.get("name", "unnamed")
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"{name}_{ts}.json"
        path = os.path.join(self._experiments_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        return path

    def load_experiment(self, name: str) -> Optional[Dict[str, Any]]:
        """Load the latest experiment matching the given name prefix."""
        if not os.path.isdir(self._experiments_dir):
            return None
        matches = sorted([
            f for f in os.listdir(self._experiments_dir)
            if f.startswith(name) and f.endswith(".json")
        ])
        if not matches:
            return None
        path = os.path.join(self._experiments_dir, matches[-1])
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def compare_experiments(self, *names: str) -> Dict[str, Any]:
        """Load and compare multiple experiment results side by side."""
        experiments: List[Dict[str, Any]] = []
        for n in names:
            exp = self.load_experiment(n)
            if exp is not None:
                experiments.append(exp)

        comparison: List[Dict[str, Any]] = []
        for exp in experiments:
            best_model_result = max(
                exp.get("models", []),
                key=lambda m: m.get("f1_macro_mean", 0),
                default={},
            )
            comparison.append({
                "experiment_name": exp.get("name", "unknown"),
                "timestamp": exp.get("timestamp", ""),
                "n_samples": exp.get("n_samples", 0),
                "best_model": exp.get("best_model", ""),
                "best_f1_macro": best_model_result.get("f1_macro_mean", 0),
                "best_accuracy": best_model_result.get("accuracy_mean", 0),
            })

        return {"experiments": experiments, "comparison": comparison}
