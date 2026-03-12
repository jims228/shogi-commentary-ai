"""Tests for ImportancePredictor and should_explain_position."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from sklearn.ensemble import GradientBoostingRegressor

    _HAS_SKLEARN = True
except ImportError:
    _HAS_SKLEARN = False

from backend.api.services.importance_predictor import (
    ImportancePredictor,
    _features_to_extended_vector,
    _rule_based_importance,
)
from backend.api.services.commentary_enhancer import should_explain_position


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


def _create_importance_corpus(tmpdir: str, n: int = 80) -> str:
    """テスト用のアノテーション済みコーパス (importance付き) を生成."""
    path = os.path.join(tmpdir, "importance_corpus.jsonl")
    with open(path, "w", encoding="utf-8") as f:
        for i in range(n):
            phase = ["opening", "midgame", "endgame"][i % 3]
            ap = (i * 7) % 100
            ks = 50 - (i % 30)
            pa = 40 + (i % 35)
            d_ks = float(i % 10 - 5)
            d_pa = float(i % 8 - 4)
            d_ap = float(i % 6 - 3)
            # importance correlates with tension + phase
            raw = (abs(d_ks) + abs(d_pa) + abs(d_ap)) / 30.0
            if phase == "endgame":
                raw += 0.2
            importance = round(min(1.0, max(0.0, raw)), 2)
            record = {
                "features": {
                    "king_safety": ks,
                    "piece_activity": pa,
                    "attack_pressure": ap,
                    "phase": phase,
                    "ply": i * 5,
                    "move_intent": ["attack", "defense", "development"][i % 3],
                    "tension_delta": {
                        "d_king_safety": d_ks,
                        "d_piece_activity": d_pa,
                        "d_attack_pressure": d_ap,
                    },
                },
                "annotation": {
                    "focus": ["king_safety"],
                    "importance": importance,
                    "depth": "strategic",
                    "style": "neutral",
                },
                "original_text": f"テスト解説文{i}",
                "annotator": "rule-based",
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return path


# ---------------------------------------------------------------------------
# Feature engineering tests
# ---------------------------------------------------------------------------
class TestFeatureEngineering(unittest.TestCase):
    """11次元拡張ベクトルのテスト."""

    def test_vector_length_11(self) -> None:
        vec = _features_to_extended_vector(_make_features())
        self.assertEqual(len(vec), 11)

    def test_tension_magnitude_calculation(self) -> None:
        features = _make_features(tension_delta={
            "d_king_safety": -10.0,
            "d_piece_activity": 5.0,
            "d_attack_pressure": -3.0,
        })
        vec = _features_to_extended_vector(features)
        # tension_magnitude = |10| + |5| + |3| = 18.0
        self.assertAlmostEqual(vec[8], 18.0, places=1)

    def test_is_endgame_flag(self) -> None:
        vec_mid = _features_to_extended_vector(_make_features(phase="midgame"))
        vec_end = _features_to_extended_vector(_make_features(phase="endgame"))
        self.assertEqual(vec_mid[9], 0.0)
        self.assertEqual(vec_end[9], 1.0)

    def test_intent_score_mapping(self) -> None:
        vec_sac = _features_to_extended_vector(_make_features(move_intent="sacrifice"))
        vec_atk = _features_to_extended_vector(_make_features(move_intent="attack"))
        vec_dev = _features_to_extended_vector(_make_features(move_intent="development"))
        vec_none = _features_to_extended_vector(_make_features(move_intent="unknown"))
        self.assertEqual(vec_sac[10], 1.0)
        self.assertEqual(vec_atk[10], 0.7)
        self.assertEqual(vec_dev[10], 0.1)
        self.assertEqual(vec_none[10], 0.0)

    def test_zero_tension_delta(self) -> None:
        vec = _features_to_extended_vector(_make_features())
        self.assertEqual(vec[8], 0.0)  # tension_magnitude


# ---------------------------------------------------------------------------
# Rule-based fallback tests
# ---------------------------------------------------------------------------
class TestRuleBasedImportance(unittest.TestCase):
    """ルールベース重要度推定のテスト."""

    def test_zero_tension_low_importance(self) -> None:
        features = _make_features()
        score = _rule_based_importance(features)
        self.assertLessEqual(score, 0.2)

    def test_high_tension_high_importance(self) -> None:
        features = _make_features(tension_delta={
            "d_king_safety": -15.0,
            "d_piece_activity": 10.0,
            "d_attack_pressure": 5.0,
        })
        score = _rule_based_importance(features)
        self.assertGreater(score, 0.5)

    def test_endgame_boost(self) -> None:
        base = _make_features(phase="midgame")
        endgame = _make_features(phase="endgame")
        score_mid = _rule_based_importance(base)
        score_end = _rule_based_importance(endgame)
        self.assertGreater(score_end, score_mid)

    def test_sacrifice_intent_boost(self) -> None:
        base = _make_features(move_intent="development")
        sac = _make_features(move_intent="sacrifice")
        score_base = _rule_based_importance(base)
        score_sac = _rule_based_importance(sac)
        self.assertGreater(score_sac, score_base)

    def test_clamped_to_0_1(self) -> None:
        features = _make_features(
            phase="endgame",
            move_intent="sacrifice",
            tension_delta={
                "d_king_safety": -50.0,
                "d_piece_activity": 50.0,
                "d_attack_pressure": 50.0,
            },
        )
        score = _rule_based_importance(features)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)


# ---------------------------------------------------------------------------
# ImportancePredictor training tests
# ---------------------------------------------------------------------------
@unittest.skipUnless(_HAS_SKLEARN, "scikit-learn not installed")
class TestImportancePredictorTrain(unittest.TestCase):
    """ImportancePredictor の訓練テスト."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.mkdtemp()
        self._corpus_path = _create_importance_corpus(self._tmpdir, n=80)

    def test_train_returns_expected_keys(self) -> None:
        ip = ImportancePredictor()
        result = ip.train(data_path=self._corpus_path)
        self.assertNotIn("error", result)
        for key in ["n_samples", "mean_importance", "std_importance",
                     "train_r2", "train_mae"]:
            self.assertIn(key, result, f"Missing key: {key}")
        # Minimum performance threshold — catch complete model failure (e.g., circular training)
        self.assertGreater(result["train_r2"], 0.3)

    def test_train_marks_trained(self) -> None:
        ip = ImportancePredictor()
        self.assertFalse(ip.is_trained)
        ip.train(data_path=self._corpus_path)
        self.assertTrue(ip.is_trained)

    def test_train_sample_count(self) -> None:
        ip = ImportancePredictor()
        result = ip.train(data_path=self._corpus_path)
        self.assertEqual(result["n_samples"], 80)

    def test_predict_trained_in_range(self) -> None:
        ip = ImportancePredictor()
        ip.train(data_path=self._corpus_path)
        features = _make_features(
            attack_pressure=60,
            tension_delta={
                "d_king_safety": -10.0,
                "d_piece_activity": 5.0,
                "d_attack_pressure": 15.0,
            },
        )
        pred = ip.predict(features)
        self.assertIsInstance(pred, float)
        self.assertGreaterEqual(pred, 0.0)
        self.assertLessEqual(pred, 1.0)

    def test_predict_untrained_fallback(self) -> None:
        ip = ImportancePredictor()
        self.assertFalse(ip.is_trained)
        features = _make_features(
            tension_delta={
                "d_king_safety": -10.0,
                "d_piece_activity": 5.0,
                "d_attack_pressure": 15.0,
            },
        )
        pred = ip.predict(features)
        expected = _rule_based_importance(features)
        self.assertEqual(pred, expected)

    def test_should_explain_with_threshold(self) -> None:
        ip = ImportancePredictor()
        ip.train(data_path=self._corpus_path)
        high_tension = _make_features(
            phase="endgame",
            move_intent="sacrifice",
            tension_delta={
                "d_king_safety": -20.0,
                "d_piece_activity": 10.0,
                "d_attack_pressure": 15.0,
            },
        )
        low_tension = _make_features()

        # High tension should be explained (low threshold)
        self.assertTrue(ip.should_explain(high_tension, threshold=0.1))
        # Low tension likely shouldn't be explained at high threshold
        self.assertFalse(ip.should_explain(low_tension, threshold=0.9))

    def test_evaluate_returns_cv_metrics(self) -> None:
        ip = ImportancePredictor()
        result = ip.evaluate(data_path=self._corpus_path, n_splits=3)
        self.assertNotIn("error", result)
        for key in ["n_samples", "n_splits", "mean_r2", "std_r2",
                     "mean_mae", "std_mae"]:
            self.assertIn(key, result, f"Missing key: {key}")
        # Minimum performance threshold — catch complete model failure
        self.assertGreater(result["mean_r2"], 0.3)

    def test_save_and_load_roundtrip(self) -> None:
        ip = ImportancePredictor()
        ip.train(data_path=self._corpus_path)

        model_path = os.path.join(self._tmpdir, "test_importance.joblib")
        saved = ip.save(path=model_path)
        self.assertTrue(os.path.exists(saved))

        ip2 = ImportancePredictor()
        self.assertFalse(ip2.is_trained)
        loaded = ip2.load(path=model_path)
        self.assertTrue(loaded)
        self.assertTrue(ip2.is_trained)

        # Predictions should match
        features = _make_features(attack_pressure=60)
        pred1 = ip.predict(features)
        pred2 = ip2.predict(features)
        self.assertAlmostEqual(pred1, pred2, places=4)


# ---------------------------------------------------------------------------
# Edge case tests
# ---------------------------------------------------------------------------
@unittest.skipUnless(_HAS_SKLEARN, "scikit-learn not installed")
class TestImportancePredictorEdgeCases(unittest.TestCase):
    """ImportancePredictor のエッジケーステスト."""

    def test_insufficient_data(self) -> None:
        tmpdir = tempfile.mkdtemp()
        path = _create_importance_corpus(tmpdir, n=10)
        ip = ImportancePredictor()
        result = ip.train(data_path=path)
        self.assertIn("error", result)
        self.assertIn("insufficient", result["error"])

    def test_missing_file(self) -> None:
        ip = ImportancePredictor()
        result = ip.train(data_path="/nonexistent/path.jsonl")
        self.assertIn("error", result)

    def test_load_nonexistent(self) -> None:
        ip = ImportancePredictor()
        loaded = ip.load(path="/nonexistent/model.joblib")
        self.assertFalse(loaded)

    def test_save_untrained_raises(self) -> None:
        ip = ImportancePredictor()
        with self.assertRaises(RuntimeError):
            ip.save(path="/tmp/test_importance.joblib")


# ---------------------------------------------------------------------------
# should_explain_position integration tests
# ---------------------------------------------------------------------------
class TestShouldExplainPosition(unittest.TestCase):
    """commentary_enhancer.should_explain_position のテスト."""

    def test_returns_expected_keys(self) -> None:
        result = should_explain_position(_make_features())
        self.assertIn("should_explain", result)
        self.assertIn("importance", result)
        self.assertIn("reason", result)

    def test_high_tension_returns_true(self) -> None:
        features = _make_features(
            phase="endgame",
            move_intent="sacrifice",
            tension_delta={
                "d_king_safety": -20.0,
                "d_piece_activity": 10.0,
                "d_attack_pressure": 15.0,
            },
        )
        result = should_explain_position(features, threshold=0.3)
        self.assertTrue(result["should_explain"])

    def test_low_tension_returns_false(self) -> None:
        features = _make_features()
        result = should_explain_position(features, threshold=0.9)
        self.assertFalse(result["should_explain"])

    def test_reason_high_tension(self) -> None:
        features = _make_features(tension_delta={
            "d_king_safety": -10.0,
            "d_piece_activity": 5.0,
            "d_attack_pressure": 5.0,
        })
        result = should_explain_position(features)
        self.assertEqual(result["reason"], "high_tension")

    def test_reason_key_move(self) -> None:
        features = _make_features(move_intent="sacrifice")
        result = should_explain_position(features)
        self.assertEqual(result["reason"], "key_move")

    def test_reason_phase_change(self) -> None:
        features = _make_features(phase="endgame", move_intent="development")
        result = should_explain_position(features)
        self.assertEqual(result["reason"], "phase_change")

    def test_reason_routine(self) -> None:
        features = _make_features()
        result = should_explain_position(features)
        self.assertEqual(result["reason"], "routine")


if __name__ == "__main__":
    unittest.main()
