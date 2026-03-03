"""盤面構造化データ抽出サービス.

局面から「解説に使える構造化データ」を抽出する。
shogi_explain_core.py の既存関数を最大限活用し、
position_features.py では返していない情報を提供する。

Usage::

    from backend.api.services.board_analyzer import BoardAnalyzer

    analyzer = BoardAnalyzer()
    result = analyzer.analyze("position startpos moves 7g7f 3c3d")
    print(result.commentary_hints)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.api.utils.shogi_explain_core import (
    PIECE_JP,
    PIECE_VALUE,
    apply_usi_move,
    attacked_squares,
    attacks_from_piece,
    board_clone,
    find_king,
    parse_position_cmd,
    piece_kind_upper,
    piece_side,
    sq_to_xy,
    xy_to_file_rank,
)

# ---------------------------------------------------------------------------
# Coordinate helpers
# ---------------------------------------------------------------------------

def _xy_to_sq(x: int, y: int) -> str:
    """内部座標 (x, y) を USI 表記 "7g" に変換."""
    return str(9 - x) + chr(ord("a") + y)


_KING_SURROUND_DELTAS = [
    (-1, -1), (0, -1), (1, -1),
    (-1, 0),           (1, 0),
    (-1, 1),  (0, 1),  (1, 1),
]

# 駒種 → 日本語名 (PIECE_JP の参照用ショートカット)
_JP = PIECE_JP


# ---------------------------------------------------------------------------
# Castle patterns
# ---------------------------------------------------------------------------

def _estimate_castle(
    board: List[List[Optional[str]]], side: str,
) -> str:
    """玉と金銀の配置パターンから囲いを推定する.

    完全な正確性ではなく、解説ヒントとして使えるレベル。
    """
    king_pos = find_king(board, side)
    if king_pos is None:
        return "不明"

    kx, ky = king_pos

    # 周囲の金銀を収集
    gs_positions: List[Tuple[int, int, str]] = []  # (x, y, kind)
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            nx, ny = kx + dx, ky + dy
            if not (0 <= nx < 9 and 0 <= ny < 9):
                continue
            p = board[ny][nx]
            if p and piece_side(p) == side:
                k = piece_kind_upper(p)
                if k in ("G", "S", "+P", "+L", "+N", "+S"):
                    gs_positions.append((nx, ny, k))

    gs_set = {(gx, gy) for gx, gy, _ in gs_positions}
    gs_count = len(gs_positions)

    if side == "b":
        # 先手: 玉が左寄り (x >= 5, つまり筋 1-4) = 居飛車系, 右寄り = 振り飛車系
        # 穴熊: 玉が9i (x=0, y=8) or 1i (x=8, y=8)
        if kx == 0 and ky == 8:
            # 先手 9九 = 穴熊の可能性
            if gs_count >= 2:
                return "穴熊"
        if kx == 8 and ky == 8:
            # 先手 1九 = 居飛車穴熊
            if gs_count >= 2:
                return "穴熊"
        # 矢倉: 玉が 7h-8h (x=1-2, y=7) 付近で金銀が上部
        if ky == 7 and 1 <= kx <= 2:
            upper_gs = sum(1 for gx, gy, _ in gs_positions if gy <= 7)
            if upper_gs >= 3:
                return "矢倉"
        # 美濃: 玉が 8h-9h (x=0-1, y=7) で金銀が近い
        if ky == 7 and 0 <= kx <= 1:
            if gs_count >= 2:
                return "美濃囲い"
        # 船囲い: 玉が 6h-7h (x=2-3, y=7) 基本的な金守り
        if ky == 7 and 2 <= kx <= 3:
            if gs_count >= 1:
                return "船囲い"
        # 居玉
        if kx == 4 and ky == 8:
            return "居玉"
    else:
        # 後手: 座標を反転して考える
        # 穴熊
        if kx == 8 and ky == 0:
            if gs_count >= 2:
                return "穴熊"
        if kx == 0 and ky == 0:
            if gs_count >= 2:
                return "穴熊"
        # 矢倉
        if ky == 1 and 6 <= kx <= 7:
            upper_gs = sum(1 for gx, gy, _ in gs_positions if gy >= 1)
            if upper_gs >= 3:
                return "矢倉"
        # 美濃
        if ky == 1 and 7 <= kx <= 8:
            if gs_count >= 2:
                return "美濃囲い"
        # 船囲い
        if ky == 1 and 5 <= kx <= 6:
            if gs_count >= 1:
                return "船囲い"
        # 居玉
        if kx == 4 and ky == 0:
            return "居玉"

    if gs_count == 0:
        return "裸玉"

    return "その他"


# ---------------------------------------------------------------------------
# DataClass
# ---------------------------------------------------------------------------

@dataclass
class BoardAnalysis:
    """盤面の構造化分析結果."""

    piece_placement: Dict[str, Any] = field(default_factory=dict)
    contested_squares: List[str] = field(default_factory=list)
    hanging_pieces: List[Dict[str, str]] = field(default_factory=list)
    king_safety_detail: Dict[str, Any] = field(default_factory=dict)
    threats: List[Dict[str, Any]] = field(default_factory=list)
    move_impact: Optional[Dict[str, Any]] = None
    commentary_hints: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------

class BoardAnalyzer:
    """局面から解説用の構造化データを抽出する."""

    def analyze(
        self,
        position_cmd: str,
        move: Optional[str] = None,
        ply: int = 0,
    ) -> BoardAnalysis:
        """局面を分析して BoardAnalysis を返す.

        Parameters
        ----------
        position_cmd : str
            USI position コマンド (例: "position startpos moves 7g7f")
        move : str, optional
            この局面で指した手 (USI形式)。指定すると move_impact を計算。
        ply : int
            手数
        """
        pos = parse_position_cmd(position_cmd)
        board = pos.board
        turn = pos.turn

        placement = self._extract_placement(board)
        contested = self._find_contested_squares(board)
        hanging = self._find_hanging_pieces(board)
        king_detail = self._analyze_king_safety(board)
        threats = self._detect_threats(board, turn)

        impact: Optional[Dict[str, Any]] = None
        if move:
            # move は「前の手番」の手なので、手番を反転して計算
            prev_turn = "w" if turn == "b" else "b"
            # move を指す前の盤面を構築するため、position_cmd を再パース
            # ただし parse_position_cmd は既に全 moves 適用済みなので、
            # 1手巻き戻す代わりに「moves の最後を除いた状態」で再パースする
            impact = self._analyze_move_impact(board, move, prev_turn, position_cmd)

        hints = self._generate_hints(
            board, turn, placement, hanging, king_detail, threats, impact, ply
        )

        return BoardAnalysis(
            piece_placement=placement,
            contested_squares=contested,
            hanging_pieces=hanging,
            king_safety_detail=king_detail,
            threats=threats,
            move_impact=impact,
            commentary_hints=hints,
        )

    # ------------------------------------------------------------------
    # 1. Piece placement
    # ------------------------------------------------------------------
    def _extract_placement(
        self, board: List[List[Optional[str]]],
    ) -> Dict[str, Any]:
        sente: Dict[str, List[str]] = {}
        gote: Dict[str, List[str]] = {}

        for y in range(9):
            for x in range(9):
                p = board[y][x]
                if p is None:
                    continue
                side = piece_side(p)
                kind = piece_kind_upper(p)
                jp_name = _JP.get(kind, kind)
                sq = _xy_to_sq(x, y)
                target = sente if side == "b" else gote
                target.setdefault(jp_name, []).append(sq)

        return {"sente": sente, "gote": gote}

    # ------------------------------------------------------------------
    # 2. Contested squares
    # ------------------------------------------------------------------
    def _find_contested_squares(
        self, board: List[List[Optional[str]]],
    ) -> List[str]:
        sente_att = attacked_squares(board, "b")
        gote_att = attacked_squares(board, "w")
        contested = sente_att & gote_att
        return sorted(_xy_to_sq(x, y) for x, y in contested)

    # ------------------------------------------------------------------
    # 3. Hanging pieces
    # ------------------------------------------------------------------
    def _find_hanging_pieces(
        self, board: List[List[Optional[str]]],
    ) -> List[Dict[str, str]]:
        sente_att = attacked_squares(board, "b")
        gote_att = attacked_squares(board, "w")
        result: List[Dict[str, str]] = []

        for y in range(9):
            for x in range(9):
                p = board[y][x]
                if p is None:
                    continue
                side = piece_side(p)
                kind = piece_kind_upper(p)
                if kind == "K":
                    continue  # 玉は浮き駒とは言わない

                # 味方の利きで守られているか
                friendly_att = sente_att if side == "b" else gote_att
                enemy_att = gote_att if side == "b" else sente_att

                is_defended = (x, y) in friendly_att
                is_attacked = (x, y) in enemy_att

                if is_attacked and not is_defended:
                    result.append({
                        "square": _xy_to_sq(x, y),
                        "piece": _JP.get(kind, kind),
                        "piece_kind": kind,
                        "side": "sente" if side == "b" else "gote",
                        "value": PIECE_VALUE.get(kind, 0),
                    })

        # 価値の高い順にソート
        result.sort(key=lambda h: -h.get("value", 0))
        return result

    # ------------------------------------------------------------------
    # 4. King safety detail
    # ------------------------------------------------------------------
    def _analyze_king_safety_one(
        self,
        board: List[List[Optional[str]]],
        side: str,
    ) -> Dict[str, Any]:
        king_pos = find_king(board, side)
        if king_pos is None:
            return {"king_pos": None, "adjacent_defenders": 0,
                    "adjacent_attackers": 0, "escape_squares": 0,
                    "castle_type": "不明"}

        kx, ky = king_pos
        opp = "w" if side == "b" else "b"
        opp_attacks = attacked_squares(board, opp)
        my_attacks = attacked_squares(board, side)

        adj_defenders = 0
        adj_attackers = 0
        escape_count = 0

        for dx, dy in _KING_SURROUND_DELTAS:
            nx, ny = kx + dx, ky + dy
            if not (0 <= nx < 9 and 0 <= ny < 9):
                continue

            is_opp_attacked = (nx, ny) in opp_attacks

            if is_opp_attacked:
                adj_attackers += 1

            sq_piece = board[ny][nx]
            if sq_piece and piece_side(sq_piece) == side:
                adj_defenders += 1
            elif sq_piece is None or piece_side(sq_piece) != side:
                # 空きマスまたは敵駒 → 逃げられるか
                if not is_opp_attacked:
                    # 味方駒がいないかチェック
                    if sq_piece is None:
                        escape_count += 1

        castle = _estimate_castle(board, side)

        return {
            "king_pos": _xy_to_sq(kx, ky),
            "adjacent_defenders": adj_defenders,
            "adjacent_attackers": adj_attackers,
            "escape_squares": escape_count,
            "castle_type": castle,
        }

    def _analyze_king_safety(
        self, board: List[List[Optional[str]]],
    ) -> Dict[str, Any]:
        return {
            "sente": self._analyze_king_safety_one(board, "b"),
            "gote": self._analyze_king_safety_one(board, "w"),
        }

    # ------------------------------------------------------------------
    # 5. Threats
    # ------------------------------------------------------------------
    def _detect_threats(
        self,
        board: List[List[Optional[str]]],
        turn: str,
    ) -> List[Dict[str, Any]]:
        """両者の脅威を検出する."""
        threats: List[Dict[str, Any]] = []

        for side in ("b", "w"):
            opp = "w" if side == "b" else "b"
            side_label = "sente" if side == "b" else "gote"

            # (a) 王手判定: side の駒が opp の玉を攻撃しているか
            opp_king = find_king(board, opp)
            if opp_king:
                for y in range(9):
                    for x in range(9):
                        p = board[y][x]
                        if p and piece_side(p) == side:
                            att = attacks_from_piece(board, x, y, p)
                            if opp_king in att:
                                threats.append({
                                    "type": "check",
                                    "by": _JP.get(piece_kind_upper(p), piece_kind_upper(p)),
                                    "from": _xy_to_sq(x, y),
                                    "to": _xy_to_sq(*opp_king),
                                    "side": side_label,
                                })

            # (b) 浮き駒への攻撃（hanging は既に計算済みだが、
            #     ここでは「どの駒が攻撃しているか」も特定する）
            for y in range(9):
                for x in range(9):
                    target = board[y][x]
                    if not target:
                        continue
                    if piece_side(target) != opp:
                        continue
                    target_kind = piece_kind_upper(target)
                    if target_kind == "K":
                        continue
                    target_val = PIECE_VALUE.get(target_kind, 0)
                    if target_val < 5:
                        continue  # 低価値駒は省略

                    # 守られていないかチェック
                    opp_defenses = attacked_squares(board, opp)
                    if (x, y) in opp_defenses:
                        continue

                    # side の駒で攻撃しているものを見つける
                    for ay in range(9):
                        for ax in range(9):
                            ap = board[ay][ax]
                            if ap and piece_side(ap) == side:
                                att = attacks_from_piece(board, ax, ay, ap)
                                if (x, y) in att:
                                    threats.append({
                                        "type": "hanging",
                                        "target": _JP.get(target_kind, target_kind),
                                        "at": _xy_to_sq(x, y),
                                        "attacker": _JP.get(
                                            piece_kind_upper(ap), piece_kind_upper(ap)
                                        ),
                                        "attacker_sq": _xy_to_sq(ax, ay),
                                        "side": side_label,
                                    })
                                    break  # 1つ見つかれば十分
                        else:
                            continue
                        break

            # (c) 桂馬の両取りポテンシャル
            for y in range(9):
                for x in range(9):
                    p = board[y][x]
                    if not p or piece_side(p) != side:
                        continue
                    if piece_kind_upper(p) != "N":
                        continue
                    att = attacks_from_piece(board, x, y, p)
                    valuable_targets = []
                    for ax, ay in att:
                        tp = board[ay][ax]
                        if tp and piece_side(tp) == opp:
                            tk = piece_kind_upper(tp)
                            if PIECE_VALUE.get(tk, 0) >= 5:
                                valuable_targets.append(_xy_to_sq(ax, ay))
                    if len(valuable_targets) >= 2:
                        threats.append({
                            "type": "fork_potential",
                            "piece": "桂",
                            "at": _xy_to_sq(x, y),
                            "targets": valuable_targets[:3],
                            "side": side_label,
                        })

        return threats

    # ------------------------------------------------------------------
    # 6. Move impact
    # ------------------------------------------------------------------
    def _analyze_move_impact(
        self,
        board_after: List[List[Optional[str]]],
        move: str,
        move_turn: str,
        position_cmd: str,
    ) -> Dict[str, Any]:
        """手の影響を分析する.

        board_after は move 適用後の盤面。
        move 前の盤面を復元して比較する。
        """
        # move 適用前の盤面を再構築
        # position_cmd の最後の moves から最後の1手を除いて再パース
        cmd = position_cmd.strip()
        if cmd.startswith("position"):
            cmd_inner = cmd[len("position"):].strip()
        else:
            cmd_inner = cmd

        board_before: Optional[List[List[Optional[str]]]] = None
        if "moves" in cmd_inner:
            parts = cmd_inner.rsplit(None, 1)
            if len(parts) >= 2 and parts[1] == move:
                # 最後の手を除去
                before_cmd = cmd_inner.rsplit(None, 1)[0].strip()
                if before_cmd.endswith("moves"):
                    before_cmd = before_cmd[:-5].strip()
                pos_before = parse_position_cmd(before_cmd)
                board_before = pos_before.board

        if board_before is None:
            # フォールバック: move を逆適用できないので影響分析をスキップ
            return self._basic_move_info(move, move_turn, board_after)

        # 利きの比較
        my_attacks_before = attacked_squares(board_before, move_turn)
        my_attacks_after = attacked_squares(board_after, move_turn)
        new_attacks = my_attacks_after - my_attacks_before
        lost_attacks = my_attacks_before - my_attacks_after

        # 守りの変化（味方の駒が守っていたマス）
        opp = "w" if move_turn == "b" else "b"

        # 取った駒
        captured: Optional[str] = None
        is_drop = "*" in move
        from_sq: Optional[str] = None
        to_sq: str

        if is_drop:
            p_char, dst = move.split("*")
            to_sq = dst
            moved_piece = p_char.upper()
        else:
            from_sq = move[:2]
            to_sq = move[2:4]
            fx, fy = sq_to_xy(from_sq)
            piece_on_before = board_before[fy][fx]
            moved_piece = piece_kind_upper(piece_on_before) if piece_on_before else "?"
            tx, ty = sq_to_xy(to_sq)
            cap = board_before[ty][tx]
            if cap and piece_side(cap) != move_turn:
                captured = _JP.get(piece_kind_upper(cap), piece_kind_upper(cap))

        # 筋が通ったか（大駒の利き増加）
        big_before = attacked_squares(board_before, move_turn, only_big=True)
        big_after = attacked_squares(board_after, move_turn, only_big=True)
        opened_lines = len(big_after) - len(big_before) >= 2

        return {
            "moved_piece": _JP.get(moved_piece, moved_piece),
            "from_sq": from_sq,
            "to_sq": to_sq,
            "captured": captured,
            "is_drop": is_drop,
            "is_promotion": move.endswith("+"),
            "new_attacks": sorted(_xy_to_sq(x, y) for x, y in list(new_attacks)[:10]),
            "lost_defenses": sorted(_xy_to_sq(x, y) for x, y in list(lost_attacks)[:10]),
            "opened_lines": opened_lines,
        }

    def _basic_move_info(
        self, move: str, turn: str, board_after: List[List[Optional[str]]],
    ) -> Dict[str, Any]:
        """盤面復元できない場合の最低限の手情報."""
        is_drop = "*" in move
        if is_drop:
            p_char, dst = move.split("*")
            return {
                "moved_piece": _JP.get(p_char.upper(), p_char.upper()),
                "from_sq": None,
                "to_sq": dst,
                "captured": None,
                "is_drop": True,
                "is_promotion": False,
                "new_attacks": [],
                "lost_defenses": [],
                "opened_lines": False,
            }
        return {
            "moved_piece": "?",
            "from_sq": move[:2],
            "to_sq": move[2:4],
            "captured": None,
            "is_drop": False,
            "is_promotion": move.endswith("+"),
            "new_attacks": [],
            "lost_defenses": [],
            "opened_lines": False,
        }

    # ------------------------------------------------------------------
    # 7. Commentary hints
    # ------------------------------------------------------------------
    def _generate_hints(
        self,
        board: List[List[Optional[str]]],
        turn: str,
        placement: Dict[str, Any],
        hanging: List[Dict[str, str]],
        king_detail: Dict[str, Any],
        threats: List[Dict[str, Any]],
        impact: Optional[Dict[str, Any]],
        ply: int,
    ) -> List[str]:
        hints: List[str] = []
        sente_side = "先手" if turn == "b" else "後手"
        gote_side = "後手" if turn == "b" else "先手"

        # 手番側の玉の安全度
        turn_king = king_detail.get("sente" if turn == "b" else "gote", {})
        opp_king = king_detail.get("gote" if turn == "b" else "sente", {})

        # 囲いの状態
        my_castle = turn_king.get("castle_type", "不明")
        opp_castle = opp_king.get("castle_type", "不明")
        if my_castle not in ("不明", "その他", "裸玉"):
            hints.append(f"{sente_side}の玉は{my_castle}で構えている")
        if opp_castle not in ("不明", "その他", "裸玉"):
            hints.append(f"{gote_side}の玉は{opp_castle}で構えている")

        # 裸玉・居玉の警告（序盤は居玉が普通なので省略）
        if my_castle == "裸玉" and ply > 20:
            hints.append(f"{sente_side}の玉の周りに守り駒がなく非常に危険")
        elif my_castle == "居玉" and ply > 30:
            hints.append(f"{sente_side}は居玉のまま。囲いを組む余裕がない展開")
        if opp_castle == "裸玉" and ply > 20:
            hints.append(f"{gote_side}の玉の周りに守り駒がなく攻めやすい")

        # 逃げ道
        my_escape = turn_king.get("escape_squares", 0)
        if my_escape == 0 and ply > 20:
            king_pos = turn_king.get("king_pos", "")
            hints.append(f"{sente_side}の玉({king_pos})に逃げ道がない")
        opp_escape = opp_king.get("escape_squares", 0)
        if opp_escape == 0 and ply > 20:
            king_pos = opp_king.get("king_pos", "")
            hints.append(f"{gote_side}の玉({king_pos})に逃げ道がない。寄せのチャンス")

        # 浮き駒
        for h in hanging[:3]:
            side_jp = "先手" if h["side"] == "sente" else "後手"
            hints.append(
                f"{h['square']}の{side_jp}{h['piece']}が浮いている（守りの利きがない）"
            )

        # 王手
        checks = [t for t in threats if t["type"] == "check"]
        for c in checks[:2]:
            side_jp = "先手" if c["side"] == "sente" else "後手"
            hints.append(
                f"{side_jp}の{c['by']}({c['from']})が{c['to']}の玉に王手をかけている"
            )

        # 浮き駒への攻撃脅威
        hanging_threats = [t for t in threats if t["type"] == "hanging"]
        for t in hanging_threats[:2]:
            side_jp = "先手" if t["side"] == "sente" else "後手"
            hints.append(
                f"{side_jp}の{t['attacker']}が{t['at']}の{t['target']}を狙っている（取れる状態）"
            )

        # 両取り
        forks = [t for t in threats if t["type"] == "fork_potential"]
        for f in forks[:1]:
            side_jp = "先手" if f["side"] == "sente" else "後手"
            targets_str = "と".join(f["targets"])
            hints.append(f"{side_jp}の{f['piece']}({f['at']})が{targets_str}を同時に狙える形")

        # 手の影響
        if impact:
            mp = impact.get("moved_piece", "?")
            if impact.get("captured"):
                hints.append(f"{mp}で{impact['captured']}を取った")
            if impact.get("is_promotion"):
                hints.append(f"{mp}が成って戦力が増した")
            if impact.get("opened_lines"):
                hints.append("大駒の筋が通り、攻めの幅が広がった")
            new_att = impact.get("new_attacks", [])
            if len(new_att) >= 3:
                hints.append(f"この手で{len(new_att)}マスに新たに利きが通った")

        # ヒントが少なければ汎用的な情報を追加
        if len(hints) < 2:
            if ply <= 30:
                hints.append("序盤の駒組み段階。囲いの完成と大駒の活用がポイント")
            elif ply <= 80:
                hints.append("中盤の攻防。駒の働きと玉の安全のバランスが重要")
            else:
                hints.append("終盤の寄せ合い。速度計算と正確な読みが求められる")

        return hints
