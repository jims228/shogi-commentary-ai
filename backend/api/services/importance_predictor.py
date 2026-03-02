"""解説タイミング予測 (Importance Prediction) MLモデル.

局面の特徴量から「この局面の解説重要度」（0.0-1.0）を予測する
回帰モデル。現状は等間隔で解説しているが、局面が動いた瞬間に
解説すべきかを判断するために使う。
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
    from sklearn.ensemble import GradientBoostingRegressor
    from sklearn.metrics import mean_absolute_error, r2_score
    from sklearn.model_selection import KFold
    import joblib

    _HAS_SKLEARN = True
except ImportError:
    _HAS_SKLEARN = False

from backend.api.services.ml_trainer import _FEATURE_KEYS, _features_to_vector

_DEFAULT_DATA_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "data")
)
_DEFAULT_CORPUS_PATH = os.path.join(
    _DEFAULT_DATA_DIR, "annotated", "merged_corpus.jsonl"
)
_DEFAULT_MODEL_PATH = os.path.join(
    _DEFAULT_DATA_DIR, "models", "importance_predictor.joblib"
)

_MIN_SAMPLES = 50

# Intent score mapping
_INTENT_SCORES: Dict[str, float] = {
    "sacrifice": 1.0,
    "attack": 0.7,
    "exchange": 0.5,
    "defense": 0.3,
    "development": 0.1,
}


# ---------------------------------------------------------------------------
# Extended feature engineering (11D)
# ---------------------------------------------------------------------------
def _features_to_extended_vector(features: Dict[str, Any]) -> List[float]:
    """8次元ベースベクトルに3次元追加して11次元に拡張."""
    base = _features_to_vector(features)

    td = features.get("tension_delta", {})
    d_ks = abs(float(td.get("d_king_safety", 0.0)))
    d_pa = abs(float(td.get("d_piece_activity", 0.0)))
    d_ap = abs(float(td.get("d_attack_pressure", 0.0)))

    tension_magnitude = d_ks + d_pa + d_ap
    is_endgame = 1.0 if features.get("phase") == "endgame" else 0.0
    intent = features.get("move_intent", "")
    intent_score = _INTENT_SCORES.get(intent, 0.0)

    return base + [tension_magnitude, is_endgame, intent_score]


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def _load_importance_data(
    data_path: Optional[str] = None,
) -> Dict[str, Any]:
    """annotated corpus から回帰用データを構築."""
    src = data_path or _DEFAULT_CORPUS_PATH
    if not os.path.exists(src):
        return {"X": [], "y": [], "n_samples": 0, "error": f"not found: {src}"}

    X: List[List[float]] = []
    y: List[float] = []

    with open(src, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                features = obj.get("features")
                ann = obj.get("annotation", {})
                importance = ann.get("importance")
                if features is None or importance is None:
                    continue
                X.append(_features_to_extended_vector(features))
                y.append(float(importance))
            except Exception:
                continue

    error = None
    if len(X) < _MIN_SAMPLES:
        error = f"insufficient samples ({len(X)} < {_MIN_SAMPLES})"

    return {
        "X": X,
        "y": y,
        "n_samples": len(X),
        "error": error,
    }


# ---------------------------------------------------------------------------
# Rule-based fallback
# ---------------------------------------------------------------------------
def _rule_based_importance(features: Dict[str, Any]) -> float:
    """annotation_service._estimate_importance 互換のルールベース."""
    td = features.get("tension_delta", {})
    d_ks = abs(float(td.get("d_king_safety", 0.0)))
    d_pa = abs(float(td.get("d_piece_activity", 0.0)))
    d_ap = abs(float(td.get("d_attack_pressure", 0.0)))

    raw = (d_ks + d_pa + d_ap) / 30.0

    phase = features.get("phase", "midgame")
    intent = features.get("move_intent")

    if phase == "endgame":
        raw += 0.2
    if intent in ("sacrifice", "attack"):
        raw += 0.1

    return round(min(1.0, max(0.0, raw)), 2)


# ---------------------------------------------------------------------------
# ImportancePredictor
# ---------------------------------------------------------------------------
class ImportancePredictor:
    """解説タイミング予測: 局面の重要度を0.0-1.0で予測."""

    def __init__(self) -> None:
        self._model: Any = None  # GradientBoostingRegressor
        self._trained = False

    @property
    def is_trained(self) -> bool:
        return self._trained and self._model is not None

    def train(self, data_path: Optional[str] = None) -> Dict[str, Any]:
        """アノテーション済みデータから訓練.

        Returns
        -------
        dict
            {n_samples, mean_importance, std_importance,
             train_r2, train_mae}
        """
        if not _HAS_SKLEARN:
            return {"error": "scikit-learn not installed", "n_samples": 0}

        data = _load_importance_data(data_path)
        if data.get("error"):
            return {"error": data["error"], "n_samples": data["n_samples"]}

        X = np.array(data["X"])
        y = np.array(data["y"])

        reg = GradientBoostingRegressor(
            n_estimators=100, max_depth=4, random_state=42,
            learning_rate=0.1,
        )
        reg.fit(X, y)

        self._model = reg
        self._trained = True

        # Training metrics
        preds = reg.predict(X)
        train_r2 = float(r2_score(y, preds))
        train_mae = float(mean_absolute_error(y, preds))

        return {
            "n_samples": len(X),
            "mean_importance": round(float(np.mean(y)), 4),
            "std_importance": round(float(np.std(y)), 4),
            "train_r2": round(train_r2, 4),
            "train_mae": round(train_mae, 4),
        }

    def predict(self, features: Dict[str, Any]) -> float:
        """局面特徴量から重要度を予測.

        未訓練時はルールベースにフォールバック。
        Returns: float 0.0-1.0
        """
        if not self.is_trained or not _HAS_SKLEARN:
            return _rule_based_importance(features)

        try:
            vec = _features_to_extended_vector(features)
            pred = float(self._model.predict([vec])[0])
            return round(min(1.0, max(0.0, pred)), 2)
        except Exception as e:
            _LOG.warning("[importance_predictor] predict error, fallback: %s", e)
            return _rule_based_importance(features)

    def should_explain(self, features: Dict[str, Any], threshold: float = 0.5) -> bool:
        """この局面を解説すべきか判定.

        predict() >= threshold なら True。
        """
        return self.predict(features) >= threshold

    def evaluate(
        self,
        data_path: Optional[str] = None,
        n_splits: int = 5,
    ) -> Dict[str, Any]:
        """k-fold交差検証.

        Returns
        -------
        dict
            {n_samples, n_splits, mean_r2, std_r2, mean_mae, std_mae}
        """
        if not _HAS_SKLEARN:
            return {"error": "scikit-learn not installed"}

        data = _load_importance_data(data_path)
        if data.get("error"):
            return {"error": data["error"], "n_samples": data["n_samples"]}

        X = np.array(data["X"])
        y = np.array(data["y"])

        effective_splits = min(n_splits, len(X))
        if effective_splits < 2:
            effective_splits = 2

        kf = KFold(n_splits=effective_splits, shuffle=True, random_state=42)

        r2_scores: List[float] = []
        mae_scores: List[float] = []

        for train_idx, val_idx in kf.split(X):
            X_train, X_val = X[train_idx], X[val_idx]
            y_train, y_val = y[train_idx], y[val_idx]

            reg = GradientBoostingRegressor(
                n_estimators=100, max_depth=4, random_state=42,
                learning_rate=0.1,
            )
            reg.fit(X_train, y_train)
            preds = reg.predict(X_val)

            r2_scores.append(float(r2_score(y_val, preds)))
            mae_scores.append(float(mean_absolute_error(y_val, preds)))

        return {
            "n_samples": len(X),
            "n_splits": effective_splits,
            "mean_r2": round(float(np.mean(r2_scores)), 4),
            "std_r2": round(float(np.std(r2_scores)), 4),
            "mean_mae": round(float(np.mean(mae_scores)), 4),
            "std_mae": round(float(np.std(mae_scores)), 4),
        }

    def save(self, path: Optional[str] = None) -> str:
        """モデルをjoblib保存."""
        if not _HAS_SKLEARN:
            raise RuntimeError("scikit-learn not installed")
        if not self.is_trained:
            raise RuntimeError("model not trained")

        out = path or _DEFAULT_MODEL_PATH
        os.makedirs(os.path.dirname(out), exist_ok=True)
        joblib.dump(self._model, out)
        return out

    def load(self, path: Optional[str] = None) -> bool:
        """保存済みモデルを読み込み."""
        if not _HAS_SKLEARN:
            return False
        src = path or _DEFAULT_MODEL_PATH
        if not os.path.exists(src):
            return False
        try:
            self._model = joblib.load(src)
            self._trained = True
            return True
        except Exception as e:
            _LOG.warning("[importance_predictor] load error: %s", e)
            return False
