"""Tests for annotation schema and rule-based annotation service."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import unittest

from backend.api.schemas.annotation import (
    DEPTH_LEVELS,
    FOCUS_LABELS,
    validate_annotation,
)
from backend.api.services.annotation_service import annotate_text


def _make_features(**overrides):
    """テスト用の局面特徴量を生成."""
    base = {
        "king_safety": 50,
        "piece_activity": 50,
        "attack_pressure": 0,
        "phase": "midgame",
        "turn": "b",
        "ply": 30,
        "move_intent": "development",
        "tension_delta": {
            "d_king_safety": 0.0,
            "d_piece_activity": 0.0,
            "d_attack_pressure": 0.0,
        },
    }
    base.update(overrides)
    return base


def _make_valid_record(**ann_overrides):
    """テスト用のアノテーションレコードを生成."""
    ann = {
        "focus": ["king_safety"],
        "importance": 0.5,
        "depth": "strategic",
        "style": "neutral",
    }
    ann.update(ann_overrides)
    return {
        "sfen": "position startpos",
        "ply": 10,
        "features": _make_features(),
        "annotation": ann,
        "original_text": "テスト解説文",
        "annotator": "rule-based",
    }


# ---------------------------------------------------------------------------
# Schema validation tests
# ---------------------------------------------------------------------------
class TestValidateAnnotation(unittest.TestCase):
    """validate_annotation のテスト."""

    def test_valid_record_passes(self) -> None:
        valid, errors = validate_annotation(_make_valid_record())
        self.assertTrue(valid)
        self.assertEqual(errors, [])

    def test_valid_multiple_focus(self) -> None:
        record = _make_valid_record(
            focus=["king_safety", "attack_pressure", "tempo"]
        )
        valid, errors = validate_annotation(record)
        self.assertTrue(valid)

    def test_valid_all_depth_levels(self) -> None:
        for depth in DEPTH_LEVELS:
            record = _make_valid_record(depth=depth)
            valid, errors = validate_annotation(record)
            self.assertTrue(valid, f"depth={depth} should be valid")

    def test_invalid_focus_label(self) -> None:
        record = _make_valid_record(focus=["king_safety", "nonexistent"])
        valid, errors = validate_annotation(record)
        self.assertFalse(valid)
        self.assertTrue(any("nonexistent" in e for e in errors))

    def test_importance_out_of_range(self) -> None:
        record = _make_valid_record(importance=1.5)
        valid, errors = validate_annotation(record)
        self.assertFalse(valid)
        self.assertTrue(any("importance" in e for e in errors))

    def test_importance_negative(self) -> None:
        record = _make_valid_record(importance=-0.1)
        valid, errors = validate_annotation(record)
        self.assertFalse(valid)

    def test_invalid_depth(self) -> None:
        record = _make_valid_record(depth="ultra_deep")
        valid, errors = validate_annotation(record)
        self.assertFalse(valid)
        self.assertTrue(any("depth" in e for e in errors))

    def test_invalid_style(self) -> None:
        record = _make_valid_record(style="aggressive")
        valid, errors = validate_annotation(record)
        self.assertFalse(valid)
        self.assertTrue(any("style" in e for e in errors))

    def test_missing_annotation_field(self) -> None:
        record = {"sfen": "test", "ply": 0}
        valid, errors = validate_annotation(record)
        self.assertFalse(valid)
        self.assertTrue(any("annotation" in e for e in errors))


# ---------------------------------------------------------------------------
# Focus detection tests
# ---------------------------------------------------------------------------
class TestFocusDetection(unittest.TestCase):
    """annotate_text の focus 推定テスト."""

    def test_king_safety_keywords(self) -> None:
        text = "玉の囲いを固めて守りを重視します。"
        result = annotate_text(text, _make_features())
        self.assertIn("king_safety", result["focus"])

    def test_attack_pressure_keywords(self) -> None:
        text = "攻めの形を作り、相手玉に迫る狙いです。"
        result = annotate_text(text, _make_features())
        self.assertIn("attack_pressure", result["focus"])

    def test_piece_activity_keywords(self) -> None:
        text = "銀を活用して駒の効率を上げていきます。"
        result = annotate_text(text, _make_features())
        self.assertIn("piece_activity", result["focus"])

    def test_endgame_technique_keywords(self) -> None:
        text = "終盤の寄せに入り、詰みを目指します。"
        result = annotate_text(text, _make_features())
        self.assertIn("endgame_technique", result["focus"])

    def test_multiple_focus_labels(self) -> None:
        text = "玉の守りを固めつつ、攻めの狙いも見せる展開です。"
        result = annotate_text(text, _make_features())
        self.assertIn("king_safety", result["focus"])
        self.assertIn("attack_pressure", result["focus"])

    def test_fallback_positional(self) -> None:
        text = "ここは自然な一手です。"
        result = annotate_text(text, _make_features())
        self.assertIn("positional", result["focus"])


# ---------------------------------------------------------------------------
# Depth estimation tests
# ---------------------------------------------------------------------------
class TestDepthEstimation(unittest.TestCase):
    """annotate_text の depth 推定テスト."""

    def test_short_text_surface(self) -> None:
        text = "7六歩と突きました。"
        result = annotate_text(text, _make_features())
        self.assertEqual(result["depth"], "surface")

    def test_medium_text_strategic(self) -> None:
        text = "角道を開けて攻めの準備を整えています。駒の活用を図る展開です。"
        result = annotate_text(text, _make_features())
        self.assertEqual(result["depth"], "strategic")

    def test_intent_word_strategic(self) -> None:
        text = "攻めのための準備です。"
        result = annotate_text(text, _make_features())
        self.assertEqual(result["depth"], "strategic")

    def test_long_with_conditional_deep(self) -> None:
        text = (
            "ここで飛車を振ることで攻めの形を作ります。"
            "もし相手が受けに回った場合は角の活用を図り、"
            "さらに桂馬の跳躍で攻撃の幅を広げていくことになります。"
            "非常に重要な局面で、慎重に考える必要があります。"
        )
        result = annotate_text(text, _make_features())
        self.assertEqual(result["depth"], "deep")


# ---------------------------------------------------------------------------
# Importance estimation tests
# ---------------------------------------------------------------------------
class TestImportanceEstimation(unittest.TestCase):
    """annotate_text の importance 推定テスト."""

    def test_zero_delta_low_importance(self) -> None:
        features = _make_features()
        result = annotate_text("普通の一手です。", features)
        self.assertLessEqual(result["importance"], 0.2)

    def test_high_delta_high_importance(self) -> None:
        features = _make_features(
            tension_delta={
                "d_king_safety": 15.0,
                "d_piece_activity": 10.0,
                "d_attack_pressure": 8.0,
            }
        )
        result = annotate_text("大きな変化です。", features)
        self.assertGreaterEqual(result["importance"], 0.5)

    def test_endgame_boost(self) -> None:
        features_mid = _make_features(phase="midgame")
        features_end = _make_features(phase="endgame")
        result_mid = annotate_text("一手。", features_mid)
        result_end = annotate_text("一手。", features_end)
        self.assertGreater(result_end["importance"], result_mid["importance"])

    def test_importance_clamped_to_1(self) -> None:
        features = _make_features(
            phase="endgame",
            move_intent="sacrifice",
            tension_delta={
                "d_king_safety": 50.0,
                "d_piece_activity": 50.0,
                "d_attack_pressure": 50.0,
            },
        )
        result = annotate_text("大駒を捨てる。", features)
        self.assertLessEqual(result["importance"], 1.0)


# ---------------------------------------------------------------------------
# Integration test
# ---------------------------------------------------------------------------
class TestAnnotationIntegration(unittest.TestCase):
    """annotate_text の統合テスト."""

    def test_result_has_all_fields(self) -> None:
        result = annotate_text(
            "玉の囲いを整えつつ攻めの狙いを見せます。",
            _make_features(),
        )
        self.assertIn("focus", result)
        self.assertIn("importance", result)
        self.assertIn("depth", result)
        self.assertIn("style", result)
        self.assertIsInstance(result["focus"], list)
        self.assertIsInstance(result["importance"], float)
        self.assertIn(result["depth"], DEPTH_LEVELS)

    def test_annotated_record_validates(self) -> None:
        ann = annotate_text(
            "序盤の駒組みが進んでいます。銀を活用して攻めの準備です。",
            _make_features(phase="opening"),
        )
        record = {
            "sfen": "position startpos",
            "ply": 10,
            "features": _make_features(phase="opening"),
            "annotation": ann,
            "original_text": "テスト",
            "annotator": "rule-based",
        }
        valid, errors = validate_annotation(record)
        self.assertTrue(valid, f"Errors: {errors}")


if __name__ == "__main__":
    unittest.main()
