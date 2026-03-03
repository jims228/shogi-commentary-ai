"""Tests for sync_commentary pipeline (with mocks for AI)."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.sync_commentary import (
    sync_commentary,
    _match_segment_rule_based,
    _build_move_index,
    _has_shogi_terms,
    _classify_commentary_type,
    _filter_segment,
)


# ---------------------------------------------------------------------------
# テストデータ
# ---------------------------------------------------------------------------

def _make_moves():
    """テスト用棋譜データ."""
    return [
        {"ply": 1, "move_ja": "７六歩", "dest_file": 7, "dest_rank": 6, "piece_name": "歩"},
        {"ply": 2, "move_ja": "３四歩", "dest_file": 3, "dest_rank": 4, "piece_name": "歩"},
        {"ply": 3, "move_ja": "２六歩", "dest_file": 2, "dest_rank": 6, "piece_name": "歩"},
        {"ply": 4, "move_ja": "８四歩", "dest_file": 8, "dest_rank": 4, "piece_name": "歩"},
        {"ply": 5, "move_ja": "２五歩", "dest_file": 2, "dest_rank": 5, "piece_name": "歩"},
        {"ply": 6, "move_ja": "８五歩", "dest_file": 8, "dest_rank": 5, "piece_name": "歩"},
        {"ply": 7, "move_ja": "同銀", "dest_file": 8, "dest_rank": 5, "piece_name": "銀", "is_same": True},
        {"ply": 24, "move_ja": "５五銀", "dest_file": 5, "dest_rank": 5, "piece_name": "銀"},
    ]


def _make_transcript(segments):
    """テスト用文字起こしデータ."""
    return {
        "source": "test_audio.wav",
        "model": "base",
        "language": "ja",
        "segments": segments,
    }


def _make_parsed_kifu(moves):
    """テスト用棋譜パース結果."""
    return {
        "header": {"sente": "先手", "gote": "後手"},
        "moves": moves,
        "result": "投了",
    }


class TestBuildMoveIndex(unittest.TestCase):
    """指し手インデックス構築テスト."""

    def test_basic_index(self):
        moves = _make_moves()
        index = _build_move_index(moves)
        # "7六歩" → [1] (全角→半角正規化)
        self.assertIn("7六歩", index)
        self.assertEqual(index["7六歩"], [1])

    def test_original_key_preserved(self):
        moves = _make_moves()
        index = _build_move_index(moves)
        # 元の全角キーも保持
        self.assertIn("７六歩", index)


class TestRuleBasedMatching(unittest.TestCase):
    """ルールベースマッチングテスト."""

    def test_move_mention_match(self):
        """テキスト中の指し手名 → 正しい ply にマッチ."""
        moves = _make_moves()
        index = _build_move_index(moves)
        text = "ここで5五銀と出たのが好手ですね"
        result = _match_segment_rule_based(text, index, moves)
        self.assertIsNotNone(result)
        ply, confidence, reason = result
        self.assertEqual(ply, 24)
        self.assertGreaterEqual(confidence, 0.9)

    def test_ply_direct_mention(self):
        """「24手目の局面」→ ply=24."""
        moves = _make_moves()
        index = _build_move_index(moves)
        text = "24手目の局面が面白い"
        result = _match_segment_rule_based(text, index, moves)
        self.assertIsNotNone(result)
        ply, confidence, reason = result
        self.assertEqual(ply, 24)
        self.assertEqual(confidence, 1.0)

    def test_no_match(self):
        """将棋に無関係なテキスト → マッチしない."""
        moves = _make_moves()
        index = _build_move_index(moves)
        text = "それでは対局者のプロフィールをご紹介します"
        result = _match_segment_rule_based(text, index, moves)
        self.assertIsNone(result)

    def test_same_move_match(self):
        """「同銀」の処理."""
        moves = _make_moves()
        index = _build_move_index(moves)
        text = "同銀と取った手が素晴らしい"
        result = _match_segment_rule_based(text, index, moves)
        self.assertIsNotNone(result)
        ply, _, _ = result
        self.assertEqual(ply, 7)

    def test_zenkaku_mention(self):
        """全角数字での指し手メンション."""
        moves = _make_moves()
        index = _build_move_index(moves)
        text = "７六歩と角道を開けました"
        result = _match_segment_rule_based(text, index, moves)
        self.assertIsNotNone(result)
        ply, _, _ = result
        self.assertEqual(ply, 1)


class TestFiltering(unittest.TestCase):
    """フィルタリングテスト."""

    def test_shogi_terms_detected(self):
        """将棋用語を含むテキスト → True."""
        self.assertTrue(_has_shogi_terms("角道を開ける手です"))
        self.assertTrue(_has_shogi_terms("矢倉の陣形"))
        self.assertTrue(_has_shogi_terms("王手がかかっています"))

    def test_no_shogi_terms(self):
        """将棋用語を含まないテキスト → False."""
        self.assertFalse(_has_shogi_terms("お昼ご飯は何にしましょうか"))
        self.assertFalse(_has_shogi_terms("対局者の経歴をご紹介します"))

    def test_filter_short_segment(self):
        """短すぎるセグメント除外."""
        is_valid, reason = _filter_segment("はい", has_match=False, neighbor_matched=False)
        self.assertFalse(is_valid)
        self.assertEqual(reason, "too_short")

    def test_filter_no_shogi_terms(self):
        """将棋用語なしセグメント除外."""
        is_valid, reason = _filter_segment(
            "それでは対局者のプロフィールをご紹介します",
            has_match=False,
            neighbor_matched=False,
        )
        self.assertFalse(is_valid)
        self.assertEqual(reason, "no_shogi_terms")

    def test_filter_matched_always_valid(self):
        """マッチ済みセグメントは常に有効."""
        is_valid, _ = _filter_segment("はい", has_match=True, neighbor_matched=False)
        self.assertTrue(is_valid)

    def test_shogi_term_passes_filter(self):
        """将棋用語ありのテキストはフィルター通過."""
        is_valid, _ = _filter_segment(
            "ここで角道を止める手が重要です",
            has_match=False,
            neighbor_matched=False,
        )
        self.assertTrue(is_valid)


class TestCommentaryTypeClassification(unittest.TestCase):
    """コメンタリータイプ推定テスト."""

    def test_move_evaluation(self):
        self.assertEqual(
            _classify_commentary_type("これは好手ですね"),
            "move_evaluation",
        )

    def test_position_analysis(self):
        self.assertEqual(
            _classify_commentary_type("形勢は互角に近いです"),
            "position_analysis",
        )

    def test_tactical(self):
        self.assertEqual(
            _classify_commentary_type("ここで詰みがありますね"),
            "tactical",
        )

    def test_general(self):
        self.assertEqual(
            _classify_commentary_type("次の手を考えましょう"),
            "general",
        )


class TestSyncPipeline(unittest.TestCase):
    """sync_commentary 統合テスト."""

    def test_rule_based_only(self):
        """Stage 1のみ（AI無し）で正しく同期."""
        moves = _make_moves()
        segments = [
            {"id": 0, "start": 10.0, "end": 15.0, "text": "７六歩と角道を開けました"},
            {"id": 1, "start": 15.0, "end": 20.0, "text": "5五銀と出た手が好手ですね"},
            {"id": 2, "start": 20.0, "end": 25.0, "text": "お昼ご飯の話をしましょう"},
        ]
        transcript = _make_transcript(segments)
        parsed_kifu = _make_parsed_kifu(moves)

        result = sync_commentary(transcript, parsed_kifu, use_ai=False)

        # マッチ数
        self.assertEqual(result["stats"]["rule_based_matches"], 2)
        self.assertEqual(result["stats"]["ai_matches"], 0)
        self.assertEqual(len(result["synced_comments"]), 2)

        # 正しい ply にマッチ
        plys = {c["ply"] for c in result["synced_comments"]}
        self.assertIn(1, plys)
        self.assertIn(24, plys)

    def test_unmatched_segments(self):
        """マッチしないセグメントが unmatched に分類."""
        moves = _make_moves()
        segments = [
            {"id": 0, "start": 0.0, "end": 5.0, "text": "こんにちは、本日の対局です"},
            {"id": 1, "start": 100.0, "end": 105.0, "text": "お昼ご飯の話です"},
        ]
        transcript = _make_transcript(segments)
        parsed_kifu = _make_parsed_kifu(moves)

        result = sync_commentary(transcript, parsed_kifu, use_ai=False)

        self.assertEqual(result["stats"]["matched_segments"], 0)
        self.assertEqual(len(result["unmatched_segments"]), 2)

    def test_confidence_values(self):
        """confidence が適切に設定される."""
        moves = _make_moves()
        segments = [
            {"id": 0, "start": 10.0, "end": 15.0, "text": "24手目の局面がポイントです"},
        ]
        transcript = _make_transcript(segments)
        parsed_kifu = _make_parsed_kifu(moves)

        result = sync_commentary(transcript, parsed_kifu, use_ai=False)

        self.assertEqual(len(result["synced_comments"]), 1)
        self.assertEqual(result["synced_comments"][0]["confidence"], 1.0)

    def test_empty_input(self):
        """空の入力でエラーにならない."""
        transcript = _make_transcript([])
        parsed_kifu = _make_parsed_kifu([])

        result = sync_commentary(transcript, parsed_kifu, use_ai=False)

        self.assertEqual(result["stats"]["total_segments"], 0)
        self.assertEqual(result["stats"]["match_rate"], 0.0)


class TestAIMocking(unittest.TestCase):
    """AI補完のモックテスト."""

    @patch("scripts.sync_commentary._ai_match_segments")
    def test_ai_complement(self, mock_ai):
        """AI補完結果が正しく統合される."""
        mock_ai.return_value = [
            {
                "id": 1,
                "start": 50.0,
                "end": 55.0,
                "text": "ここが難しい局面で、攻めるか受けるか迷うところです",
                "ply": 5,
                "confidence": 0.8,
                "match_method": "ai",
                "ai_reason": "context_inference",
            }
        ]

        moves = _make_moves()
        segments = [
            {"id": 0, "start": 10.0, "end": 15.0, "text": "７六歩と角道を開けました"},
            {"id": 1, "start": 50.0, "end": 55.0, "text": "ここが難しい局面で、攻めるか受けるか迷うところです"},
        ]
        transcript = _make_transcript(segments)
        parsed_kifu = _make_parsed_kifu(moves)

        result = sync_commentary(transcript, parsed_kifu, use_ai=True)

        # ルールベース + AI
        self.assertEqual(result["stats"]["rule_based_matches"], 1)
        self.assertEqual(result["stats"]["ai_matches"], 1)
        self.assertEqual(result["stats"]["matched_segments"], 2)

    @patch("scripts.sync_commentary._ai_match_segments")
    def test_ai_confidence_capped(self, mock_ai):
        """AI結果のconfidenceが0.85以下に制限される."""
        mock_ai.return_value = [
            {
                "id": 0,
                "start": 10.0,
                "end": 15.0,
                "text": "難しい局面です",
                "ply": 3,
                "confidence": 0.85,
                "match_method": "ai",
                "ai_reason": "test",
            }
        ]

        moves = _make_moves()
        segments = [
            {"id": 0, "start": 10.0, "end": 15.0, "text": "難しい局面です"},
        ]
        transcript = _make_transcript(segments)
        parsed_kifu = _make_parsed_kifu(moves)

        result = sync_commentary(transcript, parsed_kifu, use_ai=True)

        self.assertEqual(len(result["synced_comments"]), 1)
        self.assertLessEqual(result["synced_comments"][0]["confidence"], 0.85)


if __name__ == "__main__":
    unittest.main()
