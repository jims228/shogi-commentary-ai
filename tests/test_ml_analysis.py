"""Tests for ML feature importance and style distribution analysis."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.api.services.ml_trainer import STYLES, _FEATURE_KEYS

try:
    from sklearn.tree import DecisionTreeClassifier
    _HAS_SKLEARN = True
except ImportError:
    _HAS_SKLEARN = False

from backend.api.services.ml_analysis import (
    analyze_feature_importance,
    analyze_style_distribution,
    generate_analysis_report,
)


def _create_log_file(tmpdir: str, n: int = 50) -> str:
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
                    "explanation": (
                        f"序盤の駒組みが進み、銀が活用されています。"
                        f"攻めの形を整えつつ、守りも固めていく展開です。手番{i}。"
                    ),
                    "model": "test",
                },
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return path


class TestAnalysisNoSklearn(unittest.TestCase):
    """Tests that work without scikit-learn (correlation only)."""

    def test_correlation_method_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_log_file(tmpdir, n=50)
            result = analyze_feature_importance(
                data_path=tmpdir, method="correlation"
            )
            self.assertIsNotNone(result.get("correlation"))
            self.assertEqual(len(result["correlation"]), len(_FEATURE_KEYS))
            self.assertIsNotNone(result.get("feature_correlation_matrix"))
            matrix = result["feature_correlation_matrix"]
            self.assertEqual(len(matrix), len(_FEATURE_KEYS))
            self.assertEqual(len(matrix[0]), len(_FEATURE_KEYS))


@unittest.skipIf(not _HAS_SKLEARN, "scikit-learn not installed")
class TestFeatureImportance(unittest.TestCase):
    """Feature importance analysis tests."""

    def test_tree_importance(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_log_file(tmpdir, n=50)
            result = analyze_feature_importance(
                data_path=tmpdir, method="tree"
            )
            self.assertNotIn("error", result)
            self.assertIsNotNone(result["tree"])
            self.assertEqual(len(result["tree"]), len(_FEATURE_KEYS))
            for v in result["tree"].values():
                self.assertIsInstance(v, float)

    def test_permutation_importance(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_log_file(tmpdir, n=50)
            result = analyze_feature_importance(
                data_path=tmpdir, method="permutation"
            )
            self.assertNotIn("error", result)
            self.assertIsNotNone(result["permutation"])
            self.assertEqual(len(result["permutation"]), len(_FEATURE_KEYS))

    def test_all_methods_with_consensus(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_log_file(tmpdir, n=50)
            result = analyze_feature_importance(
                data_path=tmpdir, method="all"
            )
            self.assertNotIn("error", result)
            self.assertIsNotNone(result["tree"])
            self.assertIsNotNone(result["permutation"])
            self.assertIsNotNone(result["correlation"])
            ranking = result["consensus_ranking"]
            self.assertEqual(len(ranking), len(_FEATURE_KEYS))
            # Rankings should be sorted ascending by avg rank
            avg_ranks = [r[1] for r in ranking]
            self.assertEqual(avg_ranks, sorted(avg_ranks))


@unittest.skipIf(not _HAS_SKLEARN, "scikit-learn not installed")
class TestStyleDistribution(unittest.TestCase):
    """Style distribution analysis tests."""

    def test_crosstab_structure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_log_file(tmpdir, n=50)
            result = analyze_style_distribution(data_path=tmpdir)
            self.assertGreater(result["n_samples"], 0)
            crosstab = result["phase_style_crosstab"]
            self.assertIsInstance(crosstab, dict)
            for phase_counts in crosstab.values():
                for style in STYLES:
                    self.assertIn(style, phase_counts)

    def test_class_balance(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_log_file(tmpdir, n=50)
            result = analyze_style_distribution(data_path=tmpdir)
            balance = result["class_balance"]
            total = sum(balance.values())
            self.assertAlmostEqual(total, 100.0, places=0)

    def test_imbalance_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Generate data likely to have imbalanced styles
            _create_log_file(tmpdir, n=50)
            result = analyze_style_distribution(data_path=tmpdir)
            # Warnings should be a list (may or may not be empty)
            self.assertIsInstance(result["warnings"], list)

    def test_per_style_feature_means(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_log_file(tmpdir, n=50)
            result = analyze_style_distribution(data_path=tmpdir)
            means = result["per_style_feature_means"]
            for style in STYLES:
                self.assertIn(style, means)
                for feat in _FEATURE_KEYS:
                    self.assertIn(feat, means[style])


@unittest.skipIf(not _HAS_SKLEARN, "scikit-learn not installed")
class TestAnalysisReport(unittest.TestCase):
    """Report generation tests."""

    def test_report_contains_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_log_file(tmpdir, n=50)
            importance = analyze_feature_importance(
                data_path=tmpdir, method="all"
            )
            distribution = analyze_style_distribution(data_path=tmpdir)
            report = generate_analysis_report(importance, distribution)
            self.assertIsInstance(report, str)
            self.assertIn("# Feature Importance Analysis", report)
            self.assertIn("## Consensus Ranking", report)
            self.assertIn("# Style Distribution", report)
            self.assertIn("## Class Balance", report)
            self.assertIn("## Phase x Style Cross-tabulation", report)
            self.assertIn("## Per-Style Feature Means", report)


if __name__ == "__main__":
    unittest.main()
