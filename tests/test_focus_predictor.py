"""Tests for focus predictor and commentary enhancer."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.api.schemas.annotation import FOCUS_LABELS

try:
    from sklearn.ensemble import RandomForestClassifier
    _HAS_SKLEARN = True
except ImportError:
    _HAS_SKLEARN = False

from backend.api.services.focus_predictor import (
    FocusPredictor,
    _rule_based_predict_from_features,
)
from backend.api.services.commentary_enhancer import (
    FOCUS_DESCRIPTIONS,
    enhance_prompt_with_focus,
)


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


def _create_annotated_corpus(tmpdir: str, n: int = 80) -> str:
    """テスト用のアノテーション済みコーパスを生成."""
    path = os.path.join(tmpdir, "annotated_corpus.jsonl")
    focus_options = [
        ["king_safety"],
        ["piece_activity"],
        ["attack_pressure"],
        ["positional"],
        ["king_safety", "piece_activity"],
        ["attack_pressure", "endgame_technique"],
    ]
    with open(path, "w", encoding="utf-8") as f:
        for i in range(n):
            phase = ["opening", "midgame", "endgame"][i % 3]
            ap = (i * 7) % 100
            ks = 50 - (i % 30)
            pa = 40 + (i % 35)
            focus = focus_options[i % len(focus_options)]
            record = {
                "features": {
                    "king_safety": ks,
                    "piece_activity": pa,
                    "attack_pressure": ap,
                    "phase": phase,
                    "ply": i * 5,
                    "tension_delta": {
                        "d_king_safety": float(i % 10 - 5),
                        "d_piece_activity": float(i % 8 - 4),
                        "d_attack_pressure": float(i % 6 - 3),
                    },
                },
                "annotation": {
                    "focus": focus,
                    "importance": round(min(1.0, (i % 10) / 10.0), 2),
                    "depth": ["surface", "strategic", "deep"][i % 3],
                    "style": "neutral",
                },
                "original_text": f"テスト解説文{i}",
                "annotator": "rule-based",
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return path


# ---------------------------------------------------------------------------
# Rule-based fallback tests
# ---------------------------------------------------------------------------
class TestRuleBasedFallback(unittest.TestCase):
    """ルールベースフォールバックのテスト."""

    def test_low_king_safety(self) -> None:
        features = _make_features(king_safety=20)
        result = _rule_based_predict_from_features(features)
        self.assertIn("king_safety", result)

    def test_high_attack_pressure(self) -> None:
        features = _make_features(attack_pressure=60)
        result = _rule_based_predict_from_features(features)
        self.assertIn("attack_pressure", result)

    def test_high_piece_activity(self) -> None:
        features = _make_features(piece_activity=80)
        result = _rule_based_predict_from_features(features)
        self.assertIn("piece_activity", result)

    def test_endgame_phase(self) -> None:
        features = _make_features(phase="endgame")
        result = _rule_based_predict_from_features(features)
        self.assertIn("endgame_technique", result)

    def test_default_positional(self) -> None:
        features = _make_features()
        result = _rule_based_predict_from_features(features)
        self.assertIn("positional", result)

    def test_empty_features(self) -> None:
        result = _rule_based_predict_from_features({})
        self.assertIsInstance(result, list)
        self.assertTrue(len(result) > 0)


# ---------------------------------------------------------------------------
# FocusPredictor tests
# ---------------------------------------------------------------------------
@unittest.skipUnless(_HAS_SKLEARN, "scikit-learn not installed")
class TestFocusPredictorTrain(unittest.TestCase):
    """FocusPredictor の訓練テスト."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.mkdtemp()
        self._corpus_path = _create_annotated_corpus(self._tmpdir, n=80)

    def test_train_returns_stats(self) -> None:
        fp = FocusPredictor()
        result = fp.train(data_path=self._corpus_path)
        self.assertNotIn("error", result)
        self.assertEqual(result["n_samples"], 80)
        self.assertEqual(result["n_labels"], len(FOCUS_LABELS))
        self.assertIn("accuracy", result)
        self.assertIn("f1_samples", result)
        self.assertIn("f1_macro", result)
        self.assertIn("label_distribution", result)
        # Minimum performance thresholds — catch complete model failure
        self.assertGreater(result["accuracy"], 0.5)
        self.assertGreater(result["f1_samples"], 0.4)
        self.assertGreater(result["f1_macro"], 0.4)

    def test_train_marks_trained(self) -> None:
        fp = FocusPredictor()
        self.assertFalse(fp.is_trained)
        fp.train(data_path=self._corpus_path)
        self.assertTrue(fp.is_trained)

    def test_predict_trained_model(self) -> None:
        fp = FocusPredictor()
        fp.train(data_path=self._corpus_path)
        result = fp.predict(_make_features())
        self.assertIsInstance(result, list)
        self.assertTrue(len(result) > 0)
        for lbl in result:
            self.assertIn(lbl, FOCUS_LABELS)

    def test_predict_untrained_fallback(self) -> None:
        fp = FocusPredictor()
        result = fp.predict(_make_features())
        self.assertIsInstance(result, list)
        self.assertTrue(len(result) > 0)

    def test_evaluate_returns_metrics(self) -> None:
        fp = FocusPredictor()
        result = fp.evaluate(data_path=self._corpus_path, n_splits=3)
        self.assertNotIn("error", result)
        self.assertIn("mean_accuracy", result)
        self.assertIn("mean_f1_samples", result)
        self.assertIn("mean_f1_macro", result)
        self.assertIn("per_label_f1", result)
        self.assertEqual(len(result["per_label_f1"]), len(FOCUS_LABELS))
        # Minimum performance thresholds — catch complete model failure
        self.assertGreater(result["mean_accuracy"], 0.5)
        self.assertGreater(result["mean_f1_samples"], 0.4)
        self.assertGreater(result["mean_f1_macro"], 0.4)

    def test_save_and_load_roundtrip(self) -> None:
        fp = FocusPredictor()
        fp.train(data_path=self._corpus_path)

        model_path = os.path.join(self._tmpdir, "test_model.joblib")
        saved = fp.save(path=model_path)
        self.assertTrue(os.path.exists(saved))

        fp2 = FocusPredictor()
        self.assertFalse(fp2.is_trained)
        loaded = fp2.load(path=model_path)
        self.assertTrue(loaded)
        self.assertTrue(fp2.is_trained)

        # Predictions should match
        features = _make_features(king_safety=30, attack_pressure=60)
        pred1 = fp.predict(features)
        pred2 = fp2.predict(features)
        self.assertEqual(sorted(pred1), sorted(pred2))


@unittest.skipUnless(_HAS_SKLEARN, "scikit-learn not installed")
class TestFocusPredictorEdgeCases(unittest.TestCase):
    """FocusPredictor のエッジケーステスト."""

    def test_insufficient_data(self) -> None:
        tmpdir = tempfile.mkdtemp()
        path = _create_annotated_corpus(tmpdir, n=10)
        fp = FocusPredictor()
        result = fp.train(data_path=path)
        self.assertIn("error", result)
        self.assertIn("insufficient", result["error"])

    def test_missing_file(self) -> None:
        fp = FocusPredictor()
        result = fp.train(data_path="/nonexistent/path.jsonl")
        self.assertIn("error", result)

    def test_load_nonexistent(self) -> None:
        fp = FocusPredictor()
        loaded = fp.load(path="/nonexistent/model.joblib")
        self.assertFalse(loaded)

    def test_save_untrained_raises(self) -> None:
        fp = FocusPredictor()
        with self.assertRaises(RuntimeError):
            fp.save(path="/tmp/test.joblib")


# ---------------------------------------------------------------------------
# CommentaryEnhancer tests
# ---------------------------------------------------------------------------
class TestCommentaryEnhancer(unittest.TestCase):
    """enhance_prompt_with_focus のテスト."""

    def test_returns_all_keys(self) -> None:
        result = enhance_prompt_with_focus(
            _make_features(), ["king_safety", "attack_pressure"]
        )
        self.assertIn("features", result)
        self.assertIn("focus", result)
        self.assertIn("focus_descriptions", result)
        self.assertIn("suggested_talking_points", result)

    def test_focus_descriptions_correct_keys(self) -> None:
        result = enhance_prompt_with_focus(
            _make_features(), ["king_safety", "piece_activity"]
        )
        self.assertEqual(set(result["focus_descriptions"].keys()),
                         {"king_safety", "piece_activity"})

    def test_talking_points_non_empty(self) -> None:
        result = enhance_prompt_with_focus(
            _make_features(), ["king_safety"]
        )
        self.assertIsInstance(result["suggested_talking_points"], list)
        self.assertTrue(len(result["suggested_talking_points"]) > 0)

    def test_empty_focus_defaults_positional(self) -> None:
        result = enhance_prompt_with_focus(_make_features(), [])
        self.assertEqual(result["focus"], ["positional"])

    def test_all_labels(self) -> None:
        result = enhance_prompt_with_focus(
            _make_features(), list(FOCUS_LABELS)
        )
        self.assertEqual(len(result["focus"]), len(FOCUS_LABELS))
        self.assertEqual(len(result["focus_descriptions"]), len(FOCUS_LABELS))
        self.assertEqual(
            len(result["suggested_talking_points"]), len(FOCUS_LABELS)
        )

    def test_focus_descriptions_constant(self) -> None:
        self.assertEqual(len(FOCUS_DESCRIPTIONS), len(FOCUS_LABELS))
        for lbl in FOCUS_LABELS:
            self.assertIn(lbl, FOCUS_DESCRIPTIONS)


if __name__ == "__main__":
    unittest.main()
