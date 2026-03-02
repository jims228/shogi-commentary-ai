"""アノテーション済み解説データのスキーマ定義.

3つのMLタスク用ラベル:
  A. Focus Prediction — 局面のどの要素に言及すべきか
  B. Explanation Importance — この局面は解説すべきか (0.0-1.0)
  C. Explanation Depth — surface / strategic / deep
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from backend.api.services.ml_trainer import STYLES

# ---------------------------------------------------------------------------
# Label constants
# ---------------------------------------------------------------------------
FOCUS_LABELS: Tuple[str, ...] = (
    "king_safety",
    "piece_activity",
    "attack_pressure",
    "positional",
    "tempo",
    "endgame_technique",
)

DEPTH_LEVELS: Tuple[str, ...] = (
    "surface",
    "strategic",
    "deep",
)

SOURCES: Tuple[str, ...] = (
    "nhk",
    "mobile",
    "blog",
    "template",
    "gemini",
)

ANNOTATORS: Tuple[str, ...] = (
    "human",
    "gemini-auto",
    "gemini-reviewed",
    "rule-based",
)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def validate_annotation(record: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """アノテーションレコードのバリデーション.

    Parameters
    ----------
    record : dict
        annotation フィールドを含むレコード。

    Returns
    -------
    (bool, list[str])
        (valid, error_messages)
    """
    errors: List[str] = []

    ann = record.get("annotation")
    if ann is None:
        return False, ["missing 'annotation' field"]

    # --- focus ---
    focus = ann.get("focus")
    if focus is None:
        errors.append("missing 'annotation.focus'")
    elif not isinstance(focus, list):
        errors.append("'annotation.focus' must be a list")
    else:
        for label in focus:
            if label not in FOCUS_LABELS:
                errors.append(
                    f"invalid focus label: '{label}'. "
                    f"Valid: {list(FOCUS_LABELS)}"
                )

    # --- importance ---
    importance = ann.get("importance")
    if importance is None:
        errors.append("missing 'annotation.importance'")
    elif not isinstance(importance, (int, float)):
        errors.append("'annotation.importance' must be a number")
    elif not (0.0 <= float(importance) <= 1.0):
        errors.append(
            f"'annotation.importance' must be 0.0-1.0, got {importance}"
        )

    # --- depth ---
    depth = ann.get("depth")
    if depth is None:
        errors.append("missing 'annotation.depth'")
    elif depth not in DEPTH_LEVELS:
        errors.append(
            f"invalid depth: '{depth}'. Valid: {list(DEPTH_LEVELS)}"
        )

    # --- style ---
    style = ann.get("style")
    if style is None:
        errors.append("missing 'annotation.style'")
    elif style not in STYLES:
        errors.append(
            f"invalid style: '{style}'. Valid: {list(STYLES)}"
        )

    return (len(errors) == 0, errors)
