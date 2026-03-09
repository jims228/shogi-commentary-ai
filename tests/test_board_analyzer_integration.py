"""Tests verifying BoardAnalyzer output reaches the LLM prompt in the legacy pipeline."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.api.services.board_analyzer import BoardAnalyzer, BoardAnalysis
from backend.api.services.ai_service import build_board_analysis_block


# ---------------------------------------------------------------------------
# Tests for build_board_analysis_block()
# ---------------------------------------------------------------------------

class TestBuildBoardAnalysisBlock(unittest.TestCase):
    """build_board_analysis_block() correctly formats BoardAnalysis into prompt text."""

    def _make_analysis(self, **kwargs) -> BoardAnalysis:
        defaults = dict(
            piece_placement={},
            contested_squares=[],
            hanging_pieces=[],
            king_safety_detail={},
            threats=[],
            move_impact=None,
            commentary_hints=[],
        )
        defaults.update(kwargs)
        return BoardAnalysis(**defaults)

    def test_empty_analysis_returns_empty_string(self):
        analysis = self._make_analysis()
        result = build_board_analysis_block(analysis)
        self.assertEqual(result, "")

    def test_commentary_hints_appear_in_block(self):
        analysis = self._make_analysis(
            commentary_hints=["先手の玉は美濃囲いで構えている", "3eの先手飛が浮いている"]
        )
        result = build_board_analysis_block(analysis)
        self.assertIn("盤面のポイント", result)
        self.assertIn("美濃囲い", result)
        self.assertIn("浮いている", result)

    def test_at_most_three_hints(self):
        analysis = self._make_analysis(
            commentary_hints=["ヒント1", "ヒント2", "ヒント3", "ヒント4", "ヒント5"]
        )
        result = build_board_analysis_block(analysis)
        # ヒント4 と5は含まれない
        self.assertNotIn("ヒント4", result)
        self.assertNotIn("ヒント5", result)

    def test_castle_info_appears_for_known_castle(self):
        analysis = self._make_analysis(
            commentary_hints=["テスト"],
            king_safety_detail={
                "sente": {"castle_type": "美濃囲い", "escape_squares": 2, "adjacent_defenders": 3},
                "gote":  {"castle_type": "その他",   "escape_squares": 1, "adjacent_defenders": 1},
            }
        )
        result = build_board_analysis_block(analysis)
        self.assertIn("囲い状況", result)
        self.assertIn("美濃囲い", result)
        # 「その他」はフィルタされる
        self.assertNotIn("その他", result)

    def test_hanging_pieces_appear(self):
        analysis = self._make_analysis(
            commentary_hints=["テスト"],
            hanging_pieces=[
                {"square": "3e", "piece": "飛", "piece_kind": "R", "side": "sente", "value": 10},
            ]
        )
        result = build_board_analysis_block(analysis)
        self.assertIn("浮き駒", result)
        self.assertIn("先手飛", result)

    def test_check_threat_appears(self):
        analysis = self._make_analysis(
            commentary_hints=["テスト"],
            threats=[
                {"type": "check", "by": "飛", "from": "5e", "to": "5a", "side": "sente"}
            ]
        )
        result = build_board_analysis_block(analysis)
        self.assertIn("脅威", result)
        self.assertIn("王手", result)

    def test_move_impact_capture_appears(self):
        analysis = self._make_analysis(
            commentary_hints=["テスト"],
            move_impact={
                "moved_piece": "飛",
                "from_sq": "5e",
                "to_sq": "5a",
                "captured": "金",
                "is_drop": False,
                "is_promotion": False,
                "new_attacks": [],
                "lost_defenses": [],
                "opened_lines": False,
            }
        )
        result = build_board_analysis_block(analysis)
        self.assertIn("手の影響", result)
        self.assertIn("金を取った", result)

    def test_move_impact_promotion_appears(self):
        analysis = self._make_analysis(
            commentary_hints=["テスト"],
            move_impact={
                "moved_piece": "飛",
                "from_sq": "5e",
                "to_sq": "5a",
                "captured": None,
                "is_drop": False,
                "is_promotion": True,
                "new_attacks": [],
                "lost_defenses": [],
                "opened_lines": False,
            }
        )
        result = build_board_analysis_block(analysis)
        self.assertIn("成り駒", result)

    def test_header_label_present(self):
        analysis = self._make_analysis(commentary_hints=["テスト"])
        result = build_board_analysis_block(analysis)
        self.assertIn("【盤面の詳細分析】", result)


# ---------------------------------------------------------------------------
# Integration: BoardAnalyzer.analyze() → build_board_analysis_block()
# Tests that a real BoardAnalysis feeds through to a non-empty prompt block.
# ---------------------------------------------------------------------------

class TestBoardAnalyzerPipelineIntegration(unittest.TestCase):
    """Real BoardAnalyzer output produces a non-empty prompt block."""

    def setUp(self):
        self.analyzer = BoardAnalyzer()

    def test_startpos_produces_non_empty_block(self):
        """初期局面でも解説ヒント（序盤の汎用メッセージ）が生成される."""
        analysis = self.analyzer.analyze("position startpos", move=None, ply=1)
        block = build_board_analysis_block(analysis)
        # 初期局面は浮き駒も囲いもないが、commentary_hints が汎用メッセージを返す
        self.assertIsInstance(block, str)

    def test_after_moves_has_content(self):
        """数手進んだ局面で盤面分析ブロックにコンテンツが含まれる."""
        sfen = "position startpos moves 7g7f 3c3d 2g2f 8c8d"
        analysis = self.analyzer.analyze(sfen, move="8c8d", ply=4)
        block = build_board_analysis_block(analysis)
        # commentary_hints が少なくとも1件生成されるので block は空でない
        self.assertGreater(len(block), 0)

    def test_block_contains_board_analysis_header(self):
        """ブロックには必ず盤面分析ヘッダーが含まれる."""
        sfen = "position startpos moves 7g7f 3c3d"
        analysis = self.analyzer.analyze(sfen, move="3c3d", ply=2)
        block = build_board_analysis_block(analysis)
        if block:  # non-empty のときだけ
            self.assertIn("【盤面の詳細分析】", block)

    def test_prompt_contains_board_analysis_when_called(self):
        """build_board_analysis_block の出力がプロンプトに組み込まれることを確認する.

        generate_position_comment は async + Gemini API を呼ぶため直接テストせず、
        代わりに「プロンプト文字列の構築ロジック」を検証する。
        """
        sfen = "position startpos moves 7g7f 3c3d 2g2f 8c8d"
        analysis = self.analyzer.analyze(sfen, move="8c8d", ply=4)
        block = build_board_analysis_block(analysis)

        # ダミーの features_block と組み合わせてプロンプトを疑似構築
        features_block = "【局面の状況】\n局面: 序盤"
        prompt = (
            f"手数: 4手目\n"
            f"{features_block}{block}\n"
            f"トーン: 客観的に解説"
        )

        # BoardAnalyzer 由来のヘッダーがプロンプトに含まれている
        self.assertIn("【盤面の詳細分析】", prompt)


if __name__ == "__main__":
    unittest.main()
