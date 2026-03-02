"""解説プロンプト強化モジュール.

FocusPredictor の出力を使い、局面の着目ポイントに応じた
解説ガイドをプロンプトに付加する。
"""
from __future__ import annotations

from typing import Any, Dict, List

from backend.api.schemas.annotation import FOCUS_LABELS

# ---------------------------------------------------------------------------
# Focus descriptions (日本語)
# ---------------------------------------------------------------------------
FOCUS_DESCRIPTIONS: Dict[str, str] = {
    "king_safety": "玉の安全性・囲いの堅さ",
    "piece_activity": "駒の活用度・働き",
    "attack_pressure": "攻めの圧力・寄せの可能性",
    "positional": "形勢・陣形のバランス",
    "tempo": "手番の利・手損得",
    "endgame_technique": "終盤の寄せ・受けの技術",
}

_TALKING_POINTS: Dict[str, str] = {
    "king_safety": "玉の守りが堅いか崩れているかに注目してください",
    "piece_activity": "駒の配置と活用度を中心に解説してください",
    "attack_pressure": "攻めの圧力と寄せの狙いを解説してください",
    "positional": "陣形のバランスと形勢判断に触れてください",
    "tempo": "手番の利を活かした展開に着目してください",
    "endgame_technique": "終盤の寄せ手順や受けの技術に注目してください",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def enhance_prompt_with_focus(
    base_features: Dict[str, Any],
    focus_labels: List[str],
) -> Dict[str, Any]:
    """特徴量にfocus情報を追加してプロンプト強化用のdictを返す.

    Parameters
    ----------
    base_features : dict
        extract_position_features() 形式の局面特徴量。
    focus_labels : list[str]
        FocusPredictor.predict() の出力。

    Returns
    -------
    dict
        {features, focus, focus_descriptions, suggested_talking_points}
    """
    valid_labels = [l for l in focus_labels if l in FOCUS_LABELS]
    if not valid_labels:
        valid_labels = ["positional"]

    descriptions = {
        lbl: FOCUS_DESCRIPTIONS[lbl]
        for lbl in valid_labels
        if lbl in FOCUS_DESCRIPTIONS
    }

    talking_points = [
        _TALKING_POINTS[lbl]
        for lbl in valid_labels
        if lbl in _TALKING_POINTS
    ]

    return {
        "features": base_features,
        "focus": valid_labels,
        "focus_descriptions": descriptions,
        "suggested_talking_points": talking_points,
    }


# ---------------------------------------------------------------------------
# Importance-based explanation timing
# ---------------------------------------------------------------------------
def should_explain_position(
    features: Dict[str, Any],
    threshold: float = 0.5,
) -> Dict[str, Any]:
    """局面の解説要否を判断.

    ImportancePredictor が訓練済みならMLで予測、
    なければルールベースで判定する。

    Parameters
    ----------
    features : dict
        extract_position_features() 形式の局面特徴量。
    threshold : float
        重要度がこの値以上なら解説する。

    Returns
    -------
    dict
        {should_explain: bool, importance: float, reason: str}
    """
    from backend.api.services.importance_predictor import (
        ImportancePredictor,
        _rule_based_importance,
    )

    predictor = ImportancePredictor()
    predictor.load()

    importance = predictor.predict(features)
    reason = _classify_reason(features)

    return {
        "should_explain": importance >= threshold,
        "importance": importance,
        "reason": reason,
    }


def _classify_reason(features: Dict[str, Any]) -> str:
    """解説理由を分類."""
    td = features.get("tension_delta", {})
    d_ks = abs(float(td.get("d_king_safety", 0.0)))
    d_pa = abs(float(td.get("d_piece_activity", 0.0)))
    d_ap = abs(float(td.get("d_attack_pressure", 0.0)))
    tension_mag = d_ks + d_pa + d_ap

    if tension_mag > 15:
        return "high_tension"

    intent = features.get("move_intent", "")
    if intent in ("sacrifice", "attack"):
        return "key_move"

    phase = features.get("phase", "midgame")
    if phase == "endgame":
        return "phase_change"

    return "routine"
