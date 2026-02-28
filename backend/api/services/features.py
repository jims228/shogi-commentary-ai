"""
backend/api/services/features.py
エンジン解析結果（AnnotateResponse）と bioshogi 結果から
MoveExplanation（backend/models/explanation.py）を生成する。
"""
from __future__ import annotations

from typing import List, Dict, Any, Optional

from backend.models.explanation import MoveExplanation, MoveType, Phase, GameReport


def classify_move_type(attack_tags: List[str], defense_tags: List[str]) -> Optional[MoveType]:
    """bioshogi の attack/defense タグから手の性質を分類"""
    has_attack = len(attack_tags) > 0
    has_defense = len(defense_tags) > 0
    if has_attack and has_defense:
        return MoveType.both
    elif has_attack:
        return MoveType.attack
    elif has_defense:
        return MoveType.defense
    return None


def classify_phase(ply: int) -> Phase:
    """手数から局面フェーズを判定"""
    if ply <= 20:
        return Phase.opening
    elif ply <= 80:
        return Phase.middle
    else:
        return Phase.endgame


def classify_blunder(delta_cp: Optional[int]) -> List[str]:
    """評価値の変化から悪手タグを生成"""
    # delta_cp は自分視点での変化（負 = 悪化）
    if delta_cp is None:
        return []
    if delta_cp <= -300:
        return ["大悪手"]
    elif delta_cp <= -150:
        return ["悪手"]
    elif delta_cp <= -50:
        return ["疑問手"]
    return []


def build_move_explanation(
    ply: int,
    move: str,
    eval_before: Optional[int],
    eval_after: Optional[int],
    pv: List[str],
    bioshogi_sente: Dict[str, List[str]],
    bioshogi_gote: Dict[str, List[str]],
    is_gote: bool,
) -> MoveExplanation:
    """1手分の MoveExplanation を構築"""
    eval_delta = None
    if eval_before is not None and eval_after is not None:
        eval_delta = eval_after - eval_before

    # 手番側の bioshogi 情報を使う
    bio = bioshogi_gote if is_gote else bioshogi_sente

    move_type = classify_move_type(bio.get("attack", []), bio.get("defense", []))
    phase = classify_phase(ply)

    return MoveExplanation(
        ply=ply,
        move=move,
        eval_before=eval_before,
        eval_after=eval_after,
        eval_delta=eval_delta,
        move_type=move_type,
        tactical_themes=bio.get("technique", []),
        position_phase=phase,
        castle_info=bio.get("defense", [None])[0],
        attack_info=bio.get("attack", [None])[0],
        technique_info=bio.get("technique", []),
    )


def notes_to_explanations(
    notes: List[Dict[str, Any]],
    bioshogi: Optional[Dict[str, Any]] = None,
) -> List[MoveExplanation]:
    """annotate() の notes を MoveExplanation リストに変換"""
    explanations = []
    bioshogi_sente = (bioshogi or {}).get("sente", {})
    bioshogi_gote = (bioshogi or {}).get("gote", {})

    for note in notes:
        ply = note.get("ply", 0)
        is_gote = ply % 2 == 0
        exp = build_move_explanation(
            ply=ply,
            move=note.get("move", ""),
            eval_before=note.get("score_before_cp"),
            eval_after=note.get("score_after_cp"),
            pv=note.get("pv", []),
            bioshogi_sente=bioshogi_sente,
            bioshogi_gote=bioshogi_gote,
            is_gote=is_gote,
        )
        explanations.append(exp)

    return explanations
