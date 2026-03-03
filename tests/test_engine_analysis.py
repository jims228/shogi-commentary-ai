"""tests for backend/api/services/engine_analysis.py and --with-engine integration."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.api.services.engine_analysis import (
    AnalysisResult,
    EngineAnalysisService,
    _parse_info_line,
)


# =====================================================================
# Unit tests for _parse_info_line (no engine needed)
# =====================================================================
class TestParseInfoLine(unittest.TestCase):
    """parse_usi_info と同等のパーサの単体テスト."""

    def test_cp_score(self):
        line = "info depth 10 multipv 1 score cp 120 nodes 50000 pv 7g7f 3c3d"
        result = _parse_info_line(line)
        self.assertIsNotNone(result)
        self.assertEqual(result["multipv"], 1)
        self.assertEqual(result["score"]["type"], "cp")
        # SCORE_SCALE=0.7 → 120 * 0.7 = 84
        self.assertEqual(result["score"]["cp"], 84)
        self.assertEqual(result["pv"], "7g7f 3c3d")

    def test_mate_score(self):
        line = "info depth 15 multipv 1 score mate 5 pv G*5b 4a3b"
        result = _parse_info_line(line)
        self.assertIsNotNone(result)
        self.assertEqual(result["score"]["type"], "mate")
        self.assertEqual(result["score"]["mate"], 5)

    def test_negative_mate(self):
        line = "info depth 12 multipv 1 score mate -3 pv 5a4b"
        result = _parse_info_line(line)
        self.assertIsNotNone(result)
        self.assertEqual(result["score"]["mate"], -3)

    def test_multipv_parsing(self):
        line = "info depth 10 multipv 3 score cp 50 pv 2g2f"
        result = _parse_info_line(line)
        self.assertIsNotNone(result)
        self.assertEqual(result["multipv"], 3)

    def test_lowerbound(self):
        line = "info depth 10 multipv 1 score cp lowerbound 100 pv 7g7f"
        result = _parse_info_line(line)
        self.assertIsNotNone(result)
        self.assertEqual(result["score"]["cp"], 70)  # 100 * 0.7

    def test_no_score(self):
        line = "info depth 10 nodes 50000"
        result = _parse_info_line(line)
        self.assertIsNone(result)

    def test_no_pv(self):
        line = "info depth 10 score cp 50 nodes 50000"
        result = _parse_info_line(line)
        self.assertIsNone(result)


# =====================================================================
# Unit tests for AnalysisResult
# =====================================================================
class TestAnalysisResult(unittest.TestCase):
    def test_to_eval_info(self):
        r = AnalysisResult(ok=True, bestmove="7g7f", score_cp=100, pv="7g7f 3c3d")
        info = r.to_eval_info()
        self.assertEqual(info["score_cp"], 100)
        self.assertEqual(info["bestmove"], "7g7f")
        self.assertEqual(info["pv"], "7g7f 3c3d")
        self.assertIsNone(info["score_mate"])

    def test_to_eval_info_mate(self):
        r = AnalysisResult(ok=True, bestmove="G*5b", score_mate=3)
        info = r.to_eval_info()
        self.assertIsNone(info["score_cp"])
        self.assertEqual(info["score_mate"], 3)

    def test_default_values(self):
        r = AnalysisResult()
        self.assertFalse(r.ok)
        self.assertEqual(r.bestmove, "")
        self.assertIsNone(r.score_cp)
        self.assertEqual(r.multipv, [])


# =====================================================================
# Tests with mock engine (no real engine needed for CI)
# =====================================================================
class _MockEngineService:
    """EngineAnalysisService のモック. 固定の解析結果を返す."""

    def __init__(self, results=None):
        self._results = results or {}
        self._call_count = 0

    def start(self):
        pass

    def stop(self):
        pass

    def analyze_position(self, position_cmd: str) -> AnalysisResult:
        self._call_count += 1
        # ply を position_cmd の moves 数から推定
        if "moves" in position_cmd:
            ply = len(position_cmd.split("moves")[1].strip().split())
        else:
            ply = 0
        return AnalysisResult(
            ok=True,
            bestmove="7g7f",
            score_cp=100 - ply * 5,
            pv="7g7f 3c3d",
        )


class TestBatchExtractWithEngine(unittest.TestCase):
    """--with-engine 統合のモックテスト."""

    def test_with_engine_adds_score_cp(self):
        """エンジン使用時に score_cp 等が出力に含まれる."""
        from scripts.batch_extract_features import _batch_extract_loop

        input_file = str(Path(__file__).resolve().parent.parent / "data" / "sample_games.txt")
        input_path = Path(input_file)
        lines = [
            l.strip()
            for l in input_path.read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.strip().startswith("#")
        ][:1]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = os.path.join(tmpdir, "out.jsonl")

            mock_svc = _MockEngineService()
            total, _ = _batch_extract_loop(
                lines,
                output_file,
                sample_interval=10,
                engine_svc=mock_svc,
                progress_fn=lambda g, p, e: None,
            )

            self.assertGreater(total, 0)
            self.assertGreater(mock_svc._call_count, 0)

            with open(output_file) as f:
                records = [json.loads(line) for line in f]

            self.assertGreater(len(records), 0)
            first = records[0]
            self.assertIn("score_cp", first)
            self.assertIn("bestmove", first)
            self.assertIn("pv", first)
            self.assertIsNotNone(first["score_cp"])
            self.assertEqual(first["bestmove"], "7g7f")

    def test_without_engine_no_score(self):
        """エンジンなしの場合は score_cp 等がない (従来通り)."""
        from scripts.batch_extract_features import _batch_extract_loop, _parse_game_line

        input_file = str(Path(__file__).resolve().parent.parent / "data" / "sample_games.txt")
        input_path = Path(input_file)
        lines = [
            l.strip()
            for l in input_path.read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.strip().startswith("#")
        ][:1]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = os.path.join(tmpdir, "out.jsonl")
            total, _ = _batch_extract_loop(
                lines,
                output_file,
                sample_interval=10,
                engine_svc=None,
                progress_fn=lambda g, p, e: None,
            )

            with open(output_file) as f:
                records = [json.loads(line) for line in f]

            self.assertGreater(len(records), 0)
            first = records[0]
            # engine_extra フィールドは含まれない
            self.assertNotIn("bestmove", first)
            self.assertNotIn("pv", first)

    def test_delta_cp_calculation(self):
        """連続する局面で delta_cp が正しく計算される."""
        from scripts.batch_extract_features import _batch_extract_loop

        # 3手だけの短い棋譜を作成
        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = os.path.join(tmpdir, "game.txt")
            with open(input_file, "w") as f:
                f.write("position startpos moves 7g7f 3c3d 2g2f\n")

            output_file = os.path.join(tmpdir, "out.jsonl")

            mock_svc = _MockEngineService()
            total, _ = _batch_extract_loop(
                ["position startpos moves 7g7f 3c3d 2g2f"],
                output_file,
                sample_interval=1,
                engine_svc=mock_svc,
                progress_fn=lambda g, p, e: None,
            )

            with open(output_file) as f:
                records = [json.loads(line) for line in f]

            # ply=0 の delta_cp は None (前局面がない)
            self.assertIsNone(records[0]["delta_cp"])
            # ply=1 以降は delta_cp が数値
            for rec in records[1:]:
                if rec.get("score_cp") is not None:
                    self.assertIsNotNone(rec["delta_cp"])


class TestAnalyzeGame(unittest.TestCase):
    """EngineAnalysisService.analyze_game のモックテスト."""

    def test_analyze_game_returns_results(self):
        """analyze_game が各手の eval_info を返す."""
        svc = EngineAnalysisService.__new__(EngineAnalysisService)
        svc._alive = True
        svc._loop = MagicMock()
        svc._timeout = 10.0

        # analyze_position をモック
        call_count = 0
        def mock_analyze(pos_cmd):
            nonlocal call_count
            call_count += 1
            return AnalysisResult(ok=True, bestmove="7g7f", score_cp=80 + call_count * 5, pv="7g7f")

        svc.analyze_position = mock_analyze

        results = svc.analyze_game(
            "position startpos",
            ["7g7f", "3c3d", "2g2f"],
            sample_interval=1,
        )

        self.assertEqual(len(results), 4)  # ply 0,1,2,3
        self.assertEqual(results[0]["ply"], 0)
        self.assertEqual(results[3]["ply"], 3)
        # 全てに score_cp と bestmove がある
        for r in results:
            self.assertIn("score_cp", r)
            self.assertIn("bestmove", r)

    def test_analyze_game_with_interval(self):
        """sample_interval=2 で間引きされる."""
        svc = EngineAnalysisService.__new__(EngineAnalysisService)
        svc._alive = True
        svc._loop = MagicMock()
        svc._timeout = 10.0

        svc.analyze_position = lambda pos: AnalysisResult(ok=True, bestmove="7g7f", score_cp=100, pv="7g7f")

        results = svc.analyze_game(
            "position startpos",
            ["7g7f", "3c3d", "2g2f", "8c8d"],
            sample_interval=2,
        )
        plys = [r["ply"] for r in results]
        self.assertEqual(plys, [0, 2, 4])


if __name__ == "__main__":
    unittest.main()
