"""
backend/api/services/game_metrics.py
ルールベース棋力スコアとテンション指標の算出。
将来 ML モデルに差し替え可能なインターフェースで設計。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Skill Score
# ---------------------------------------------------------------------------

# delta_cp 閾値 (手番プレイヤー視点: 負=損、正=得)
_BEST_THRESH = -10       # delta_cp >= -10 → 最善手一致 (+3)
_SECOND_THRESH = -50     # delta_cp >= -50 → 次善手一致 (+1)
_BLUNDER_THRESH = -150   # delta_cp <= -150 → 悪手 (-2)

_POINTS_BEST = 3
_POINTS_SECOND = 1
_POINTS_NEUTRAL = 0
_POINTS_BLUNDER = -2

_GRADES = [
    (90, "S"),
    (75, "A"),
    (60, "B"),
    (40, "C"),
    (0,  "D"),
]


def _classify_move(delta_cp: int) -> int:
    """delta_cp からポイントを返す。"""
    if delta_cp >= _BEST_THRESH:
        return _POINTS_BEST
    if delta_cp >= _SECOND_THRESH:
        return _POINTS_SECOND
    if delta_cp <= _BLUNDER_THRESH:
        return _POINTS_BLUNDER
    return _POINTS_NEUTRAL


def _to_grade(score: int) -> str:
    for threshold, grade in _GRADES:
        if score >= threshold:
            return grade
    return "D"


def calculate_skill_score(
    notes: Optional[List[Dict[str, Any]]],
    total_moves: int,
) -> Dict[str, Any]:
    """
    バッチ解析 notes から棋力スコアを算出する。

    Parameters
    ----------
    notes : list[dict]
        各要素 {ply, move, delta_cp} (delta_cp は手番プレイヤー視点)
    total_moves : int
        棋譜全体の手数

    Returns
    -------
    dict
        {"score": int, "grade": str, "details": {...}}
    """
    if not notes or total_moves <= 0:
        return {"score": 0, "grade": "D", "details": {"best": 0, "second": 0, "blunder": 0, "evaluated": 0}}

    best_count = 0
    second_count = 0
    blunder_count = 0
    raw_sum = 0
    evaluated = 0

    for n in notes:
        d = n.get("delta_cp")
        if d is None:
            continue
        d = int(d)
        evaluated += 1
        pts = _classify_move(d)
        raw_sum += pts
        if pts == _POINTS_BEST:
            best_count += 1
        elif pts == _POINTS_SECOND:
            second_count += 1
        elif pts == _POINTS_BLUNDER:
            blunder_count += 1

    # 正規化: raw_sum / total_moves を 0-100 にスケール
    # 最大 = _POINTS_BEST (3) per move → score = (raw / total) * (100/3)
    if total_moves > 0:
        score = int(round((raw_sum / total_moves) * (100 / _POINTS_BEST)))
    else:
        score = 0
    score = max(0, min(100, score))

    return {
        "score": score,
        "grade": _to_grade(score),
        "details": {
            "best": best_count,
            "second": second_count,
            "blunder": blunder_count,
            "evaluated": evaluated,
        },
    }


# ---------------------------------------------------------------------------
# Tension Timeline
# ---------------------------------------------------------------------------

_WINDOW = 5        # 移動平均ウィンドウ幅
_SCALE = 200       # tension = clamp(avg / _SCALE, 0, 1)

_TENSION_LABELS = [
    (0.6, "激戦"),
    (0.3, "攻防あり"),
    (0.0, "穏やかな展開"),
]


def calculate_tension_timeline(
    eval_history: Optional[List[int]],
) -> Dict[str, Any]:
    """
    評価値推移からテンション指標を算出する。

    Parameters
    ----------
    eval_history : list[int]
        ply 0 から total_moves までの評価値リスト

    Returns
    -------
    dict
        {"timeline": [float], "avg": float, "label": str}
    """
    if not eval_history or len(eval_history) < 2:
        return {"timeline": [], "avg": 0.0, "label": "穏やかな展開"}

    # 各手の |delta_cp|
    abs_deltas = [abs(eval_history[i] - eval_history[i - 1]) for i in range(1, len(eval_history))]

    # 移動平均 (window=5)
    n = len(abs_deltas)
    smoothed: List[float] = []
    for i in range(n):
        start = max(0, i - _WINDOW + 1)
        window = abs_deltas[start : i + 1]
        smoothed.append(sum(window) / len(window))

    # tension = clamp(smoothed / _SCALE, 0, 1)
    timeline = [min(1.0, max(0.0, v / _SCALE)) for v in smoothed]

    avg_tension = sum(timeline) / len(timeline) if timeline else 0.0
    avg_tension = round(avg_tension, 3)

    label = "穏やかな展開"
    for threshold, lbl in _TENSION_LABELS:
        if avg_tension >= threshold:
            label = lbl
            break

    # timeline を小数第3位まで丸める
    timeline = [round(t, 3) for t in timeline]

    return {"timeline": timeline, "avg": avg_tension, "label": label}
