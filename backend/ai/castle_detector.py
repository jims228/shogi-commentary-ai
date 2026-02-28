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


def _unknown() -> Detected:
    return Detected(id="unknown", nameJa="不明（囲い）", confidence=0.0, reasons=[])


def _positions(board: List[List[Optional[str]]], side: str, kinds: Tuple[str, ...]) -> List[Tuple[int, int]]:
    out: List[Tuple[int, int]] = []
    for y in range(9):
        for x in range(9):
            p = board[y][x]
            if not p:
                continue
            if piece_side(p) != side:
                continue
            ku = piece_kind_upper(p)
            if ku in kinds:
                file_, rank_ = xy_to_file_rank(x, y)
                out.append((file_, rank_))
    return out


def _find_king(board: List[List[Optional[str]]], side: str) -> Optional[Tuple[int, int]]:
    ks = _positions(board, side, ("K",))
    return ks[0] if ks else None


def detect_castle(board: List[List[Optional[str]]], side: str) -> Detected:
    """
    Detect castle shape for the side-to-move using coarse piece-location heuristics.
    Prefer unknown over false positives.
    """
    kpos = _find_king(board, side)
    if not kpos:
        return _unknown()
    kf, kr = kpos

    golds = _positions(board, side, ("G",))
    silvers = _positions(board, side, ("S", "+S"))

    # Side-specific home rank / corner direction
    if side == "b":
        home_rank = 9
        anaguma_zone = {(1, 9), (2, 9), (1, 8)}
        mino_king_zone = {(7, 9), (8, 9), (7, 8), (8, 8)}
        funagakoi_king_zone = {(6, 9), (7, 9), (6, 8)}
        yagura_king_zone = {(5, 9), (6, 9), (5, 8), (6, 8)}
    else:
        home_rank = 1
        anaguma_zone = {(9, 1), (8, 1), (9, 2)}
        mino_king_zone = {(3, 1), (2, 1), (3, 2), (2, 2)}
        funagakoi_king_zone = {(4, 1), (3, 1), (4, 2)}
        yagura_king_zone = {(5, 1), (4, 1), (5, 2), (4, 2)}

    # 1) Anaguma: king tucked into corner zone.
    if (kf, kr) in anaguma_zone:
        reasons = [f"玉が隅（{kf}{'一' if kr==1 else '九' if kr==9 else ''}付近）にいる → 穴熊形"]
        if golds:
            reasons.append("金が近くにある → 隅を固める配置")
        return Detected("anaguma", "穴熊", 0.8, reasons)

    # 2) Mino: king on mino side + at least one gold/silver supporting
    if (kf, kr) in mino_king_zone:
        support = [p for p in golds + silvers if abs(p[0] - kf) <= 2 and abs(p[1] - kr) <= 2]
        if len(support) >= 1:
            return Detected(
                "mino",
                "美濃囲い",
                0.75,
                [
                    f"玉が美濃側（{kf}筋{kr}段付近）に移動している",
                    "金銀が玉の近くに集まっている → 美濃形",
                ],
            )

    # 3) Funagakoi: king slightly shifted + two golds nearby on home ranks
    if (kf, kr) in funagakoi_king_zone:
        near_golds = [g for g in golds if abs(g[0] - kf) <= 2 and abs(g[1] - home_rank) <= 2]
        if len(near_golds) >= 1:
            return Detected(
                "funagakoi",
                "舟囲い",
                0.65,
                [
                    f"玉が舟囲い側（{kf}筋{kr}段付近）にいる",
                    "金が玉の前後に寄っている → 舟囲いの形",
                ],
            )

    # 4) Yagura: king remains central-ish on home side and gold/silver form a compact block.
    if (kf, kr) in yagura_king_zone:
        # Allow 3 ranks depth around home side (e.g. 7-9 for sente, 1-3 for gote) because early shapes vary.
        if side == "b":
            valid_ranks = {home_rank, home_rank - 1, home_rank - 2}
        else:
            valid_ranks = {home_rank, home_rank + 1, home_rank + 2}
        block = [p for p in golds + silvers if p[1] in valid_ranks and abs(p[0] - kf) <= 3]
        if len(block) >= 2:
            return Detected(
                "yagura",
                "矢倉",
                0.6,
                [
                    "玉が自陣中央付近に残っている",
                    "金銀が自陣で固まっている → 矢倉の形（目安）",
                ],
            )

    return _unknown()


def detect_castle_bundle(board: List[List[Optional[str]]], side: str) -> Dict[str, Any]:
    return {"castle": detect_castle(board, side).to_dict()}


