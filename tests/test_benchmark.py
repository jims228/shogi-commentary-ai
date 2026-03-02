"""ベンチマークデータセット + バッチ特徴量抽出のテスト."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.api.services.position_features import extract_position_features
from scripts.run_benchmark import _load_benchmark, run_benchmark
from scripts.batch_extract_features import batch_extract, _parse_game_line


# ---------------------------------------------------------------------------
# Part 1: ベンチマーク局面の検証
# ---------------------------------------------------------------------------
class TestBenchmarkPositions(unittest.TestCase):
    """ベンチマーク局面が全て解析可能であることの確認."""

    @classmethod
    def setUpClass(cls):
        cls.positions = _load_benchmark()

    def test_all_positions_parseable(self):
        """全局面が extract_position_features で解析できる."""
        for pos in self.positions:
            with self.subTest(name=pos["name"]):
                features = extract_position_features(
                    pos["sfen"], ply=pos.get("ply", 0)
                )
                self.assertIn("king_safety", features)
                self.assertIn("piece_activity", features)
                self.assertIn("attack_pressure", features)
                self.assertIn("phase", features)

    def test_startpos_phase_opening(self):
        """平手初期局面は opening."""
        pos = self.positions[0]
        features = extract_position_features(pos["sfen"], ply=pos["ply"])
        self.assertEqual(features["phase"], "opening")

    def test_yagura_phase_midgame(self):
        """矢倉囲い完成は midgame."""
        pos = self.positions[1]
        features = extract_position_features(pos["sfen"], ply=pos["ply"])
        self.assertEqual(features["phase"], "midgame")

    def test_central_rook_phase_opening(self):
        """中飛車は opening."""
        pos = self.positions[2]
        features = extract_position_features(pos["sfen"], ply=pos["ply"])
        self.assertEqual(features["phase"], "opening")

    def test_endgame_race_phase(self):
        """終盤の寄せ合いは endgame."""
        pos = self.positions[3]
        features = extract_position_features(pos["sfen"], ply=pos["ply"])
        self.assertEqual(features["phase"], "endgame")

    def test_near_checkmate_phase(self):
        """詰み直前は endgame."""
        pos = self.positions[4]
        features = extract_position_features(pos["sfen"], ply=pos["ply"])
        self.assertEqual(features["phase"], "endgame")

    def test_feature_values_in_range(self):
        """全局面の特徴量が 0-100 の範囲内."""
        for pos in self.positions:
            with self.subTest(name=pos["name"]):
                features = extract_position_features(
                    pos["sfen"], ply=pos.get("ply", 0)
                )
                self.assertGreaterEqual(features["king_safety"], 0)
                self.assertLessEqual(features["king_safety"], 100)
                self.assertGreaterEqual(features["piece_activity"], 0)
                self.assertLessEqual(features["piece_activity"], 100)
                self.assertGreaterEqual(features["attack_pressure"], 0)
                self.assertLessEqual(features["attack_pressure"], 100)


# ---------------------------------------------------------------------------
# Part 2: run_benchmark 検証
# ---------------------------------------------------------------------------
class TestRunBenchmark(unittest.TestCase):
    """run_benchmark の統合テスト."""

    def test_benchmark_all_pass(self):
        """全ベンチマーク局面が期待値を満たす."""
        result = run_benchmark(json_output=True)
        self.assertTrue(
            result["all_pass"],
            f"Failed positions: {result.get('warnings', [])}",
        )

    def test_benchmark_result_structure(self):
        """結果構造が正しい."""
        result = run_benchmark(json_output=True)
        self.assertIn("total", result)
        self.assertIn("passed", result)
        self.assertIn("failed", result)
        self.assertIn("results", result)
        self.assertEqual(result["total"], 8)


# ---------------------------------------------------------------------------
# Part 3: バッチ抽出のテスト
# ---------------------------------------------------------------------------
class TestParseGameLine(unittest.TestCase):
    """_parse_game_line のユニットテスト."""

    def test_position_startpos_moves(self):
        base, moves = _parse_game_line(
            "position startpos moves 7g7f 3c3d 2g2f"
        )
        self.assertEqual(base, "position startpos")
        self.assertEqual(moves, ["7g7f", "3c3d", "2g2f"])

    def test_startpos_moves(self):
        base, moves = _parse_game_line("startpos moves 7g7f 3c3d")
        self.assertEqual(base, "position startpos")
        self.assertEqual(moves, ["7g7f", "3c3d"])

    def test_startpos_no_moves(self):
        base, moves = _parse_game_line("startpos")
        self.assertEqual(base, "position startpos")
        self.assertEqual(moves, [])

    def test_bare_moves(self):
        base, moves = _parse_game_line("7g7f 3c3d")
        self.assertEqual(base, "position startpos")
        self.assertEqual(moves, ["7g7f", "3c3d"])

    def test_sfen_with_moves(self):
        line = "sfen lnsgkgsnl/1r5b1/ppppppppp/9/9/9/PPPPPPPPP/1B5R1/LNSGKGSNL b - 1 moves 7g7f"
        base, moves = _parse_game_line(line)
        self.assertTrue(base.startswith("position sfen"))
        self.assertEqual(moves, ["7g7f"])

    def test_empty_line(self):
        base, moves = _parse_game_line("")
        self.assertEqual(base, "")
        self.assertEqual(moves, [])


class TestBatchExtract(unittest.TestCase):
    """batch_extract のテスト."""

    def test_basic_extraction(self):
        """基本的なJSONL出力."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as inp:
            inp.write("position startpos moves 7g7f 3c3d 2g2f 8c8d 2f2e\n")
            inp_path = inp.name

        out_path = inp_path.replace(".txt", ".jsonl")
        try:
            stats = batch_extract(inp_path, out_path, sample_interval=2)
            self.assertGreater(stats["positions"], 0)
            self.assertEqual(stats["games"], 1)

            # JSONL出力を検証
            with open(out_path, encoding="utf-8") as f:
                records = [json.loads(line) for line in f]

            self.assertGreater(len(records), 0)
            for rec in records:
                self.assertIn("game_index", rec)
                self.assertIn("ply", rec)
                self.assertIn("phase", rec)
                self.assertIn("king_safety", rec)
        finally:
            os.unlink(inp_path)
            if os.path.exists(out_path):
                os.unlink(out_path)

    def test_sample_interval(self):
        """サンプリング間隔が反映される."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as inp:
            # 10手の棋譜
            inp.write(
                "position startpos moves "
                "7g7f 3c3d 2g2f 8c8d 2f2e 4a3b 3i4h 7a6b 5g5f 5c5d\n"
            )
            inp_path = inp.name

        out5 = inp_path.replace(".txt", "_5.jsonl")
        out2 = inp_path.replace(".txt", "_2.jsonl")
        try:
            stats5 = batch_extract(inp_path, out5, sample_interval=5)
            stats2 = batch_extract(inp_path, out2, sample_interval=2)
            # interval=5 は ply 0,5,10 → 3 positions
            # interval=2 は ply 0,2,4,6,8,10 → 6 positions
            self.assertGreater(stats2["positions"], stats5["positions"])
        finally:
            os.unlink(inp_path)
            for p in [out5, out2]:
                if os.path.exists(p):
                    os.unlink(p)

    def test_multiple_games(self):
        """複数棋譜の処理."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as inp:
            inp.write("position startpos moves 7g7f 3c3d\n")
            inp.write("position startpos moves 2g2f 8c8d\n")
            inp.write("# comment line\n")
            inp_path = inp.name

        out_path = inp_path.replace(".txt", ".jsonl")
        try:
            stats = batch_extract(inp_path, out_path, sample_interval=1)
            self.assertEqual(stats["games"], 2)  # コメント行は除外
            self.assertGreater(stats["positions"], 0)
        finally:
            os.unlink(inp_path)
            if os.path.exists(out_path):
                os.unlink(out_path)

    def test_nonexistent_input(self):
        """存在しないファイル."""
        stats = batch_extract("/tmp/no_such_file.txt", "/tmp/out.jsonl")
        self.assertEqual(stats["games"], 0)
        self.assertEqual(stats["positions"], 0)

    def test_prev_features_chaining(self):
        """前局面の特徴量が連鎖して渡される."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as inp:
            inp.write(
                "position startpos moves 7g7f 3c3d 2g2f 8c8d 2f2e\n"
            )
            inp_path = inp.name

        out_path = inp_path.replace(".txt", ".jsonl")
        try:
            batch_extract(inp_path, out_path, sample_interval=1)

            with open(out_path, encoding="utf-8") as f:
                records = [json.loads(line) for line in f]

            # 2手目以降は tension_delta が非ゼロになりうる
            if len(records) >= 2:
                self.assertIn("tension_delta", records[1])
        finally:
            os.unlink(inp_path)
            if os.path.exists(out_path):
                os.unlink(out_path)


if __name__ == "__main__":
    unittest.main()
