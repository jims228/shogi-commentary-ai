"""Tests for ML experiment framework."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.api.services.ml_trainer import STYLES

try:
    from sklearn.tree import DecisionTreeClassifier
    _HAS_SKLEARN = True
except ImportError:
    _HAS_SKLEARN = False

from backend.api.services.ml_experiment import ExperimentRunner


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


class TestExperimentRunnerNoSklearn(unittest.TestCase):
    """Tests that check error handling."""

    def test_load_experiment_no_dir(self) -> None:
        runner = ExperimentRunner(experiments_dir="/nonexistent/path")
        result = runner.load_experiment("anything")
        self.assertIsNone(result)

    def test_compare_experiments_empty(self) -> None:
        runner = ExperimentRunner(experiments_dir="/nonexistent/path")
        comp = runner.compare_experiments("a", "b")
        self.assertEqual(comp["experiments"], [])
        self.assertEqual(comp["comparison"], [])


@unittest.skipIf(not _HAS_SKLEARN, "scikit-learn not installed")
class TestExperimentRunner(unittest.TestCase):
    """Full experiment tests."""

    def test_single_model_experiment(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_log_file(tmpdir, n=50)
            runner = ExperimentRunner(
                experiments_dir=os.path.join(tmpdir, "exp")
            )
            result = runner.run_experiment(
                name="test_single",
                model_configs=[{
                    "name": "DT",
                    "class": "DecisionTreeClassifier",
                    "params": {"max_depth": 3},
                }],
                data_path=tmpdir,
                n_splits=3,
            )
            self.assertNotIn("error", result)
            self.assertEqual(len(result["models"]), 1)
            m = result["models"][0]
            self.assertIn("accuracy_mean", m)
            self.assertIn("f1_macro_mean", m)
            self.assertIn("confusion_matrix", m)
            self.assertIn("feature_importance", m)
            self.assertEqual(len(m["feature_importance"]), 8)

    def test_multi_model_experiment(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_log_file(tmpdir, n=50)
            runner = ExperimentRunner(
                experiments_dir=os.path.join(tmpdir, "exp")
            )
            configs = [
                {"name": "DT", "class": "DecisionTreeClassifier",
                 "params": {"max_depth": 3}},
                {"name": "RF", "class": "RandomForestClassifier",
                 "params": {"n_estimators": 10}},
                {"name": "GB", "class": "GradientBoostingClassifier",
                 "params": {"n_estimators": 10}},
            ]
            result = runner.run_experiment(
                "test_multi", configs, tmpdir, n_splits=3
            )
            self.assertNotIn("error", result)
            self.assertEqual(len(result["models"]), 3)
            self.assertIn(result["best_model"], ["DT", "RF", "GB"])

    def test_kfold_consistency(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_log_file(tmpdir, n=50)
            runner = ExperimentRunner(
                experiments_dir=os.path.join(tmpdir, "exp")
            )
            result = runner.run_experiment(
                "test_kfold",
                [{"name": "DT", "class": "DecisionTreeClassifier",
                  "params": {"max_depth": 5}}],
                tmpdir,
                n_splits=5,
            )
            m = result["models"][0]
            self.assertIsInstance(m["accuracy_std"], float)
            self.assertIsInstance(m["f1_macro_std"], float)
            self.assertIsInstance(m["train_time_seconds"], float)

    def test_save_load_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_log_file(tmpdir, n=30)
            exp_dir = os.path.join(tmpdir, "experiments")
            runner = ExperimentRunner(experiments_dir=exp_dir)
            result = runner.run_experiment(
                "roundtrip_test",
                [{"name": "DT", "class": "DecisionTreeClassifier",
                  "params": {}}],
                tmpdir,
                n_splits=3,
            )
            path = runner.save_experiment(result)
            self.assertTrue(os.path.exists(path))

            loaded = runner.load_experiment("roundtrip_test")
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded["name"], "roundtrip_test")
            self.assertEqual(loaded["n_samples"], result["n_samples"])
            self.assertEqual(len(loaded["models"]), 1)

    def test_compare_experiments(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_log_file(tmpdir, n=30)
            exp_dir = os.path.join(tmpdir, "experiments")
            runner = ExperimentRunner(experiments_dir=exp_dir)

            r1 = runner.run_experiment(
                "exp_a",
                [{"name": "DT", "class": "DecisionTreeClassifier",
                  "params": {}}],
                tmpdir,
                n_splits=3,
            )
            runner.save_experiment(r1)

            r2 = runner.run_experiment(
                "exp_b",
                [{"name": "RF", "class": "RandomForestClassifier",
                  "params": {"n_estimators": 10}}],
                tmpdir,
                n_splits=3,
            )
            runner.save_experiment(r2)

            comp = runner.compare_experiments("exp_a", "exp_b")
            self.assertEqual(len(comp["experiments"]), 2)
            self.assertEqual(len(comp["comparison"]), 2)
            for c in comp["comparison"]:
                self.assertIn("best_f1_macro", c)
                self.assertIn("best_accuracy", c)

    def test_unknown_model_class(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_log_file(tmpdir, n=30)
            runner = ExperimentRunner()
            result = runner.run_experiment(
                "test_bad",
                [{"name": "bad", "class": "NonexistentClassifier",
                  "params": {}}],
                tmpdir,
            )
            self.assertIn("error", result)
            self.assertIn("NonexistentClassifier", result["error"])

    def test_insufficient_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Empty dir — no log files
            runner = ExperimentRunner()
            result = runner.run_experiment(
                "test_empty",
                [{"name": "DT", "class": "DecisionTreeClassifier",
                  "params": {}}],
                tmpdir,
            )
            self.assertIn("error", result)


if __name__ == "__main__":
    unittest.main()
