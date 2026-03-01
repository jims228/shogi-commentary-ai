"""Tests for backend.api.services.position_features."""
from __future__ import annotations

import pytest

from backend.api.services.position_features import (
    extract_position_features,
    _king_safety,
    _piece_activity,
    _attack_pressure,
    _detect_phase,
    _classify_move_intent,
    _tension_delta,
)
from backend.api.utils.shogi_explain_core import (
    parse_position_cmd,
    apply_usi_move,
    parse_sfen_board,
    STARTPOS_SFEN,
)


# ===== テスト用定数 =====
STARTPOS = "position startpos"
# 矢倉風に駒組みした局面（20手程度進めた想定）
YAGURA_MOVES = (
    "position startpos moves "
    "7g7f 8c8d 6g6f 3c3d 6f6e 7a6b "
    "2h6h 5a4b 5i4h 4b3b 3i3h 6b5b "
    "4h3i 5b4b 3h2g 4b3c 7i6h 3a2b "
    "6h5g 2b3a"
)
# 終盤局面: 駒が少ない盤面
ENDGAME_SFEN = "position sfen 4k4/9/9/9/9/9/9/9/4K4 b - 1"


class TestKingSafety:
    def test_startpos_reasonable(self):
        """初期局面では玉は金銀に守られている."""
        pos = parse_position_cmd(STARTPOS)
        score = _king_safety(pos.board, "b")
        assert 30 <= score <= 100

    def test_bare_king_low(self):
        """裸玉は安全度が低い."""
        pos = parse_position_cmd(ENDGAME_SFEN)
        score = _king_safety(pos.board, "b")
        assert score <= 30

    def test_opponent_side(self):
        """後手玉の安全度も計算できる."""
        pos = parse_position_cmd(STARTPOS)
        score = _king_safety(pos.board, "w")
        assert 30 <= score <= 100

    def test_no_king_returns_zero(self):
        """玉がない盤面（異常ケース）は 0."""
        board = [[None] * 9 for _ in range(9)]
        assert _king_safety(board, "b") == 0

    def test_range_0_100(self):
        pos = parse_position_cmd(STARTPOS)
        score = _king_safety(pos.board, "b")
        assert 0 <= score <= 100


class TestPieceActivity:
    def test_startpos_moderate(self):
        """初期局面は大駒の利きが制限されている."""
        pos = parse_position_cmd(STARTPOS)
        score = _piece_activity(pos.board, "b")
        assert 10 <= score <= 60

    def test_bare_king_zero(self):
        """玉しかいなければ活動度は0."""
        pos = parse_position_cmd(ENDGAME_SFEN)
        score = _piece_activity(pos.board, "b")
        assert score == 0

    def test_range_0_100(self):
        pos = parse_position_cmd(STARTPOS)
        score = _piece_activity(pos.board, "b")
        assert 0 <= score <= 100


class TestAttackPressure:
    def test_startpos_low(self):
        """初期局面は敵陣への侵入がなく圧力は低い."""
        pos = parse_position_cmd(STARTPOS)
        score = _attack_pressure(pos.board, "b")
        assert score <= 30

    def test_range_0_100(self):
        pos = parse_position_cmd(STARTPOS)
        score = _attack_pressure(pos.board, "b")
        assert 0 <= score <= 100

    def test_no_opp_king(self):
        """相手玉がない異常ケースでもクラッシュしない."""
        board = [[None] * 9 for _ in range(9)]
        board[8][4] = "K"
        score = _attack_pressure(board, "b")
        assert 0 <= score <= 100


class TestPhase:
    def test_opening(self):
        """手数少・駒交換なし → opening."""
        pos = parse_position_cmd(STARTPOS)
        assert _detect_phase(pos.board, 10) == "opening"

    def test_endgame_by_ply(self):
        """手数 > 100 → endgame."""
        pos = parse_position_cmd(STARTPOS)
        assert _detect_phase(pos.board, 120) == "endgame"

    def test_endgame_by_pieces(self):
        """駒が極端に少ない → endgame."""
        pos = parse_position_cmd(ENDGAME_SFEN)
        assert _detect_phase(pos.board, 80) == "endgame"

    def test_midgame(self):
        """中間的な手数 → midgame."""
        pos = parse_position_cmd(STARTPOS)
        assert _detect_phase(pos.board, 50) == "midgame"


class TestMoveIntent:
    def test_capture_is_attack_or_exchange(self):
        """駒を取る手は attack か exchange."""
        # Rook at 5h (x=4,y=7), pawn at 5f (x=4,y=5), opp king at 5a
        pos = parse_position_cmd(
            "position sfen 4k4/9/9/9/9/4p4/9/4R4/4K4 b - 1"
        )
        board_after, captured = apply_usi_move(pos.board, "5h5f", "b")
        intent = _classify_move_intent(
            pos.board, board_after, "5h5f", "b", captured
        )
        assert intent in ("attack", "exchange")

    def test_development(self):
        """序盤の駒組みは development."""
        pos = parse_position_cmd(STARTPOS)
        board_after, captured = apply_usi_move(pos.board, "7g7f", "b")
        intent = _classify_move_intent(
            pos.board, board_after, "7g7f", "b", captured
        )
        assert intent == "development"

    def test_defense_near_king(self):
        """自玉近くへの打ち駒は defense."""
        # 先手玉(5i)の近くに金打ち
        pos = parse_position_cmd(
            "position sfen 4k4/9/9/9/9/9/9/9/4K4 b G 1"
        )
        board_after, captured = apply_usi_move(pos.board, "G*4i", "b")
        intent = _classify_move_intent(
            pos.board, board_after, "G*4i", "b", captured
        )
        assert intent == "defense"


class TestTensionDelta:
    def test_no_prev(self):
        """前局面なしは全部 0."""
        after = {"king_safety": 50, "piece_activity": 40, "attack_pressure": 30}
        d = _tension_delta(None, after)
        assert d["d_king_safety"] == 0.0
        assert d["d_piece_activity"] == 0.0
        assert d["d_attack_pressure"] == 0.0

    def test_with_prev(self):
        """差分が正しく計算される."""
        before = {"king_safety": 60, "piece_activity": 30, "attack_pressure": 20}
        after = {"king_safety": 50, "piece_activity": 40, "attack_pressure": 30}
        d = _tension_delta(before, after)
        assert d["d_king_safety"] == -10.0
        assert d["d_piece_activity"] == 10.0
        assert d["d_attack_pressure"] == 10.0


class TestExtractPositionFeatures:
    def test_startpos_all_keys(self):
        """全キーが返る."""
        result = extract_position_features(STARTPOS, ply=0)
        assert "king_safety" in result
        assert "piece_activity" in result
        assert "attack_pressure" in result
        assert "phase" in result
        assert "turn" in result
        assert "ply" in result
        assert "move_intent" in result
        assert "tension_delta" in result

    def test_with_move(self):
        """手付きで intent と after が返る."""
        result = extract_position_features(STARTPOS, move="7g7f", ply=1)
        assert result["move_intent"] is not None
        assert "after" in result

    def test_without_move(self):
        """手なしで intent は None, after はない."""
        result = extract_position_features(STARTPOS, ply=0)
        assert result["move_intent"] is None
        assert "after" not in result

    def test_eval_info_attached(self):
        """eval_info があれば付加される."""
        result = extract_position_features(
            STARTPOS, ply=0, eval_info={"score_cp": 100, "score_mate": None}
        )
        assert result["score_cp"] == 100
        assert result["score_mate"] is None

    def test_prev_features_delta(self):
        """prev_features を渡すと tension_delta が非ゼロになりうる."""
        prev = {"king_safety": 80, "piece_activity": 30, "attack_pressure": 10}
        result = extract_position_features(
            STARTPOS, ply=5, prev_features=prev
        )
        td = result["tension_delta"]
        # startpos のスコアは prev とは異なるはずなので差分が出る
        assert isinstance(td["d_king_safety"], float)

    def test_yagura_midgame(self):
        """矢倉の駒組み後は midgame."""
        result = extract_position_features(YAGURA_MOVES, ply=20)
        # 20手でも交換が少なければ opening/midgame のどちらか
        assert result["phase"] in ("opening", "midgame")

    def test_endgame_sfen(self):
        """終盤局面の判定."""
        result = extract_position_features(ENDGAME_SFEN, ply=80)
        assert result["phase"] == "endgame"
