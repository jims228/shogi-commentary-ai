"""解説スタイル自動選択器.

ルールベース fallback + scikit-learn DecisionTreeClassifier で
局面特徴量から最適な解説スタイルを予測する。

Styles: technical, encouraging, dramatic, neutral
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

_LOG = logging.getLogger("uvicorn.error")

# scikit-learn はオプション依存
try:
    from sklearn.tree import DecisionTreeClassifier
    import joblib
    _HAS_SKLEARN = True
except ImportError:
    _HAS_SKLEARN = False

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------
STYLES = ("technical", "encouraging", "dramatic", "neutral")

_DEFAULT_MODEL_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "data", "models"
)
_MODEL_PATH = os.path.normpath(
    os.getenv("STYLE_MODEL_PATH",
              os.path.join(_DEFAULT_MODEL_DIR, "style_selector.joblib"))
)

# 特徴量キーの順序 (ベクトル化時に使用)
_FEATURE_KEYS = [
    "king_safety",
    "piece_activity",
    "attack_pressure",
    "ply",
    "d_king_safety",
    "d_piece_activity",
    "d_attack_pressure",
    "phase_num",  # opening=0, midgame=1, endgame=2
]

_PHASE_MAP = {"opening": 0, "midgame": 1, "endgame": 2}


# ---------------------------------------------------------------------------
# ルールベース予測 (常に利用可能)
# ---------------------------------------------------------------------------
def rule_based_predict(features: Dict[str, Any]) -> str:
    """局面特徴量からルールベースでスタイルを選択する.

    - dramatic: 攻撃圧力が高い or 終盤
    - technical: 中盤で駒活用度が高い
    - encouraging: 序盤 or 安全度が高い
    - neutral: その他
    """
    phase = features.get("phase", "midgame")
    ap = features.get("attack_pressure", 0)
    ks = features.get("king_safety", 50)
    pa = features.get("piece_activity", 50)

    # dramatic: 激しい局面
    if ap >= 50 or (phase == "endgame" and ap >= 30):
        return "dramatic"

    # technical: 中盤の複雑な駒運び
    if phase == "midgame" and pa >= 50:
        return "technical"

    # encouraging: 穏やかな序盤 or 安全な局面
    if phase == "opening" or ks >= 60:
        return "encouraging"

    return "neutral"


# ---------------------------------------------------------------------------
# スタイルラベリング (品質スコアから自動ラベル付け)
# ---------------------------------------------------------------------------
def label_style_from_scores(
    scores: Dict[str, int],
    features: Dict[str, Any],
) -> str:
    """評価スコアと特徴量からスタイルラベルを決定.

    scores: {context_relevance, naturalness, informativeness, readability}
    """
    phase = features.get("phase", "midgame")
    ap = features.get("attack_pressure", 0)

    info = scores.get("informativeness", 50)
    natural = scores.get("naturalness", 50)
    context = scores.get("context_relevance", 50)

    # informativeness が高い → technical
    if info >= 70:
        return "technical"

    # dramatic: 攻撃圧力が高い局面でcontext_relevanceも高い
    if ap >= 40 and context >= 70:
        return "dramatic"

    # encouraging: naturalness が高く穏やかな局面
    if natural >= 70 and ap < 30:
        return "encouraging"

    return "neutral"


# ---------------------------------------------------------------------------
# 特徴量 → ベクトル変換
# ---------------------------------------------------------------------------
def _features_to_vector(features: Dict[str, Any]) -> List[float]:
    """特徴量辞書を固定長の数値ベクトルに変換."""
    td = features.get("tension_delta", {})
    phase = features.get("phase", "midgame")

    return [
        float(features.get("king_safety", 50)),
        float(features.get("piece_activity", 50)),
        float(features.get("attack_pressure", 0)),
        float(features.get("ply", 0)),
        float(td.get("d_king_safety", 0.0)),
        float(td.get("d_piece_activity", 0.0)),
        float(td.get("d_attack_pressure", 0.0)),
        float(_PHASE_MAP.get(phase, 1)),
    ]


# ---------------------------------------------------------------------------
# ML スタイル選択器
# ---------------------------------------------------------------------------
class CommentaryStyleSelector:
    """解説スタイルを予測するクラス.

    scikit-learn が利用可能な場合は DecisionTreeClassifier で予測。
    利用不可または未学習の場合は rule_based_predict にフォールバック。
    """

    def __init__(self) -> None:
        self._model: Any = None
        self._label_to_idx: Dict[str, int] = {s: i for i, s in enumerate(STYLES)}
        self._idx_to_label: Dict[int, str] = {i: s for i, s in enumerate(STYLES)}

    @property
    def is_trained(self) -> bool:
        return self._model is not None

    def predict(self, features: Dict[str, Any]) -> str:
        """局面特徴量からスタイルを予測."""
        if self._model is None:
            return rule_based_predict(features)
        try:
            vec = _features_to_vector(features)
            pred = self._model.predict([vec])[0]
            return self._idx_to_label.get(int(pred), "neutral")
        except Exception as e:
            _LOG.warning("[style_selector] predict error, fallback: %s", e)
            return rule_based_predict(features)

    def train(self, log_dir: Optional[str] = None) -> Dict[str, Any]:
        """トレーニングログからモデルを学習.

        Returns
        -------
        dict
            samples, accuracy (on training set), styles distribution
        """
        if not _HAS_SKLEARN:
            return {"error": "scikit-learn not installed", "samples": 0}

        from backend.api.services.explanation_evaluator import evaluate_explanation

        default_log_dir = os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "data", "training_logs"
        )
        src = log_dir or os.path.normpath(
            os.getenv("TRAINING_LOG_DIR", default_log_dir)
        )

        X: List[List[float]] = []
        y: List[int] = []

        if not os.path.isdir(src):
            return {"error": f"log dir not found: {src}", "samples": 0}

        for name in sorted(os.listdir(src)):
            if not name.endswith(".jsonl"):
                continue
            path = os.path.join(src, name)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        obj = json.loads(line)
                        explanation = (obj.get("output") or {}).get(
                            "explanation", ""
                        )
                        feats = (obj.get("input") or {}).get("features")
                        if not explanation or not feats:
                            continue
                        ev = evaluate_explanation(explanation, feats)
                        label = label_style_from_scores(ev["scores"], feats)
                        X.append(_features_to_vector(feats))
                        y.append(self._label_to_idx[label])
            except Exception:
                continue

        if len(X) < 10:
            return {"error": "insufficient samples", "samples": len(X)}

        clf = DecisionTreeClassifier(max_depth=5, random_state=42)
        clf.fit(X, y)
        self._model = clf

        # Training accuracy
        preds = clf.predict(X)
        correct = sum(1 for a, b in zip(preds, y) if a == b)
        accuracy = round(correct / len(y), 3)

        # Style distribution
        dist = {s: 0 for s in STYLES}
        for idx in y:
            dist[self._idx_to_label[idx]] += 1

        return {
            "samples": len(X),
            "accuracy": accuracy,
            "distribution": dist,
        }

    def save(self, path: Optional[str] = None) -> str:
        """学習済みモデルを保存."""
        if not _HAS_SKLEARN:
            raise RuntimeError("scikit-learn not installed")
        if self._model is None:
            raise RuntimeError("model not trained")

        out = path or _MODEL_PATH
        os.makedirs(os.path.dirname(out), exist_ok=True)
        joblib.dump(self._model, out)
        return out

    def load(self, path: Optional[str] = None) -> bool:
        """保存済みモデルを読み込む."""
        if not _HAS_SKLEARN:
            return False
        src = path or _MODEL_PATH
        if not os.path.exists(src):
            return False
        try:
            self._model = joblib.load(src)
            return True
        except Exception as e:
            _LOG.warning("[style_selector] load error: %s", e)
            return False
