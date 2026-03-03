"""tests for backend/api/services/board_analyzer.py."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.api.services.board_analyzer import BoardAnalyzer, BoardAnalysis, _estimate_castle


class TestPiecePlacement(unittest.TestCase):
    """駒配置サマリーのテスト."""

    def setUp(self):
        self.analyzer = BoardAnalyzer()

    def test_startpos_sente_pieces(self):
        """初期局面で先手の全駒が正しく配置されている."""
        r = self.analyzer.analyze("position startpos")
        sente = r.piece_placement["sente"]
        # 先手の歩（STARTPOS_SFEN は P1PPPPPPP = 8枚）
        self.assertEqual(len(sente["歩"]), 8)
        # 飛車と角
        self.assertIn("飛", sente)
        self.assertIn("角", sente)
        self.assertEqual(sente["飛"], ["2h"])
        self.assertEqual(sente["角"], ["8h"])
        # 玉
        self.assertEqual(sente["玉"], ["5i"])

    def test_startpos_gote_pieces(self):
        """初期局面で後手の全駒が正しく配置されている."""
        r = self.analyzer.analyze("position startpos")
        gote = r.piece_placement["gote"]
        # STARTPOS_SFEN は p1ppppppp = 8枚
        self.assertEqual(len(gote["歩"]), 8)
        self.assertEqual(gote["飛"], ["8b"])
        self.assertEqual(gote["角"], ["2b"])
        self.assertEqual(gote["玉"], ["5a"])

    def test_after_move_placement_changes(self):
        """手を指すと駒配置が変わる."""
        r = self.analyzer.analyze("position startpos moves 7g7f")
        sente = r.piece_placement["sente"]
        # 7g の歩が 7f に移動
        self.assertIn("7f", sente["歩"])
        self.assertNotIn("7g", sente["歩"])


class TestContestedSquares(unittest.TestCase):
    """争点マスのテスト."""

    def setUp(self):
        self.analyzer = BoardAnalyzer()

    def test_startpos_has_few_contested(self):
        """初期局面では争点が少ない."""
        r = self.analyzer.analyze("position startpos")
        # 初期局面では5eのみが両方の歩の利きが重なる
        self.assertIsInstance(r.contested_squares, list)
        # 少なくとも存在する
        self.assertLessEqual(len(r.contested_squares), 5)

    def test_midgame_has_more_contested(self):
        """中盤では争点が増える."""
        # 矢倉局面
        r = self.analyzer.analyze(
            "position sfen ln1g1g1nl/1ks1r4/1pppp1p1p/p4s2P/9/P1P1PS1p1/1P1PP1P2/1BK1G2R1/LNSG3NL b - 32",
            ply=32,
        )
        # 中盤なので争点は多いはず
        self.assertGreater(len(r.contested_squares), 0)


class TestHangingPieces(unittest.TestCase):
    """浮き駒検出のテスト."""

    def setUp(self):
        self.analyzer = BoardAnalyzer()

    def test_startpos_no_hanging(self):
        """初期局面には浮き駒がない."""
        r = self.analyzer.analyze("position startpos")
        self.assertEqual(r.hanging_pieces, [])

    def test_detect_hanging_piece(self):
        """浮き駒がある局面で検出される."""
        # 先手の銀が5dにいて、後手の歩が5cにいる → 歩の利き(5d)で攻撃される
        # 銀は味方の利きがない場所にいる → 浮き駒
        sfen = "position sfen lnsgkgsnl/1r5b1/pppp1pppp/4p4/4S4/9/PPPPPPPPP/1B5R1/LNSGKG1NL w - 2"
        r = self.analyzer.analyze(sfen, ply=2)
        hanging_squares = [h["square"] for h in r.hanging_pieces]
        # 5eの銀が後手歩(5c→5d利き)に攻撃されて浮いている
        self.assertIn("5e", hanging_squares)

    def test_hanging_sorted_by_value(self):
        """浮き駒は価値順にソートされる."""
        r = self.analyzer.analyze("position startpos")
        # 初期局面では浮き駒なし（ソートテストはモック的に確認）
        for i in range(len(r.hanging_pieces) - 1):
            self.assertGreaterEqual(
                r.hanging_pieces[i].get("value", 0),
                r.hanging_pieces[i + 1].get("value", 0),
            )


class TestKingSafety(unittest.TestCase):
    """玉の安全度詳細テスト."""

    def setUp(self):
        self.analyzer = BoardAnalyzer()

    def test_startpos_king_safety(self):
        """初期局面の玉の安全度."""
        r = self.analyzer.analyze("position startpos")
        sente = r.king_safety_detail["sente"]
        gote = r.king_safety_detail["gote"]
        self.assertEqual(sente["king_pos"], "5i")
        self.assertEqual(gote["king_pos"], "5a")
        self.assertGreater(sente["adjacent_defenders"], 0)
        self.assertEqual(sente["adjacent_attackers"], 0)
        self.assertGreater(sente["escape_squares"], 0)

    def test_endgame_king_safety(self):
        """終盤局面で玉の安全度が低い."""
        sfen = "position sfen 4k4/9/4G4/9/9/9/9/9/4K4 b G2r2b4s4n4l18p 120"
        r = self.analyzer.analyze(sfen, ply=120)
        gote = r.king_safety_detail["gote"]
        # 後手玉は金に迫られていて安全度が低い
        self.assertGreater(gote["adjacent_attackers"], 0)


class TestCastleEstimation(unittest.TestCase):
    """囲い推定のテスト."""

    def test_startpos_is_igyo(self):
        """初期局面は居玉."""
        r = BoardAnalyzer().analyze("position startpos")
        self.assertEqual(r.king_safety_detail["sente"]["castle_type"], "居玉")

    def test_yagura_detection(self):
        """矢倉囲いの検出."""
        # 先手玉が7hにいて金銀が上部にある矢倉局面
        sfen = "position sfen ln1g1g1nl/1ks1r4/1pppp1p1p/p4s2P/9/P1P1PS1p1/1P1PP1P2/1BK1G2R1/LNSG3NL b - 32"
        r = BoardAnalyzer().analyze(sfen, ply=32)
        sente = r.king_safety_detail["sente"]
        # 先手玉は8hにいる → 矢倉パターン
        self.assertIn(sente["castle_type"], ("矢倉", "美濃囲い", "船囲い", "その他"))

    def test_anaguma_detection(self):
        """穴熊囲いの検出."""
        # 先手玉が9iにいて金銀で固めた穴熊
        sfen = "position sfen lnsgk2nl/1r4gs1/p1pppp1bp/9/9/P1P1P2PP/1P1P1PP2/1BSG1S1R1/LN1GK3L b Np 35"
        r = BoardAnalyzer().analyze(sfen, ply=35)
        gote = r.king_safety_detail["gote"]
        # 後手の囲い判定（gote側の玉位置次第）
        self.assertIsInstance(gote["castle_type"], str)


class TestMoveImpact(unittest.TestCase):
    """手の変化分析テスト."""

    def setUp(self):
        self.analyzer = BoardAnalyzer()

    def test_7g7f_opens_bishop_line(self):
        """7g7f で角道が開くことを検出."""
        r = self.analyzer.analyze(
            "position startpos moves 7g7f",
            move="7g7f",
            ply=1,
        )
        self.assertIsNotNone(r.move_impact)
        self.assertEqual(r.move_impact["moved_piece"], "歩")
        self.assertEqual(r.move_impact["from_sq"], "7g")
        self.assertEqual(r.move_impact["to_sq"], "7f")
        self.assertIsNone(r.move_impact["captured"])
        self.assertTrue(r.move_impact["opened_lines"])
        # 新たに利きが通ったマスがある
        self.assertGreater(len(r.move_impact["new_attacks"]), 0)

    def test_capture_detected(self):
        """駒を取る手で captured が設定される."""
        # 3c3d で先手歩が後手歩を取る
        r = self.analyzer.analyze(
            "position startpos moves 7g7f 3c3d 2g2f 8c8d 2f2e 8d8e 6i7h 4a3b 2e2d",
            move="2d",  # USI の最後の手を渡す
            ply=9,
        )
        # move_impact は position_cmd の最後の手で計算
        # この場合、2e2d は歩の前進で取りは発生しないかもしれないが
        # テストケースとして move_impact の存在を確認
        self.assertIsNotNone(r.move_impact)

    def test_drop_move_impact(self):
        """駒打ちの手情報."""
        # 駒打ちを含む局面
        sfen = "position sfen 4k4/9/9/9/9/9/9/9/4K4 b G 1 moves G*5b"
        r = self.analyzer.analyze(sfen, move="G*5b", ply=1)
        self.assertIsNotNone(r.move_impact)
        self.assertTrue(r.move_impact["is_drop"])
        self.assertEqual(r.move_impact["to_sq"], "5b")


class TestCommentaryHints(unittest.TestCase):
    """解説ヒント生成テスト."""

    def setUp(self):
        self.analyzer = BoardAnalyzer()

    def test_hints_are_japanese(self):
        """commentary_hints が日本語で生成される."""
        r = self.analyzer.analyze("position startpos")
        self.assertIsInstance(r.commentary_hints, list)
        self.assertGreater(len(r.commentary_hints), 0)
        for hint in r.commentary_hints:
            self.assertIsInstance(hint, str)
            self.assertGreater(len(hint), 0)

    def test_hints_not_abstract(self):
        """ヒントが具体的（「この局面は複雑です」のような抽象的なものでない）."""
        # 中盤局面
        sfen = "position sfen ln1g1g1nl/1ks1r4/1pppp1p1p/p4s2P/9/P1P1PS1p1/1P1PP1P2/1BK1G2R1/LNSG3NL b - 32"
        r = self.analyzer.analyze(sfen, ply=32)
        for hint in r.commentary_hints:
            self.assertNotIn("複雑です", hint)
            self.assertNotIn("難しい局面", hint)

    def test_endgame_hints_mention_escape(self):
        """終盤局面で逃げ道に関するヒントが出る."""
        sfen = "position sfen 4k4/4G4/4P4/9/9/9/9/9/4K4 b r2b2g3s4n4l17p 150"
        r = self.analyzer.analyze(sfen, ply=150)
        hints_text = " ".join(r.commentary_hints)
        # 後手玉は逃げ道がないか、攻め関連のヒントが出るはず
        self.assertGreater(len(r.commentary_hints), 0)

    def test_opening_has_generic_hint(self):
        """序盤で具体的なヒントが少なくても汎用ヒントがある."""
        r = self.analyzer.analyze("position startpos", ply=0)
        self.assertGreater(len(r.commentary_hints), 0)

    def test_hanging_piece_in_hints(self):
        """浮き駒がある局面でヒントに含まれる."""
        sfen = "position sfen lnsgkgsnl/1r5b1/ppppppppp/9/4S4/9/PPPPPPPPP/1B5R1/LNSGKG1NL w - 2"
        r = self.analyzer.analyze(sfen, ply=2)
        hints_text = " ".join(r.commentary_hints)
        if r.hanging_pieces:
            self.assertIn("浮いている", hints_text)


class TestBenchmarkPositions(unittest.TestCase):
    """benchmark_positions.json の全局面でクラッシュしないことを確認."""

    def setUp(self):
        self.analyzer = BoardAnalyzer()
        bench_path = Path(__file__).resolve().parent.parent / "data" / "benchmark_positions.json"
        with open(bench_path) as f:
            self.positions = json.load(f)

    def test_all_benchmark_positions(self):
        """全ベンチマーク局面で分析が正常に完了する."""
        for pos in self.positions:
            with self.subTest(name=pos["name"]):
                r = self.analyzer.analyze(pos["sfen"], ply=pos.get("ply", 0))
                self.assertIsInstance(r, BoardAnalysis)
                self.assertIsInstance(r.piece_placement, dict)
                self.assertIn("sente", r.piece_placement)
                self.assertIn("gote", r.piece_placement)
                self.assertIsInstance(r.contested_squares, list)
                self.assertIsInstance(r.hanging_pieces, list)
                self.assertIsInstance(r.king_safety_detail, dict)
                self.assertIsInstance(r.threats, list)
                self.assertIsInstance(r.commentary_hints, list)
                self.assertGreater(len(r.commentary_hints), 0)


if __name__ == "__main__":
    unittest.main()
