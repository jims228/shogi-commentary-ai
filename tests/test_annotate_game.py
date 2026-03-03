"""tests for scripts/annotate_game.py."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.api.services.engine_analysis import AnalysisResult
from scripts.annotate_game import (
    generate_annotation_template,
    _empty_human_annotation,
    _DELTA_HIGHLIGHT_THRESHOLD,
)


# ---------------------------------------------------------------------------
# Mock engine service
# ---------------------------------------------------------------------------
class _MockEngineService:
    """固定の解析結果を返すモックエンジン."""

    def __init__(self, results: dict | None = None):
        self._results = results or {}
        self._call_count = 0
        self._scores: list[int] = []

    def start(self):
        pass

    def stop(self):
        pass

    def analyze_position(self, position_cmd: str) -> AnalysisResult:
        self._call_count += 1
        if "moves" in position_cmd:
            ply = len(position_cmd.split("moves")[1].strip().split())
        else:
            ply = 0

        # ply に応じてスコアを変化させる (blunder テスト用)
        score_cp = self._results.get(ply, 100 - ply * 3)
        self._scores.append(score_cp)

        return AnalysisResult(
            ok=True,
            bestmove="7g7f",
            score_cp=score_cp,
            pv="7g7f 3c3d",
        )


class _MockBlunderEngine:
    """ply=5 で大きなdelta を起こすモックエンジン."""

    def start(self):
        pass

    def stop(self):
        pass

    def analyze_position(self, position_cmd: str) -> AnalysisResult:
        if "moves" in position_cmd:
            ply = len(position_cmd.split("moves")[1].strip().split())
        else:
            ply = 0

        # ply=5 で大暴落 (先手視点で大きく変動)
        if ply <= 4:
            score = 100
        elif ply == 5:
            score = -200  # 手番側視点で -200 → 先手視点で +200 (偶数ply=先手)
        else:
            score = -100

        return AnalysisResult(
            ok=True,
            bestmove="2g2f",
            score_cp=score,
            pv="2g2f",
        )


class _MockMateEngine:
    """特定の ply で詰みを返すモックエンジン."""

    def start(self):
        pass

    def stop(self):
        pass

    def analyze_position(self, position_cmd: str) -> AnalysisResult:
        if "moves" in position_cmd:
            ply = len(position_cmd.split("moves")[1].strip().split())
        else:
            ply = 0

        if ply == 8:
            return AnalysisResult(
                ok=True,
                bestmove="G*5b",
                score_mate=3,
                pv="G*5b 4a3b",
            )

        return AnalysisResult(
            ok=True,
            bestmove="7g7f",
            score_cp=100,
            pv="7g7f 3c3d",
        )


# ---------------------------------------------------------------------------
# テスト
# ---------------------------------------------------------------------------
SAMPLE_GAME = "position startpos moves 7g7f 3c3d 2g2f 8c8d 2f2e 8d8e 6i7h 4a3b 2e2d 2c2d 2h2d"


class TestBasicTemplate(unittest.TestCase):
    """テンプレート生成の基本テスト."""

    def test_template_structure(self):
        """テンプレートの基本構造が正しい."""
        template = generate_annotation_template(
            SAMPLE_GAME,
            game_id="test_game",
            interval=3,
            engine_svc=None,
        )
        self.assertIn("meta", template)
        self.assertIn("positions", template)
        self.assertIn("summary", template)

        meta = template["meta"]
        self.assertEqual(meta["game_id"], "test_game")
        self.assertEqual(meta["annotator"], "")
        self.assertEqual(meta["source_type"], "sample_corpus")
        self.assertIsInstance(meta["date"], str)

    def test_position_fields(self):
        """各局面エントリのフィールドが揃っている."""
        template = generate_annotation_template(
            SAMPLE_GAME, interval=5, engine_svc=None,
        )
        for pos in template["positions"]:
            self.assertIn("ply", pos)
            self.assertIn("sfen", pos)
            self.assertIn("move", pos)
            self.assertIn("highlight", pos)
            self.assertIn("engine_eval", pos)
            self.assertIn("board_analysis", pos)
            self.assertIn("features", pos)
            self.assertIn("human_annotation", pos)

    def test_interval_sampling(self):
        """interval=5 でサンプリングされる."""
        template = generate_annotation_template(
            SAMPLE_GAME, interval=5, engine_svc=None,
        )
        plys = [p["ply"] for p in template["positions"]]
        self.assertEqual(plys, [0, 5, 10])

    def test_interval_1_all_positions(self):
        """interval=1 で全手が出力される."""
        template = generate_annotation_template(
            SAMPLE_GAME, interval=1, engine_svc=None,
        )
        # 11 moves → ply 0..11 = 12 positions
        self.assertEqual(len(template["positions"]), 12)


class TestHumanAnnotation(unittest.TestCase):
    """human_annotation が空であることの確認."""

    def test_all_empty(self):
        """human_annotation の全フィールドが空."""
        template = generate_annotation_template(
            SAMPLE_GAME, interval=5, engine_svc=None,
        )
        for pos in template["positions"]:
            ha = pos["human_annotation"]
            self.assertEqual(ha["commentator_focus"]["primary"], "")
            self.assertEqual(ha["commentator_focus"]["secondary"], [])
            self.assertEqual(ha["commentator_focus"]["ignored"], [])
            self.assertEqual(ha["move_intent_human"], "")
            self.assertEqual(ha["key_insight_ja"], "")
            self.assertEqual(ha["commentary_style"], "")
            self.assertEqual(ha["commentary_depth"], "")
            self.assertEqual(ha["notes"], "")

    def test_empty_function_returns_correct_structure(self):
        """_empty_human_annotation の構造テスト."""
        ha = _empty_human_annotation()
        self.assertIsInstance(ha, dict)
        self.assertIn("commentator_focus", ha)
        self.assertIn("move_intent_human", ha)
        self.assertIn("key_insight_ja", ha)


class TestWithMockEngine(unittest.TestCase):
    """エンジンモック使用時のテスト."""

    def test_engine_eval_populated(self):
        """エンジン使用時に engine_eval が埋まる."""
        mock = _MockEngineService()
        template = generate_annotation_template(
            SAMPLE_GAME, interval=3, engine_svc=mock,
        )
        self.assertGreater(mock._call_count, 0)
        # 最初の局面には score_cp がある
        first = template["positions"][0]
        self.assertIsNotNone(first["engine_eval"]["score_cp"])
        self.assertEqual(first["engine_eval"]["best_move"], "7g7f")

    def test_no_engine_eval_is_null(self):
        """エンジンなし時は engine_eval が null."""
        template = generate_annotation_template(
            SAMPLE_GAME, interval=5, engine_svc=None,
        )
        for pos in template["positions"]:
            self.assertIsNone(pos["engine_eval"]["score_cp"])
            self.assertIsNone(pos["engine_eval"]["best_move"])
            self.assertIsNone(pos["engine_eval"]["pv"])


class TestHighlightDetection(unittest.TestCase):
    """ハイライト判定のテスト."""

    def test_large_delta_triggers_highlight(self):
        """delta > 150 で highlight=true."""
        mock = _MockBlunderEngine()
        template = generate_annotation_template(
            SAMPLE_GAME, interval=1, engine_svc=mock,
        )
        # ply=5 で暴落が起きるはず
        highlighted = [p for p in template["positions"] if p["highlight"]]
        self.assertGreater(len(highlighted), 0)

    def test_mate_triggers_highlight(self):
        """詰みがある局面で highlight=true."""
        mock = _MockMateEngine()
        template = generate_annotation_template(
            SAMPLE_GAME, interval=1, engine_svc=mock,
        )
        # ply=8 で詰みが返る
        pos8 = [p for p in template["positions"] if p["ply"] == 8]
        self.assertTrue(len(pos8) > 0)
        self.assertTrue(pos8[0]["highlight"])

    def test_no_highlight_without_engine(self):
        """エンジンなしではハイライトなし."""
        template = generate_annotation_template(
            SAMPLE_GAME, interval=1, engine_svc=None,
        )
        highlighted = [p for p in template["positions"] if p["highlight"]]
        self.assertEqual(len(highlighted), 0)


class TestSummary(unittest.TestCase):
    """summary の集計テスト."""

    def test_total_positions(self):
        """total_positions が正しい."""
        template = generate_annotation_template(
            SAMPLE_GAME, interval=5, engine_svc=None,
        )
        self.assertEqual(
            template["summary"]["total_positions"],
            len(template["positions"]),
        )

    def test_phase_distribution(self):
        """phase_distribution が集計されている."""
        template = generate_annotation_template(
            SAMPLE_GAME, interval=1, engine_svc=None,
        )
        dist = template["summary"]["phase_distribution"]
        self.assertIn("opening", dist)
        self.assertIn("midgame", dist)
        self.assertIn("endgame", dist)
        total = sum(dist.values())
        self.assertEqual(total, len(template["positions"]))

    def test_highlighted_count_matches(self):
        """highlighted_positions がハイライトされた局面数と一致."""
        mock = _MockBlunderEngine()
        template = generate_annotation_template(
            SAMPLE_GAME, interval=1, engine_svc=mock,
        )
        actual = len([p for p in template["positions"] if p["highlight"]])
        self.assertEqual(template["summary"]["highlighted_positions"], actual)

    def test_mate_positions_in_summary(self):
        """mate_positions に詰み局面の ply が含まれる."""
        mock = _MockMateEngine()
        template = generate_annotation_template(
            SAMPLE_GAME, interval=1, engine_svc=mock,
        )
        self.assertIn(8, template["summary"]["mate_positions"])

    def test_blunder_positions_in_summary(self):
        """blunder_positions にdelta大の ply が含まれる."""
        mock = _MockBlunderEngine()
        template = generate_annotation_template(
            SAMPLE_GAME, interval=1, engine_svc=mock,
        )
        self.assertGreater(len(template["summary"]["blunder_positions"]), 0)


class TestBoardAnalysis(unittest.TestCase):
    """board_analysis セクションのテスト."""

    def test_board_analysis_fields(self):
        """board_analysis に必要なフィールドがある."""
        template = generate_annotation_template(
            SAMPLE_GAME, interval=5, engine_svc=None,
        )
        for pos in template["positions"]:
            ba = pos["board_analysis"]
            self.assertIn("king_safety_sente", ba)
            self.assertIn("king_safety_gote", ba)
            self.assertIn("contested_squares", ba)
            self.assertIn("hanging_pieces", ba)
            self.assertIn("commentary_hints", ba)

    def test_king_safety_fields(self):
        """king_safety に必要なフィールドがある."""
        template = generate_annotation_template(
            SAMPLE_GAME, interval=5, engine_svc=None,
        )
        first = template["positions"][0]
        for side_key in ("king_safety_sente", "king_safety_gote"):
            ks = first["board_analysis"][side_key]
            self.assertIn("king_pos", ks)
            self.assertIn("castle_type", ks)
            self.assertIn("adjacent_defenders", ks)
            self.assertIn("escape_squares", ks)


class TestJsonSerializable(unittest.TestCase):
    """出力がJSON直列化可能かテスト."""

    def test_serializable(self):
        """json.dumps で例外が出ない."""
        mock = _MockEngineService()
        template = generate_annotation_template(
            SAMPLE_GAME, interval=3, engine_svc=mock,
        )
        output = json.dumps(template, ensure_ascii=False, indent=2)
        self.assertIsInstance(output, str)
        # re-parse
        parsed = json.loads(output)
        self.assertEqual(len(parsed["positions"]), len(template["positions"]))


if __name__ == "__main__":
    unittest.main()
