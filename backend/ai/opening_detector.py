from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from backend.api.utils.shogi_explain_core import piece_kind_upper, piece_side, xy_to_file_rank


@dataclass
class Detected:
    id: str
    nameJa: str
    confidence: float
    reasons: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "nameJa": self.nameJa,
            "confidence": float(self.confidence),
            "reasons": list(self.reasons or []),
        }


def _unknown(kind: str) -> Detected:
    return Detected(id="unknown", nameJa=f"不明（{kind}）", confidence=0.0, reasons=[])


def _find_rook_file(board: List[List[Optional[str]]], side: str) -> Optional[int]:
    # side: 'b' or 'w'
    for y in range(9):
        for x in range(9):
            p = board[y][x]
            if not p:
                continue
            if piece_side(p) != side:
                continue
            if piece_kind_upper(p) in ("R", "+R"):
                file_, _ = xy_to_file_rank(x, y)
                return file_
    return None


def detect_style(board: List[List[Optional[str]]], side: str) -> Detected:
    """
    Detect high-level style (居飛車/振り飛車) by rook file.
    - side='b': rook start file=2
    - side='w': rook start file=8
    """
    rf = _find_rook_file(board, side)
    if rf is None:
        return _unknown("戦型")

    if side == "b":
        if rf == 2:
            return Detected(
                id="ibisha",
                nameJa="居飛車",
                confidence=0.85,
                reasons=[f"飛車が2筋（{rf}筋）にある → 居飛車系"],
            )
        return Detected(
            id="furibisha",
            nameJa="振り飛車",
            confidence=0.9 if rf in (5, 6, 7, 8) else 0.7,
            reasons=[f"飛車が2筋から外れて{rf}筋にある → 振り飛車系"],
        )

    # gote
    if rf == 8:
        return Detected(
            id="ibisha",
            nameJa="居飛車",
            confidence=0.85,
            reasons=[f"飛車が8筋（{rf}筋）にある → 居飛車系"],
        )
    return Detected(
        id="furibisha",
        nameJa="振り飛車",
        confidence=0.9 if rf in (2, 3, 4, 5) else 0.7,
        reasons=[f"飛車が8筋から外れて{rf}筋にある → 振り飛車系"],
    )


def detect_opening(board: List[List[Optional[str]]], moves: List[str], side: str) -> Detected:
    """
    Detect opening (戦法) by simple, high-signal features.
    Preference: avoid false positives -> unknown when unsure.
    """
    rf = _find_rook_file(board, side)
    if rf is None:
        return _unknown("戦法")

    # 1) Bishop exchange (角換わり) – detect by early bishop capture moves from start squares.
    # - sente bishop start: 8h, capture line often starts with 8h2b...
    # - gote bishop start: 2b, capture line often starts with 2b8h...
    has_sente_bx = any(m.startswith("8h2b") for m in moves)
    has_gote_bx = any(m.startswith("2b8h") for m in moves)
    if (has_sente_bx or has_gote_bx):
        # Only call it 角換わり when the rook stayed on its home file (typical signal).
        if (side == "b" and rf == 2) or (side == "w" and rf == 8):
            reasons: List[str] = []
            if has_sente_bx:
                reasons.append("序盤に 8h2b...（先手角の突入/角交換） が見える")
            if has_gote_bx:
                reasons.append("序盤に 2b8h...（後手角の突入/角交換） が見える")
            reasons.append(f"飛車が居飛車位置（{rf}筋）にある → 角換わり系の可能性が高い")
            return Detected(
                id="kaku-gawari",
                nameJa="角換わり",
                confidence=0.8 if (has_sente_bx and has_gote_bx) else 0.65,
                reasons=reasons,
            )

    # 2) Furibisha subtypes based on rook file (most reliable signal for beginners).
    if side == "b":
        if rf == 6:
            return Detected("shikenbisha", "四間飛車", 0.85, [f"飛車が6筋にいる（2h→6h 等） → 四間飛車"])
        if rf == 7:
            return Detected("sankenbisha", "三間飛車", 0.85, [f"飛車が7筋にいる（2h→7h 等） → 三間飛車"])
        if rf == 5:
            return Detected("nakabisha", "中飛車", 0.8, [f"飛車が5筋にいる → 中飛車"])
        if rf == 8:
            return Detected("mukai-bisha", "向かい飛車", 0.8, [f"飛車が8筋にいる → 向かい飛車"])
    else:
        # gote mapping (mirror of sente)
        if rf == 4:
            return Detected("shikenbisha", "四間飛車", 0.85, [f"飛車が4筋にいる（8b→4b 等） → 四間飛車"])
        if rf == 3:
            return Detected("sankenbisha", "三間飛車", 0.85, [f"飛車が3筋にいる → 三間飛車"])
        if rf == 5:
            return Detected("nakabisha", "中飛車", 0.8, [f"飛車が5筋にいる → 中飛車"])
        if rf == 2:
            return Detected("mukai-bisha", "向かい飛車", 0.8, [f"飛車が2筋にいる → 向かい飛車"])

    return _unknown("戦法")


def detect_opening_bundle(board: List[List[Optional[str]]], moves: List[str], side: str) -> Dict[str, Any]:
    style = detect_style(board, side)
    opening = detect_opening(board, moves, side)
    return {"style": style.to_dict(), "opening": opening.to_dict()}


