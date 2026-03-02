#!/usr/bin/env python3
"""Baseline experiment runner - full pipeline end-to-end.

Usage:
    python scripts/run_baseline.py
    python scripts/run_baseline.py --data-path data/training_logs --cv-folds 5
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

_DATA_DIR = _PROJECT_ROOT / "data"


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------
def _count_lines(path: Path) -> int:
    """ファイルの有効行数を数える (空行・コメント行除外)."""
    if not path.exists():
        return 0
    count = 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                count += 1
    return count


def _count_jsonl(path: Path) -> int:
    """JSONLファイルのレコード数を数える."""
    if not path.exists():
        return 0
    count = 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                count += 1
    return count


# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------
def step1_corpus_check() -> Dict[str, Any]:
    """Step 1: Count games and positions."""
    game_count = _count_lines(_DATA_DIR / "sample_games.txt")
    features_count = _count_jsonl(_DATA_DIR / "pipeline_test_features.jsonl")
    result = {
        "sample_games": game_count,
        "pipeline_features": features_count,
    }
    print(f"\n  [Step 1] Corpus Check")
    print(f"  Sample games:      {game_count} games")
    print(f"  Pipeline features: {features_count} positions")
    return result


def step2_phase_distribution() -> Dict[str, Any]:
    """Step 2: Phase distribution from pipeline features."""
    features_path = _DATA_DIR / "pipeline_test_features.jsonl"
    if not features_path.exists():
        print(f"\n  [Step 2] Phase Distribution - SKIPPED (no features file)")
        return {"total": 0, "phases": {}}

    counts: Counter[str] = Counter()
    total = 0
    with open(features_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                counts[obj.get("phase", "unknown")] += 1
                total += 1
            except Exception:
                continue

    result = {"total": total, "phases": dict(counts)}
    print(f"\n  [Step 2] Phase Distribution ({total} positions)")
    for phase in ["opening", "midgame", "endgame"]:
        count = counts.get(phase, 0)
        pct = f"{count / total * 100:.1f}%" if total else "0%"
        print(f"    {phase:<12} {count:>4} ({pct})")
    return result


def step3_commentary_stats() -> Dict[str, Any]:
    """Step 3: Commentary and quality stats."""
    from backend.api.services.training_logger import TrainingLogger
    from backend.api.services.explanation_evaluator import evaluate_training_logs

    logger = TrainingLogger()
    stats = logger.get_stats()
    log_files = stats.get("files", [])
    total_records = sum(f.get("records", 0) for f in log_files)

    batch_path = _DATA_DIR / "batch_commentary" / "batch_commentary.jsonl"
    batch_count = _count_jsonl(batch_path)

    result: Dict[str, Any] = {
        "training_log_files": len(log_files),
        "training_log_records": total_records,
        "batch_commentary_records": batch_count,
    }

    print(f"\n  [Step 3] Commentary & Quality Stats")
    print(f"  Training log files:  {len(log_files)} files, {total_records} records")
    print(f"  Batch commentary:    {batch_count} records")

    log_dir = stats.get("log_dir", "")
    if total_records > 0 and log_dir:
        eval_stats = evaluate_training_logs(log_dir)
        result["quality_evaluation"] = eval_stats
        if eval_stats.get("total_records", 0) > 0:
            print(f"  Avg quality score:   {eval_stats.get('avg_total', 0)}")
            print(f"  Low quality (<40):   {eval_stats.get('low_quality_count', 0)}")
            avg_scores = eval_stats.get("avg_scores", {})
            for axis, val in avg_scores.items():
                print(f"    {axis:<22} {val}")
    return result


def step4_model_training(
    data_path: Optional[str] = None,
    n_splits: int = 5,
) -> Dict[str, Any]:
    """Step 4: Run 3-model k-fold CV experiment."""
    from backend.api.services.ml_experiment import ExperimentRunner

    model_configs = [
        {
            "name": "DecisionTree",
            "class": "DecisionTreeClassifier",
            "params": {"max_depth": 5},
        },
        {
            "name": "RandomForest",
            "class": "RandomForestClassifier",
            "params": {"n_estimators": 100, "max_depth": 8},
        },
        {
            "name": "GradientBoosting",
            "class": "GradientBoostingClassifier",
            "params": {"n_estimators": 100, "max_depth": 5, "learning_rate": 0.1},
        },
    ]

    runner = ExperimentRunner()
    result = runner.run_experiment(
        name="baseline",
        model_configs=model_configs,
        data_path=data_path,
        n_splits=n_splits,
    )

    if result.get("error"):
        print(f"\n  [Step 4] Model Training - ERROR: {result['error']}")
        return result

    print(
        f"\n  [Step 4] Model Training "
        f"({result['n_samples']} samples, {result['n_splits']}-fold CV)"
    )
    print(f"  {'Model':<22} {'Accuracy':>12} {'F1-macro':>12} {'Time(s)':>10}")
    print(f"  {'─' * 58}")
    for m in result.get("models", []):
        acc = f"{m['accuracy_mean']:.2f}±{m['accuracy_std']:.2f}"
        f1 = f"{m['f1_macro_mean']:.2f}±{m['f1_macro_std']:.2f}"
        t = f"{m['train_time_seconds']:.2f}"
        marker = " *" if m["name"] == result.get("best_model") else ""
        print(f"  {m['name']:<22} {acc:>12} {f1:>12} {t:>10}{marker}")

    path = runner.save_experiment(result)
    print(f"  Saved: {path}")
    return result


def step5_feature_importance(
    data_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Step 5: Feature importance analysis (3 methods)."""
    from backend.api.services.ml_analysis import analyze_feature_importance

    result = analyze_feature_importance(data_path=data_path, method="all")
    if result.get("error"):
        print(f"\n  [Step 5] Feature Importance - ERROR: {result['error']}")
        return result

    print(
        f"\n  [Step 5] Feature Importance Analysis "
        f"({result.get('n_samples', 0)} samples)"
    )
    ranking = result.get("consensus_ranking", [])
    if ranking:
        print("  Consensus Ranking:")
        for feat, avg_rank in ranking:
            print(f"    {feat:<22} rank {avg_rank:.1f}")
    return result


def step6_style_distribution(
    data_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Step 6: Style distribution analysis."""
    from backend.api.services.ml_analysis import analyze_style_distribution
    from backend.api.services.ml_trainer import STYLES

    result = analyze_style_distribution(data_path=data_path)

    print(f"\n  [Step 6] Style Distribution ({result.get('n_samples', 0)} samples)")
    balance = result.get("class_balance", {})
    for style in STYLES:
        pct = balance.get(style, 0)
        print(f"    {style:<14} {pct:.1f}%")
    for w in result.get("warnings", []):
        print(f"    Warning: {w}")
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def run_baseline(
    data_path: Optional[str] = None,
    n_splits: int = 5,
) -> Dict[str, Any]:
    """Run full baseline experiment."""
    print()
    print("=" * 60)
    print("  Shogi Commentary AI - Baseline Experiment")
    print("=" * 60)
    start = time.time()

    results: Dict[str, Any] = {
        "name": "baseline",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    results["corpus"] = step1_corpus_check()
    results["phase_distribution"] = step2_phase_distribution()
    results["commentary_stats"] = step3_commentary_stats()
    results["experiment"] = step4_model_training(data_path, n_splits)
    results["feature_importance"] = step5_feature_importance(data_path)
    results["style_distribution"] = step6_style_distribution(data_path)

    results["elapsed_sec"] = round(time.time() - start, 2)

    # Save combined results
    exp_dir = _DATA_DIR / "experiments"
    exp_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = exp_dir / f"baseline_full_{ts}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print()
    print("=" * 60)
    print(f"  Baseline complete in {results['elapsed_sec']}s")
    print(f"  Results saved: {out_path}")
    print("=" * 60)
    print()
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run baseline experiment (full pipeline)"
    )
    parser.add_argument("--data-path", default=None, help="Training log directory")
    parser.add_argument("--cv-folds", type=int, default=5, help="CV folds (default: 5)")
    args = parser.parse_args()
    run_baseline(data_path=args.data_path, n_splits=args.cv_folds)
