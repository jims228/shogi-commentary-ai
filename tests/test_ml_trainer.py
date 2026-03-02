"""tests for backend.api.services.ml_trainer."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from typing import Any, Dict

from backend.api.services.ml_trainer import (
    STYLES,
    CommentaryStyleSelector,
    _HAS_SKLEARN,
    _features_to_vector,
    label_style_from_scores,
    rule_based_predict,
)


# ---------------------------------------------------------------------------
# rule_based_predict
# ---------------------------------------------------------------------------
class TestRuleBasedPredict(unittest.TestCase):
    def test_technical_high_attack_pressure(self) -> None:
        f = {"phase": "midgame", "attack_pressure": 55, "king_safety": 30, "piece_activity": 40}
        self.assertEqual(rule_based_predict(f), "technical")

    def test_technical_endgame_moderate_pressure(self) -> None:
        f = {"phase": "endgame", "attack_pressure": 35, "king_safety": 20, "piece_activity": 40}
        self.assertEqual(rule_based_predict(f), "technical")

    def test_technical_midgame_high_activity(self) -> None:
        f = {"phase": "midgame", "attack_pressure": 20, "king_safety": 40, "piece_activity": 60}
        self.assertEqual(rule_based_predict(f), "technical")

    def test_encouraging_opening(self) -> None:
        f = {"phase": "opening", "attack_pressure": 5, "king_safety": 50, "piece_activity": 40}
        self.assertEqual(rule_based_predict(f), "encouraging")

    def test_encouraging_high_safety(self) -> None:
        f = {"phase": "midgame", "attack_pressure": 10, "king_safety": 65, "piece_activity": 30}
        self.assertEqual(rule_based_predict(f), "encouraging")

    def test_neutral_fallback(self) -> None:
        f = {"phase": "midgame", "attack_pressure": 20, "king_safety": 40, "piece_activity": 30}
        self.assertEqual(rule_based_predict(f), "neutral")


# ---------------------------------------------------------------------------
# label_style_from_scores
# ---------------------------------------------------------------------------
class TestLabelStyleFromScores(unittest.TestCase):
    def test_technical_high_informativeness(self) -> None:
        scores = {"informativeness": 75, "naturalness": 50, "context_relevance": 50, "readability": 50}
        f = {"phase": "midgame", "attack_pressure": 20}
        self.assertEqual(label_style_from_scores(scores, f), "technical")

    def test_neutral_moderate_pressure_and_context(self) -> None:
        scores = {"informativeness": 50, "naturalness": 50, "context_relevance": 75, "readability": 50}
        f = {"phase": "endgame", "attack_pressure": 50}
        self.assertEqual(label_style_from_scores(scores, f), "neutral")

    def test_encouraging_natural_low_pressure(self) -> None:
        scores = {"informativeness": 50, "naturalness": 75, "context_relevance": 50, "readability": 60}
        f = {"phase": "opening", "attack_pressure": 10}
        self.assertEqual(label_style_from_scores(scores, f), "encouraging")

    def test_neutral_default(self) -> None:
        scores = {"informativeness": 50, "naturalness": 50, "context_relevance": 50, "readability": 50}
        f = {"phase": "midgame", "attack_pressure": 20}
        self.assertEqual(label_style_from_scores(scores, f), "neutral")


# ---------------------------------------------------------------------------
# _features_to_vector
# ---------------------------------------------------------------------------
class TestFeaturesToVector(unittest.TestCase):
    def test_vector_length(self) -> None:
        f: Dict[str, Any] = {
            "king_safety": 50,
            "piece_activity": 60,
            "attack_pressure": 20,
            "ply": 30,
            "phase": "midgame",
            "tension_delta": {
                "d_king_safety": -5.0,
                "d_piece_activity": 3.0,
                "d_attack_pressure": 2.0,
            },
        }
        vec = _features_to_vector(f)
        self.assertEqual(len(vec), 8)
        self.assertEqual(vec[0], 50.0)  # king_safety
        self.assertEqual(vec[7], 1.0)   # midgame = 1

    def test_defaults_for_missing_keys(self) -> None:
        vec = _features_to_vector({})
        self.assertEqual(len(vec), 8)
        self.assertEqual(vec[0], 50.0)  # default king_safety
        self.assertEqual(vec[2], 0.0)   # default attack_pressure
        self.assertEqual(vec[7], 1.0)   # default phase = midgame


# ---------------------------------------------------------------------------
# CommentaryStyleSelector
# ---------------------------------------------------------------------------
class TestCommentaryStyleSelector(unittest.TestCase):
    def test_untrained_uses_rule_based(self) -> None:
        sel = CommentaryStyleSelector()
        self.assertFalse(sel.is_trained)
        f = {"phase": "opening", "attack_pressure": 5, "king_safety": 50, "piece_activity": 40}
        result = sel.predict(f)
        self.assertIn(result, STYLES)
        self.assertEqual(result, rule_based_predict(f))

    def test_predict_returns_valid_style(self) -> None:
        sel = CommentaryStyleSelector()
        for phase in ["opening", "midgame", "endgame"]:
            for ap in [0, 30, 60]:
                f = {"phase": phase, "attack_pressure": ap, "king_safety": 50, "piece_activity": 50}
                self.assertIn(sel.predict(f), STYLES)

    def test_train_insufficient_samples(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            sel = CommentaryStyleSelector()
            result = sel.train(log_dir=tmpdir)
            self.assertEqual(result["samples"], 0)
            self.assertIn("error", result)

    def test_train_no_dir(self) -> None:
        sel = CommentaryStyleSelector()
        result = sel.train(log_dir="/nonexistent/path")
        self.assertEqual(result["samples"], 0)


@unittest.skipIf(not _HAS_SKLEARN, "scikit-learn not installed")
class TestCommentaryStyleSelectorML(unittest.TestCase):
    """sklearn が利用可能な場合のMLテスト."""

    def _create_log_file(self, tmpdir: str, n: int = 30) -> str:
        """テスト用のトレーニングログを生成."""
        path = os.path.join(tmpdir, "explanations_test.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            for i in range(n):
                phase = ["opening", "midgame", "endgame"][i % 3]
                ap = (i * 7) % 100
                record = {
                    "type": "explanation",
                    "input": {
                        "sfen": "position startpos",
                        "ply": i * 5,
                        "features": {
                            "king_safety": 50 - (i % 20),
                            "piece_activity": 40 + (i % 30),
                            "attack_pressure": ap,
                            "phase": phase,
                            "ply": i * 5,
                            "tension_delta": {
                                "d_king_safety": float(i % 10 - 5),
                                "d_piece_activity": float(i % 8 - 4),
                                "d_attack_pressure": float(i % 6 - 3),
                            },
                        },
                    },
                    "output": {
                        "explanation": f"序盤の駒組みが進み、銀が活用されています。攻めの形を整えつつ、守りも固めていく展開です。手番{i}。",
                        "model": "test",
                    },
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return path

    def test_train_and_predict(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            self._create_log_file(tmpdir, n=30)
            sel = CommentaryStyleSelector()
            result = sel.train(log_dir=tmpdir)
            self.assertNotIn("error", result)
            self.assertGreaterEqual(result["samples"], 10)
            self.assertTrue(sel.is_trained)

            f = {"phase": "midgame", "attack_pressure": 60, "king_safety": 30, "piece_activity": 50}
            style = sel.predict(f)
            self.assertIn(style, STYLES)

    def test_save_and_load(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            self._create_log_file(tmpdir, n=30)
            sel = CommentaryStyleSelector()
            sel.train(log_dir=tmpdir)
            self.assertTrue(sel.is_trained)

            model_path = os.path.join(tmpdir, "model.joblib")
            sel.save(model_path)
            self.assertTrue(os.path.exists(model_path))

            sel2 = CommentaryStyleSelector()
            self.assertFalse(sel2.is_trained)
            loaded = sel2.load(model_path)
            self.assertTrue(loaded)
            self.assertTrue(sel2.is_trained)

            # Same predictions
            f = {"phase": "endgame", "attack_pressure": 70, "king_safety": 20, "piece_activity": 40}
            self.assertEqual(sel.predict(f), sel2.predict(f))

    def test_accuracy_reasonable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            self._create_log_file(tmpdir, n=50)
            sel = CommentaryStyleSelector()
            result = sel.train(log_dir=tmpdir)
            # Training accuracy should be reasonable
            self.assertGreater(result["accuracy"], 0.5)
            # Distribution should have all styles
            self.assertIn("distribution", result)


if __name__ == "__main__":
    unittest.main()
