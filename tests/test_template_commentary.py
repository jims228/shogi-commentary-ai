"""テンプレート解説生成器のテスト."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.api.services.template_commentary import generate_template_commentary
from backend.api.services.explanation_evaluator import evaluate_explanation


class TestPhaseTemplates(unittest.TestCase):
    """各phaseで適切なテンプレートが選ばれること."""

    def test_opening_mentions_opening_terms(self):
        features = {"phase": "opening", "king_safety": 60, "attack_pressure": 5}
        text = generate_template_commentary(features, seed=0)
        opening_terms = {"序盤", "駒組み", "陣形"}
        self.assertTrue(
            any(t in text for t in opening_terms),
            f"Opening text should contain opening terms: {text}",
        )

    def test_midgame_mentions_midgame_terms(self):
        features = {"phase": "midgame", "king_safety": 50, "attack_pressure": 30}
        text = generate_template_commentary(features, seed=0)
        midgame_terms = {"中盤", "仕掛け", "戦い"}
        self.assertTrue(
            any(t in text for t in midgame_terms),
            f"Midgame text should contain midgame terms: {text}",
        )

    def test_endgame_mentions_endgame_terms(self):
        features = {"phase": "endgame", "king_safety": 20, "attack_pressure": 60}
        text = generate_template_commentary(features, seed=0)
        endgame_terms = {"終盤", "寄せ"}
        self.assertTrue(
            any(t in text for t in endgame_terms),
            f"Endgame text should contain endgame terms: {text}",
        )


class TestIntentDescriptions(unittest.TestCase):
    """各intentで正しい説明が入ること."""

    def test_attack_intent(self):
        features = {"phase": "midgame", "move_intent": "attack",
                     "king_safety": 50, "attack_pressure": 40}
        text = generate_template_commentary(features, seed=0)
        attack_words = {"攻め", "攻撃", "崩し"}
        self.assertTrue(
            any(w in text for w in attack_words),
            f"Attack text should contain attack words: {text}",
        )

    def test_defense_intent(self):
        features = {"phase": "midgame", "move_intent": "defense",
                     "king_safety": 40, "attack_pressure": 10}
        text = generate_template_commentary(features, seed=0)
        defense_words = {"守り", "受け", "安全", "補強"}
        self.assertTrue(
            any(w in text for w in defense_words),
            f"Defense text should contain defense words: {text}",
        )

    def test_exchange_intent(self):
        features = {"phase": "midgame", "move_intent": "exchange",
                     "king_safety": 50, "attack_pressure": 20}
        text = generate_template_commentary(features, seed=0)
        self.assertIn("交換", text)

    def test_development_intent(self):
        features = {"phase": "opening", "move_intent": "development",
                     "king_safety": 60, "attack_pressure": 0}
        text = generate_template_commentary(features, seed=0)
        dev_words = {"展開", "活用", "配置"}
        self.assertTrue(
            any(w in text for w in dev_words),
            f"Development text should contain development words: {text}",
        )

    def test_sacrifice_intent(self):
        features = {"phase": "endgame", "move_intent": "sacrifice",
                     "king_safety": 30, "attack_pressure": 50}
        text = generate_template_commentary(features, seed=0)
        sac_words = {"犠牲", "捨て"}
        self.assertTrue(
            any(w in text for w in sac_words),
            f"Sacrifice text should contain sacrifice words: {text}",
        )

    def test_none_intent(self):
        features = {"phase": "midgame", "move_intent": None,
                     "king_safety": 50, "attack_pressure": 10}
        text = generate_template_commentary(features, seed=0)
        self.assertGreater(len(text), 0)


class TestTextLength(unittest.TestCase):
    """文字数が適切範囲内であること."""

    def test_minimum_length(self):
        features = {"phase": "opening", "king_safety": 50, "attack_pressure": 0}
        text = generate_template_commentary(features, seed=42)
        self.assertGreaterEqual(len(text), 40, f"Too short: {text}")

    def test_maximum_length(self):
        features = {"phase": "endgame", "king_safety": 10, "attack_pressure": 80,
                     "move_intent": "attack", "piece_activity": 30}
        text = generate_template_commentary(features, seed=42)
        self.assertLessEqual(len(text), 250, f"Too long: {text}")

    def test_various_features_produce_valid_lengths(self):
        """各種特徴量の組み合わせで適切な長さのテキストが生成される."""
        test_cases = [
            {"phase": "opening", "king_safety": 80, "attack_pressure": 0},
            {"phase": "midgame", "king_safety": 40, "attack_pressure": 50},
            {"phase": "endgame", "king_safety": 10, "attack_pressure": 90},
        ]
        for i, features in enumerate(test_cases):
            with self.subTest(i=i):
                text = generate_template_commentary(features, seed=i)
                self.assertGreaterEqual(len(text), 40)
                self.assertLessEqual(len(text), 250)


class TestQualityScores(unittest.TestCase):
    """evaluator でのスコアが40以上であること."""

    def test_opening_score(self):
        features = {"phase": "opening", "king_safety": 60,
                     "attack_pressure": 5, "move_intent": "development"}
        text = generate_template_commentary(features, seed=0)
        result = evaluate_explanation(text, features=features)
        self.assertGreaterEqual(
            result["total"], 40,
            f"Opening score too low: {result}",
        )

    def test_midgame_score(self):
        features = {"phase": "midgame", "king_safety": 45,
                     "attack_pressure": 35, "move_intent": "attack"}
        text = generate_template_commentary(features, seed=0)
        result = evaluate_explanation(text, features=features)
        self.assertGreaterEqual(
            result["total"], 40,
            f"Midgame score too low: {result}",
        )

    def test_endgame_score(self):
        features = {"phase": "endgame", "king_safety": 15,
                     "attack_pressure": 65, "move_intent": "attack"}
        text = generate_template_commentary(features, seed=0)
        result = evaluate_explanation(text, features=features)
        self.assertGreaterEqual(
            result["total"], 40,
            f"Endgame score too low: {result}",
        )

    def test_seed_reproducibility(self):
        """同じseedで同じテキストが生成される."""
        features = {"phase": "midgame", "king_safety": 50, "attack_pressure": 20}
        text1 = generate_template_commentary(features, seed=123)
        text2 = generate_template_commentary(features, seed=123)
        self.assertEqual(text1, text2)

    def test_different_seeds_may_differ(self):
        """異なるseedで異なるテキストが生成される可能性がある."""
        features = {"phase": "midgame", "king_safety": 50, "attack_pressure": 20}
        texts = set()
        for s in range(20):
            texts.add(generate_template_commentary(features, seed=s))
        # 20回で少なくとも2種類は出るはず
        self.assertGreater(len(texts), 1)


if __name__ == "__main__":
    unittest.main()
