"""ML学習用の局面特徴量抽出パイプライン.

入力: SFEN文字列（局面）+ USI手順 + エンジン評価値
出力: 特徴量辞書
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from backend.api.utils.shogi_explain_core import (
    PIECE_VALUE,
    apply_usi_move,
    attacked_squares,
    attacks_from_piece,
    find_king,
    parse_position_cmd,
    piece_kind_upper,
    piece_side,
)

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------
_KING_SURROUND_DELTAS = [
    (-1, -1), (0, -1), (1, -1),
    (-1, 0),           (1, 0),
    (-1, 1),  (0, 1),  (1, 1),
]

_GOLD_SILVER_KINDS = {"G", "S", "+P", "+L", "+N", "+S"}

# 駒打ちの持ち駒価値合計に使う
_HAND_VALUES = {"P": 1, "L": 3, "N": 3, "S": 5, "G": 6, "B": 8, "R": 10}


# ---------------------------------------------------------------------------
# 1. king_safety: 玉の安全度 (0-100)
# ---------------------------------------------------------------------------
def _king_safety(
    board: List[List[Optional[str]]],
    side: str,
) -> int:
    """玉周囲の守備駒と金銀近接を評価して 0-100 を返す."""
    king_pos = find_king(board, side)
    if king_pos is None:
        return 0

    kx, ky = king_pos
    opp = "w" if side == "b" else "b"

    defend_count = 0
    gold_silver_adj = 0

    for dx, dy in _KING_SURROUND_DELTAS:
        nx, ny = kx + dx, ky + dy
        if not (0 <= nx < 9 and 0 <= ny < 9):
            # 壁も防御とみなす（端玉の壁効果）
            defend_count += 1
            continue
        p = board[ny][nx]
        if p is None:
            continue
        if piece_side(p) == side:
            defend_count += 1
            kind = piece_kind_upper(p)
            if kind in _GOLD_SILVER_KINDS:
                gold_silver_adj += 1

    # 敵の利きが玉周囲にどれだけあるか
    opp_attacks = attacked_squares(board, opp)
    threat_count = 0
    for dx, dy in _KING_SURROUND_DELTAS:
        nx, ny = kx + dx, ky + dy
        if (nx, ny) in opp_attacks:
            threat_count += 1
    # 玉自身への直接攻撃
    if (kx, ky) in opp_attacks:
        threat_count += 2

    # スコア: 守備(最大8) + 金銀ボーナス(最大3) - 脅威(最大10)
    raw = defend_count * 6 + gold_silver_adj * 8 - threat_count * 8
    return max(0, min(100, raw))


# ---------------------------------------------------------------------------
# 2. piece_activity: 駒の活用度 (0-100)
# ---------------------------------------------------------------------------
def _count_hand_value(board: List[List[Optional[str]]], side: str) -> int:
    """盤上の味方駒の合計価値（玉を除く）."""
    total = 0
    for y in range(9):
        for x in range(9):
            p = board[y][x]
            if p and piece_side(p) == side:
                kind = piece_kind_upper(p)
                if kind != "K":
                    total += PIECE_VALUE.get(kind, 0)

    return total


def _piece_activity(
    board: List[List[Optional[str]]],
    side: str,
) -> int:
    """大駒の利き範囲 + 成り駒数 + 盤上駒価値を評価して 0-100 を返す."""
    big_reach = len(attacked_squares(board, side, only_big=True))

    promoted_count = 0
    for y in range(9):
        for x in range(9):
            p = board[y][x]
            if p and piece_side(p) == side and p.startswith("+"):
                promoted_count += 1

    board_value = _count_hand_value(board, side)

    # 大駒利き: 最大30マス程度想定 → 0-40点
    # 成り駒: 最大5個程度 → 0-25点
    # 盤上駒価値: 最大65程度 → 0-35点
    reach_score = min(40, big_reach * 2)
    promo_score = min(25, promoted_count * 5)
    value_score = min(35, int(board_value * 0.55))

    return max(0, min(100, reach_score + promo_score + value_score))


# ---------------------------------------------------------------------------
# 3. attack_pressure: 攻撃圧力 (0-100)
# ---------------------------------------------------------------------------
def _attack_pressure(
    board: List[List[Optional[str]]],
    side: str,
) -> int:
    """相手玉近くへの脅威 + 敵陣への駒の侵入度を評価して 0-100 を返す."""
    opp = "w" if side == "b" else "b"
    opp_king = find_king(board, opp)

    my_attacks = attacked_squares(board, side)

    # (a) 相手玉周囲への利き数
    king_area_threats = 0
    if opp_king:
        okx, oky = opp_king
        for dx, dy in _KING_SURROUND_DELTAS:
            nx, ny = okx + dx, oky + dy
            if (nx, ny) in my_attacks:
                king_area_threats += 1
        if (okx, oky) in my_attacks:
            king_area_threats += 3  # 王手は大きい

    # (b) 敵陣にいる味方駒の数
    # 先手の敵陣=y 0-2, 後手の敵陣=y 6-8
    enemy_camp_start = 0 if side == "b" else 6
    enemy_camp_end = 3 if side == "b" else 9
    pieces_in_camp = 0
    for y in range(enemy_camp_start, enemy_camp_end):
        for x in range(9):
            p = board[y][x]
            if p and piece_side(p) == side:
                kind = piece_kind_upper(p)
                if kind != "K":
                    pieces_in_camp += 1

    # king_area_threats: 最大11 → 0-55点
    # pieces_in_camp: 最大10程度 → 0-45点
    threat_score = min(55, king_area_threats * 5)
    camp_score = min(45, pieces_in_camp * 9)

    return max(0, min(100, threat_score + camp_score))


# ---------------------------------------------------------------------------
# 4. phase: 局面フェーズ判定
# ---------------------------------------------------------------------------
def _detect_phase(
    board: List[List[Optional[str]]],
    ply: int,
) -> str:
    """序盤/中盤/終盤を手数 + 駒交換状況で判定."""
    # 盤上の駒数（双方合計、玉含む）
    piece_count = 0
    for y in range(9):
        for x in range(9):
            if board[y][x] is not None:
                piece_count += 1

    # 初期盤面は40駒 (双方20ずつ)
    # 駒が大量に減っていたら終盤寄り
    exchanged = 40 - piece_count  # 持ち駒になった数の近似

    if ply <= 30 and exchanged <= 4:
        return "opening"
    if ply > 100 or exchanged >= 15:
        return "endgame"
    if ply > 60 or exchanged >= 8:
        return "endgame" if piece_count <= 22 else "midgame"
    return "midgame"


# ---------------------------------------------------------------------------
# 5. move_intent: 手の意図分類
# ---------------------------------------------------------------------------
def _classify_move_intent(
    board_before: List[List[Optional[str]]],
    board_after: List[List[Optional[str]]],
    move: str,
    turn: str,
    captured: Optional[str],
) -> str:
    """attack / defense / development / exchange / sacrifice を返す."""
    opp = "w" if turn == "b" else "b"

    is_drop = "*" in move
    is_capture = captured is not None

    # 犠牲判定: 駒を取られる位置に自分の高価値駒を動かした
    if not is_drop and not is_capture:
        # 移動先に相手の利きがあるか
        dst = move[2:4]
        from backend.api.utils.shogi_explain_core import sq_to_xy
        dx, dy = sq_to_xy(dst)
        opp_attacks_after = attacked_squares(board_after, opp)
        moved_piece = board_after[dy][dx]
        if moved_piece and (dx, dy) in opp_attacks_after:
            moved_value = PIECE_VALUE.get(piece_kind_upper(moved_piece), 0)
            if moved_value >= 5:
                return "sacrifice"

    # 駒交換: 取った駒の価値と取られそうな駒の価値が同程度
    if is_capture:
        captured_val = PIECE_VALUE.get(piece_kind_upper(captured), 0)
        # 移動先に相手の利きがあれば exchange の可能性
        dst = move[2:4]
        from backend.api.utils.shogi_explain_core import sq_to_xy
        dx, dy = sq_to_xy(dst)
        opp_attacks_after = attacked_squares(board_after, opp)
        if (dx, dy) in opp_attacks_after:
            moving_piece = board_after[dy][dx]
            if moving_piece:
                my_val = PIECE_VALUE.get(piece_kind_upper(moving_piece), 0)
                if abs(my_val - captured_val) <= 2:
                    return "exchange"

    # 攻撃: 王手 or 相手玉周囲への利き増加
    opp_king = find_king(board_after, opp)
    if opp_king:
        my_attacks_after = attacked_squares(board_after, turn)
        if opp_king in my_attacks_after:
            return "attack"
        # 相手玉周囲への利き
        okx, oky = opp_king
        near_threats = 0
        for ddx, ddy in _KING_SURROUND_DELTAS:
            nx, ny = okx + ddx, oky + ddy
            if (nx, ny) in my_attacks_after:
                near_threats += 1
        if near_threats >= 3 or is_capture:
            return "attack"

    # 防御: 自玉周囲を固める動き
    my_king = find_king(board_after, turn)
    if my_king:
        mkx, mky = my_king
        if not is_drop:
            dst = move[2:4]
            from backend.api.utils.shogi_explain_core import sq_to_xy
            dx, dy = sq_to_xy(dst)
            dist = abs(dx - mkx) + abs(dy - mky)
            if dist <= 2:
                return "defense"
        else:
            # 打った駒が自玉の近くなら防御
            dp, ddst = move.split("*")
            from backend.api.utils.shogi_explain_core import sq_to_xy
            dx, dy = sq_to_xy(ddst)
            dist = abs(dx - mkx) + abs(dy - mky)
            if dist <= 2:
                return "defense"

    return "development"


# ---------------------------------------------------------------------------
# 6. tension_delta: 局面間の特徴量変化
# ---------------------------------------------------------------------------
def _tension_delta(
    features_before: Optional[Dict[str, Any]],
    features_after: Dict[str, Any],
) -> Dict[str, float]:
    """前局面と現局面の特徴量差分を返す."""
    if features_before is None:
        return {
            "d_king_safety": 0.0,
            "d_piece_activity": 0.0,
            "d_attack_pressure": 0.0,
        }
    return {
        "d_king_safety": float(
            features_after["king_safety"] - features_before["king_safety"]
        ),
        "d_piece_activity": float(
            features_after["piece_activity"] - features_before["piece_activity"]
        ),
        "d_attack_pressure": float(
            features_after["attack_pressure"] - features_before["attack_pressure"]
        ),
    }


# ---------------------------------------------------------------------------
# 公開API
# ---------------------------------------------------------------------------
def extract_position_features(
    sfen: str,
    move: Optional[str] = None,
    ply: int = 0,
    eval_info: Optional[Dict[str, Any]] = None,
    prev_features: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """局面の特徴量を抽出して辞書で返す.

    Parameters
    ----------
    sfen : str
        position コマンド文字列 (例: "position startpos moves 7g7f 3c3d")
    move : str, optional
        この局面で指した手 (USI形式)。None の場合は局面のみの特徴量。
    ply : int
        手数（0始まり）
    eval_info : dict, optional
        エンジン評価値 {"score_cp": int, "score_mate": int} など
    prev_features : dict, optional
        前局面の特徴量辞書 (tension_delta 計算用)

    Returns
    -------
    dict
        king_safety, piece_activity, attack_pressure, phase,
        move_intent, tension_delta を含む辞書
    """
    pos = parse_position_cmd(sfen)
    board = pos.board
    turn = pos.turn

    # 手番側の特徴を計算
    ks = _king_safety(board, turn)
    pa = _piece_activity(board, turn)
    ap = _attack_pressure(board, turn)
    phase = _detect_phase(board, ply)

    features: Dict[str, Any] = {
        "king_safety": ks,
        "piece_activity": pa,
        "attack_pressure": ap,
        "phase": phase,
        "turn": turn,
        "ply": ply,
    }

    # 手がある場合のみ intent と局面差分を計算
    if move:
        board_after, captured = apply_usi_move(board, move, turn)
        intent = _classify_move_intent(board, board_after, move, turn, captured)
        features["move_intent"] = intent

        # 手を指した後の特徴量
        next_turn = "w" if turn == "b" else "b"
        ks_after = _king_safety(board_after, next_turn)
        pa_after = _piece_activity(board_after, next_turn)
        ap_after = _attack_pressure(board_after, next_turn)

        after_features = {
            "king_safety": ks_after,
            "piece_activity": pa_after,
            "attack_pressure": ap_after,
        }
        features["tension_delta"] = _tension_delta(prev_features, features)
        features["after"] = after_features
    else:
        features["move_intent"] = None
        features["tension_delta"] = _tension_delta(prev_features, features)

    # エンジン評価値があれば付加
    if eval_info:
        features["score_cp"] = eval_info.get("score_cp")
        features["score_mate"] = eval_info.get("score_mate")

    return features
