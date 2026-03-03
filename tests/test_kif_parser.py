"""Tests for KIF parser."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.kif_parser import (
    parse_kif,
    parse_kif_file,
    move_to_usi,
    moves_to_usi,
    _detect_encoding,
    _parse_file_rank,
)


# ---------------------------------------------------------------------------
# テスト用KIFデータ
# ---------------------------------------------------------------------------

_SAMPLE_KIF = """\
# ---- Kifu for Windows V7 ----
開始日時：2024/01/15 10:00
棋戦：NHK杯
手合割：平手
先手：藤井聡太
後手：渡辺明
手数----指手---------消費時間--
   1 ７六歩(77)   ( 0:16/00:00:16)
   2 ３四歩(33)   ( 0:05/00:00:05)
*解説者「角道を開ける最もオーソドックスな初手に対し後手も角道を開けました」
   3 ２六歩(27)   ( 0:30/00:00:46)
   4 ８四歩(83)   ( 0:10/00:00:15)
   5 投了
"""

_SAMPLE_KIF_DROP = """\
開始日時：2024/02/01
手合割：平手
先手：先手
後手：後手
手数----指手---------消費時間--
   1 ７六歩(77)   ( 0:01/00:00:01)
   2 ３四歩(33)   ( 0:01/00:00:01)
   3 ２二角成(88)   ( 0:01/00:00:02)
   4 同　銀(31)   ( 0:01/00:00:02)
   5 ４五角打   ( 0:01/00:00:03)
   6 投了
"""

_SAMPLE_KIF_PROMOTE = """\
手合割：平手
先手：A
後手：B
手数----指手---------消費時間--
   1 ７六歩(77)   ( 0:01/00:00:01)
   2 ３四歩(33)   ( 0:01/00:00:01)
   3 ２二角成(88)   ( 0:01/00:00:02)
   4 投了
"""

_SAMPLE_KIF_MULTI_COMMENT = """\
手合割：平手
先手：A
後手：B
手数----指手---------消費時間--
   1 ７六歩(77)   ( 0:16/00:00:16)
*最もポピュラーな初手
*角道を開ける狙い
   2 ３四歩(33)   ( 0:05/00:00:05)
   3 投了
"""

_SAMPLE_KIF_SENNICHITE = """\
手合割：平手
先手：A
後手：B
手数----指手---------消費時間--
   1 ７六歩(77)   ( 0:16/00:00:16)
   2 ３四歩(33)   ( 0:05/00:00:05)
   3 千日手
"""

_SAMPLE_KIF_NO_TIME = """\
手合割：平手
先手：A
後手：B
手数----指手---------消費時間--
   1 ７六歩(77)
   2 ３四歩(33)
   3 投了
"""


class TestHeaderParsing(unittest.TestCase):
    """ヘッダーパーステスト."""

    def test_basic_headers(self):
        result = parse_kif(_SAMPLE_KIF)
        h = result["header"]
        self.assertEqual(h["sente"], "藤井聡太")
        self.assertEqual(h["gote"], "渡辺明")
        self.assertEqual(h["date"], "2024/01/15 10:00")
        self.assertEqual(h["handicap"], "平手")
        self.assertEqual(h["event"], "NHK杯")

    def test_missing_headers(self):
        kif = "手合割：平手\n手数----指手---------消費時間--\n   1 投了\n"
        result = parse_kif(kif)
        h = result["header"]
        self.assertEqual(h.get("handicap"), "平手")
        self.assertNotIn("sente", h)
        self.assertNotIn("gote", h)


class TestMoveParsing(unittest.TestCase):
    """指し手パーステスト."""

    def test_basic_moves(self):
        result = parse_kif(_SAMPLE_KIF)
        moves = result["moves"]
        self.assertEqual(len(moves), 4)

        # 1手目
        self.assertEqual(moves[0]["ply"], 1)
        self.assertIn("歩", moves[0]["move_ja"])
        self.assertEqual(moves[0]["move_from"], "77")
        self.assertEqual(moves[0]["time_spent"], "0:16")
        self.assertEqual(moves[0]["cumulative_time"], "00:00:16")

        # 2手目
        self.assertEqual(moves[1]["ply"], 2)
        self.assertIn("歩", moves[1]["move_ja"])
        self.assertEqual(moves[1]["move_from"], "33")

    def test_same_move(self):
        """「同X」の処理."""
        result = parse_kif(_SAMPLE_KIF_DROP)
        moves = result["moves"]
        # 4手目: 同　銀(31)
        self.assertEqual(moves[3]["ply"], 4)
        self.assertIn("同", moves[3]["move_ja"])
        self.assertIn("銀", moves[3]["move_ja"])
        self.assertTrue(moves[3].get("is_same", False))

    def test_drop_move(self):
        """駒打ちの処理."""
        result = parse_kif(_SAMPLE_KIF_DROP)
        moves = result["moves"]
        # 5手目: ４五角打
        self.assertEqual(moves[4]["ply"], 5)
        self.assertIn("角", moves[4]["move_ja"])
        self.assertTrue(moves[4].get("is_drop", False))

    def test_promote_move(self):
        """成りの処理."""
        result = parse_kif(_SAMPLE_KIF_PROMOTE)
        moves = result["moves"]
        # 3手目: ２二角成(88)
        self.assertEqual(moves[2]["ply"], 3)
        self.assertIn("角", moves[2]["move_ja"])
        self.assertTrue(moves[2].get("is_promote", False))

    def test_no_time(self):
        """消費時間がない指し手行."""
        result = parse_kif(_SAMPLE_KIF_NO_TIME)
        moves = result["moves"]
        self.assertEqual(len(moves), 2)
        self.assertIsNone(moves[0]["time_spent"])
        self.assertIsNone(moves[0]["cumulative_time"])


class TestCommentParsing(unittest.TestCase):
    """コメント抽出テスト."""

    def test_comment_attached_to_move(self):
        result = parse_kif(_SAMPLE_KIF)
        moves = result["moves"]
        # コメントは2手目に紐づく（*行は2手目の直後に出現）
        self.assertEqual(len(moves[1]["comments"]), 1)
        self.assertIn("角道を開ける", moves[1]["comments"][0])

    def test_multi_line_comments(self):
        result = parse_kif(_SAMPLE_KIF_MULTI_COMMENT)
        moves = result["moves"]
        # 1手目に2行のコメント
        self.assertEqual(len(moves[0]["comments"]), 2)
        self.assertIn("ポピュラー", moves[0]["comments"][0])
        self.assertIn("角道", moves[0]["comments"][1])


class TestResultDetection(unittest.TestCase):
    """終了条件テスト."""

    def test_resign(self):
        result = parse_kif(_SAMPLE_KIF)
        self.assertIn("投了", result["result"])

    def test_sennichite(self):
        result = parse_kif(_SAMPLE_KIF_SENNICHITE)
        self.assertIn("千日手", result["result"])


class TestUSIConversion(unittest.TestCase):
    """USI変換テスト."""

    def test_normal_move(self):
        """通常手: ７六歩(77) → 7g7f"""
        result = parse_kif(_SAMPLE_KIF)
        usi_list = moves_to_usi(result)
        # 1手目: 77 → 76 → 7g7f
        self.assertEqual(usi_list[0], "7g7f")
        # 2手目: 33 → 34 → 3c3d
        self.assertEqual(usi_list[1], "3c3d")

    def test_promote_move_usi(self):
        """成り: ２二角成(88) → 8h2b+"""
        result = parse_kif(_SAMPLE_KIF_PROMOTE)
        usi_list = moves_to_usi(result)
        self.assertEqual(usi_list[2], "8h2b+")

    def test_same_move_usi(self):
        """同X: 同銀(31) → 3a2b (移動先は前手の2二)"""
        result = parse_kif(_SAMPLE_KIF_DROP)
        usi_list = moves_to_usi(result)
        # 3手目: ２二角成(88) → 8h2b+
        self.assertEqual(usi_list[2], "8h2b+")
        # 4手目: 同銀(31) → 3a2b
        self.assertEqual(usi_list[3], "3a2b")

    def test_drop_move_usi(self):
        """打ち: ４五角打 → B*4e"""
        result = parse_kif(_SAMPLE_KIF_DROP)
        usi_list = moves_to_usi(result)
        self.assertEqual(usi_list[4], "B*4e")


class TestFileRankParsing(unittest.TestCase):
    """筋段変換テスト."""

    def test_zenkaku_kanji(self):
        f, r = _parse_file_rank("７", "六")
        self.assertEqual(f, 7)
        self.assertEqual(r, 6)

    def test_hankaku(self):
        f, r = _parse_file_rank("7", "六")
        self.assertEqual(f, 7)
        self.assertEqual(r, 6)


class TestEncodingDetection(unittest.TestCase):
    """エンコーディング検出テスト."""

    def test_utf8_file(self):
        with tempfile.NamedTemporaryFile(suffix=".kifu", delete=False, mode="wb") as f:
            f.write(_SAMPLE_KIF.encode("utf-8"))
            path = Path(f.name)
        try:
            enc = _detect_encoding(path)
            self.assertIn("utf", enc.lower())
            result = parse_kif_file(path)
            self.assertEqual(len(result["moves"]), 4)
        finally:
            path.unlink()

    def test_shiftjis_file(self):
        with tempfile.NamedTemporaryFile(suffix=".kif", delete=False, mode="wb") as f:
            f.write(_SAMPLE_KIF.encode("cp932"))
            path = Path(f.name)
        try:
            enc = _detect_encoding(path)
            self.assertEqual(enc, "cp932")
            result = parse_kif_file(path)
            self.assertEqual(len(result["moves"]), 4)
        finally:
            path.unlink()


class TestEdgeCases(unittest.TestCase):
    """エッジケーステスト."""

    def test_empty_input(self):
        result = parse_kif("")
        self.assertEqual(result["moves"], [])
        self.assertEqual(result["result"], "")

    def test_only_comments(self):
        kif = "# これはコメント\n# もう一行\n"
        result = parse_kif(kif)
        self.assertEqual(result["moves"], [])

    def test_header_only(self):
        kif = "先手：テスト\n後手：テスト2\n"
        result = parse_kif(kif)
        self.assertEqual(result["header"]["sente"], "テスト")
        self.assertEqual(result["moves"], [])


if __name__ == "__main__":
    unittest.main()
