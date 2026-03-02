"""Tests for baseline experiment runner and report generation."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _create_experiment_json(exp_dir: str) -> str:
    """Create a realistic experiment JSON file for report testing."""
    os.makedirs(exp_dir, exist_ok=True)
    data = {
        "name": "baseline",
        "timestamp": "2026-03-03T00:00:00+00:00",
        "corpus": {"sample_games": 10, "pipeline_features": 340},
        "phase_distribution": {
            "total": 340,
            "phases": {"opening": 120, "midgame": 140, "endgame": 80},
        },
        "commentary_stats": {
            "training_log_files": 1,
            "training_log_records": 50,
            "batch_commentary_records": 30,
            "quality_evaluation": {
                "total_records": 50,
                "avg_total": 58.5,
                "avg_scores": {
                    "context_relevance": 65.0,
                    "naturalness": 55.0,
                    "informativeness": 50.0,
                    "readability": 60.0,
                },
                "low_quality_count": 5,
                "by_phase": {
                    "opening": 60.0,
                    "midgame": 57.0,
                    "endgame": 55.0,
                },
                "by_intent": {"attack": 58.0, "defense": 56.0},
            },
        },
        "experiment": {
            "name": "baseline",
            "n_samples": 50,
            "n_splits": 5,
            "best_model": "RandomForest",
            "style_distribution": {
                "technical": 20,
                "encouraging": 15,
                "neutral": 15,
            },
            "models": [
                {
                    "name": "DecisionTree",
                    "accuracy_mean": 0.45,
                    "accuracy_std": 0.05,
                    "f1_macro_mean": 0.40,
                    "f1_macro_std": 0.06,
                    "train_time_seconds": 0.01,
                    "feature_importance": {"phase_num": 0.35, "ply": 0.20},
                },
                {
                    "name": "RandomForest",
                    "accuracy_mean": 0.55,
                    "accuracy_std": 0.04,
                    "f1_macro_mean": 0.50,
                    "f1_macro_std": 0.05,
                    "train_time_seconds": 0.12,
                    "feature_importance": {
                        "phase_num": 0.30,
                        "attack_pressure": 0.25,
                    },
                },
                {
                    "name": "GradientBoosting",
                    "accuracy_mean": 0.52,
                    "accuracy_std": 0.03,
                    "f1_macro_mean": 0.48,
                    "f1_macro_std": 0.04,
                    "train_time_seconds": 0.15,
                    "feature_importance": {"ply": 0.28, "phase_num": 0.22},
                },
            ],
        },
        "feature_importance": {
            "n_samples": 50,
            "tree": {
                "phase_num": 0.3500,
                "ply": 0.2000,
                "attack_pressure": 0.1500,
            },
            "permutation": {
                "phase_num": 0.3000,
                "ply": 0.1800,
                "attack_pressure": 0.1200,
            },
            "correlation": {
                "phase_num": 0.2500,
                "ply": 0.2200,
                "attack_pressure": 0.1000,
            },
            "consensus_ranking": [
                ["phase_num", 1.0],
                ["ply", 2.0],
                ["attack_pressure", 3.0],
            ],
        },
        "style_distribution": {
            "n_samples": 50,
            "class_balance": {
                "technical": 36.0,
                "encouraging": 32.0,
                "neutral": 32.0,
            },
            "phase_style_crosstab": {
                "opening": {
                    "technical": 5,
                    "encouraging": 5,
                    "neutral": 4,
                },
                "midgame": {
                    "technical": 8,
                    "encouraging": 5,
                    "neutral": 8,
                },
                "endgame": {
                    "technical": 5,
                    "encouraging": 6,
                    "neutral": 4,
                },
            },
            "warnings": [],
        },
    }
    path = os.path.join(exp_dir, "baseline_20260303_000000.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


class TestReportGeneration(unittest.TestCase):
    """Test report generation from experiment data."""

    def _generate_in_tmpdir(
        self, tmpdir: str, *, create_data: bool = True
    ) -> str:
        """Helper: generate report in a temp directory."""
        exp_dir = os.path.join(tmpdir, "experiments")
        if create_data:
            _create_experiment_json(exp_dir)
        else:
            os.makedirs(exp_dir, exist_ok=True)

        import scripts.generate_report as mod

        orig_exp = mod._EXPERIMENTS_DIR
        orig_rep = mod._REPORTS_DIR
        try:
            mod._EXPERIMENTS_DIR = Path(exp_dir)
            mod._REPORTS_DIR = Path(os.path.join(tmpdir, "reports"))
            name = "baseline" if create_data else "nonexistent"
            return mod.generate_report(experiment_name=name)
        finally:
            mod._EXPERIMENTS_DIR = orig_exp
            mod._REPORTS_DIR = orig_rep

    def test_report_generates_successfully(self) -> None:
        """Report file is created and is non-empty."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self._generate_in_tmpdir(tmpdir)
            self.assertTrue(os.path.exists(result))
            content = Path(result).read_text(encoding="utf-8")
            self.assertGreater(len(content), 100)

    def test_required_sections_present(self) -> None:
        """All 7 required sections are in the report."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self._generate_in_tmpdir(tmpdir)
            content = Path(result).read_text(encoding="utf-8")
            required_sections = [
                "## 1. Project Overview",
                "## 2. Dataset Statistics",
                "## 3. Quality Evaluation",
                "## 4. ML Model Comparison",
                "## 5. Feature Importance",
                "## 6. Style Classification Analysis",
                "## 7. Issues and Next Steps",
            ]
            for section in required_sections:
                self.assertIn(section, content, f"Missing section: {section}")

    def test_numeric_formatting(self) -> None:
        """Numeric values are properly formatted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self._generate_in_tmpdir(tmpdir)
            content = Path(result).read_text(encoding="utf-8")
            # Accuracy formatting (X.XX +/- X.XX)
            self.assertRegex(content, r"0\.\d{2} \+/- 0\.\d{2}")
            # Percentage formatting (X.X%)
            self.assertRegex(content, r"\d+\.\d%")
            # Feature importance formatting (X.XXXX)
            self.assertRegex(content, r"0\.\d{4}")

    def test_fallback_no_experiment_data(self) -> None:
        """Report generates even when no experiment data exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self._generate_in_tmpdir(tmpdir, create_data=False)
            self.assertTrue(os.path.exists(result))
            content = Path(result).read_text(encoding="utf-8")
            self.assertIn("## 1. Project Overview", content)
            self.assertIn("No experiment data found", content)


if __name__ == "__main__":
    unittest.main()
