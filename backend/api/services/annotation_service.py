"""ルールベース半自動アノテーションサービス.

既存の解説テキストと局面特徴量から、3つのMLタスク用ラベルを自動推定する。
Gemini API を呼ばず、キーワードマッチングとヒューリスティクスのみで動作する。
"""
from __future__ import annotations

from typing import Any, Dict, List

from backend.api.services.explanation_evaluator import evaluate_explanation
from backend.api.services.ml_trainer import STYLES, label_style_from_scores

# ---------------------------------------------------------------------------
# Focus detection keywords
# ---------------------------------------------------------------------------
_FOCUS_KEYWORDS: Dict[str, List[str]] = {
    "king_safety": [
        "玉", "囲い", "守り", "王", "安全", "固め",
        "美濃", "矢倉", "穴熊", "雁木", "守る", "備え",
    ],
    "attack_pressure": [
        "攻め", "攻撃", "狙い", "寄せ", "王手", "詰み",
        "突破", "仕掛け", "踏み込", "圧力", "迫る", "殺到",
    ],
    "piece_activity": [
        "活用", "働き", "効率", "利き", "成る", "打つ",
        "配置", "駒組み",
    ],
    "positional": [
        "形", "陣形", "バランス", "位", "模様", "厚み",
        "手筋", "筋",
    ],
    "tempo": [
        "手番", "先手", "後手", "テンポ", "手損", "手得",
    ],
    "endgame_technique": [
        "終盤", "寄せ", "詰み", "必至", "詰めろ", "入玉", "秒読み",
    ],
}

# Intent keywords for depth estimation
_INTENT_WORDS = ("ため", "狙い", "準備", "意図", "目的", "つもり")
_CONDITIONAL_WORDS = ("もし", "場合", "仮に", "一方", "ところが", "しかし")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def annotate_text(text: str, features: Dict[str, Any]) -> Dict[str, Any]:
    """解説テキストと局面特徴量からアノテーションを自動推定.

    Parameters
    ----------
    text : str
        解説テキスト。
    features : dict
        extract_position_features() 形式の局面特徴量。

    Returns
    -------
    dict
        {"focus": [...], "importance": float, "depth": str, "style": str}
    """
    return {
        "focus": _detect_focus(text),
        "importance": _estimate_importance(features),
        "depth": _estimate_depth(text),
        "style": _estimate_style(text, features),
    }


# ---------------------------------------------------------------------------
# Focus detection
# ---------------------------------------------------------------------------
def _detect_focus(text: str) -> List[str]:
    """テキスト中のキーワードから着目点ラベルを推定."""
    found: List[str] = []
    for label, keywords in _FOCUS_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                found.append(label)
                break
    return found if found else ["positional"]


# ---------------------------------------------------------------------------
# Importance estimation
# ---------------------------------------------------------------------------
def _estimate_importance(features: Dict[str, Any]) -> float:
    """局面特徴量の変化幅から解説重要度を推定.

    tension_delta の絶対値の合計を 0.0-1.0 に正規化。
    終盤やアクティブな意図でブースト。
    """
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
# Depth estimation
# ---------------------------------------------------------------------------
def _estimate_depth(text: str) -> str:
    """テキスト長とキーワードから説明深度を推定."""
    length = len(text)
    has_intent = any(w in text for w in _INTENT_WORDS)
    has_conditional = any(w in text for w in _CONDITIONAL_WORDS)

    if length > 80 and has_conditional:
        return "deep"
    if length >= 30 or has_intent:
        return "strategic"
    return "surface"


# ---------------------------------------------------------------------------
# Style estimation
# ---------------------------------------------------------------------------
def _estimate_style(text: str, features: Dict[str, Any]) -> str:
    """既存のルールベース評価からスタイルラベルを推定."""
    ev = evaluate_explanation(text, features)
    return label_style_from_scores(ev["scores"], features)
