#!/usr/bin/env python3
"""ML実験実行CLI.

Usage:
    python scripts/run_experiment.py --name baseline
    python scripts/run_experiment.py --analysis-only
    python scripts/run_experiment.py --compare baseline custom
    python scripts/run_experiment.py --name custom --models RandomForest GradientBoosting --cv-folds 5
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from backend.api.services.ml_experiment import ExperimentRunner  # noqa: E402
from backend.api.services.ml_analysis import (  # noqa: E402
    analyze_feature_importance,
    analyze_style_distribution,
    generate_analysis_report,
)
from backend.api.services.ml_trainer import STYLES  # noqa: E402

# -----------------------------------------------------------------------
# Model shorthand → config
# -----------------------------------------------------------------------
_MODEL_SHORTHAND: Dict[str, Dict[str, Any]] = {
    "DecisionTree": {
        "name": "DecisionTree",
        "class": "DecisionTreeClassifier",
        "params": {"max_depth": 5},
    },
    "RandomForest": {
        "name": "RandomForest",
        "class": "RandomForestClassifier",
        "params": {"n_estimators": 100, "max_depth": 8},
    },
    "GradientBoosting": {
        "name": "GradientBoosting",
        "class": "GradientBoostingClassifier",
        "params": {"n_estimators": 100, "max_depth": 5, "learning_rate": 0.1},
    },
}


# -----------------------------------------------------------------------
# ASCII output helpers
# -----------------------------------------------------------------------
def _importance_bar(value: float, max_val: float, width: int = 20) -> str:
    if max_val <= 0:
        return "░" * width
    filled = int(value / max_val * width)
    return "█" * filled + "░" * (width - filled)


def print_experiment_results(result: Dict[str, Any]) -> None:
    """実験結果をASCIIテーブルで表示."""
    print()
    print("=" * 64)
    print(f"  Experiment: {result['name']}")
    print(f"  Date: {result.get('timestamp', 'unknown')}")
    print(f"  Data: {result['n_samples']} samples, 8 features, {len(STYLES)} classes")
    print(f"  CV folds: {result.get('n_splits', '?')}")
    print()

    # Style distribution
    dist = result.get("style_distribution", {})
    total = sum(dist.values())
    if total > 0:
        print("  Style Distribution:")
        for style in STYLES:
            count = dist.get(style, 0)
            pct = count / total * 100
            bar = _importance_bar(count, total, 30)
            print(f"    {style:<14} {bar} {count:>4} ({pct:.0f}%)")
        # Imbalance warning
        for style in STYLES:
            pct = dist.get(style, 0) / total * 100
            if pct < 10:
                print(f"    ⚠ Class imbalance detected ({style}: {pct:.0f}%)")
        print()

    # Model comparison table
    print("  Model Comparison:")
    print(f"  {'Model':<22} {'Accuracy':>12} {'F1-macro':>12} {'Time(s)':>10}")
    print(f"  {'─' * 58}")

    models = result.get("models", [])
    best_name = result.get("best_model", "")

    for m in models:
        acc = f"{m['accuracy_mean']:.2f}±{m['accuracy_std']:.2f}"
        f1 = f"{m['f1_macro_mean']:.2f}±{m['f1_macro_std']:.2f}"
        t = f"{m['train_time_seconds']:.2f}"
        marker = " ★" if m["name"] == best_name else ""
        print(f"  {m['name']:<22} {acc:>12} {f1:>12} {t:>10}{marker}")

    print(f"  {'─' * 58}")
    if best_name:
        best_m = next((m for m in models if m["name"] == best_name), None)
        if best_m:
            print(
                f"  Best: {best_name} "
                f"(F1-macro: {best_m['f1_macro_mean']:.3f})"
            )
    print()

    # Feature importance for best model
    if best_name:
        best_m = next((m for m in models if m["name"] == best_name), None)
        if best_m and best_m.get("feature_importance"):
            print_feature_importance(best_m["feature_importance"])


def print_feature_importance(importance: Dict[str, float]) -> None:
    """特徴量重要度をASCIIバーで表示."""
    if not importance:
        return
    print("  Feature Importance:")
    sorted_feats = sorted(importance.items(), key=lambda x: -x[1])
    max_val = max(importance.values()) if importance else 1.0
    for feat, val in sorted_feats:
        bar = _importance_bar(val, max_val, 20)
        print(f"    {feat:<22} {bar}  {val:.4f}")
    print()


def print_comparison_table(comparison: Dict[str, Any]) -> None:
    """実験間比較テーブルを表示."""
    print()
    print("=" * 64)
    print("  Experiment Comparison")
    print("=" * 64)

    entries = comparison.get("comparison", [])
    if not entries:
        print("  No experiments found.")
        print()
        return

    print(f"  {'Experiment':<22} {'Samples':>8} {'Best Model':<18} {'F1':>6} {'Acc':>6}")
    print(f"  {'─' * 62}")
    for e in entries:
        print(
            f"  {e['experiment_name']:<22} "
            f"{e['n_samples']:>8} "
            f"{e['best_model']:<18} "
            f"{e['best_f1_macro']:>6.3f} "
            f"{e['best_accuracy']:>6.3f}"
        )
    print("=" * 64)
    print()


def print_analysis(importance: Dict[str, Any], distribution: Dict[str, Any]) -> None:
    """分析結果をASCIIで表示."""
    print()
    print("=" * 64)
    print("  Feature Importance Analysis")
    print("=" * 64)

    # Consensus ranking
    ranking = importance.get("consensus_ranking", [])
    if ranking:
        print()
        print("  Consensus Ranking:")
        max_rank = max(r for _, r in ranking) if ranking else 1
        for feat, avg_rank in ranking:
            bar = _importance_bar(max_rank - avg_rank + 1, max_rank, 20)
            print(f"    {feat:<22} {bar}  rank {avg_rank:.1f}")

    # Per-method
    for method_key, title in [
        ("tree", "Tree-based (RandomForest)"),
        ("permutation", "Permutation"),
        ("correlation", "Correlation (|r|)"),
    ]:
        imp = importance.get(method_key)
        if imp is None:
            continue
        print()
        print(f"  {title}:")
        sorted_imp = sorted(imp.items(), key=lambda x: -x[1])
        max_val = max(imp.values()) if imp else 1.0
        for feat, val in sorted_imp:
            bar = _importance_bar(val, max_val, 20)
            print(f"    {feat:<22} {bar}  {val:.4f}")

    # Style distribution
    print()
    print("=" * 64)
    print("  Style Distribution Analysis")
    print("=" * 64)

    balance = distribution.get("class_balance", {})
    if balance:
        print()
        print("  Class Balance:")
        for style in STYLES:
            pct = balance.get(style, 0)
            bar = _importance_bar(pct, 100, 30)
            print(f"    {style:<14} {bar} {pct:.1f}%")

    warnings = distribution.get("warnings", [])
    for w in warnings:
        print(f"    ⚠ {w}")

    print()
    print("=" * 64)
    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ML experiment runner for style selector"
    )
    parser.add_argument("--name", type=str, default=None, help="実験名")
    parser.add_argument(
        "--models",
        nargs="*",
        default=None,
        help="モデル: DecisionTree, RandomForest, GradientBoosting (default: all)",
    )
    parser.add_argument(
        "--cv-folds", type=int, default=5, help="CV折り数 (default: 5)"
    )
    parser.add_argument(
        "--data-path", type=str, default=None, help="トレーニングログディレクトリ"
    )
    parser.add_argument(
        "--analysis-only",
        action="store_true",
        help="特徴量分析のみ実行",
    )
    parser.add_argument(
        "--compare",
        nargs="*",
        default=None,
        help="過去実験の比較",
    )
    args = parser.parse_args()

    # --- Compare mode ---
    if args.compare:
        runner = ExperimentRunner()
        comp = runner.compare_experiments(*args.compare)
        print_comparison_table(comp)
        return

    # --- Analysis-only mode ---
    if args.analysis_only:
        importance = analyze_feature_importance(data_path=args.data_path)
        if importance.get("error"):
            print(f"Error: {importance['error']}", file=sys.stderr)
            sys.exit(1)
        distribution = analyze_style_distribution(data_path=args.data_path)
        print_analysis(importance, distribution)

        # Also save markdown report
        report = generate_analysis_report(importance, distribution)
        report_path = _PROJECT_ROOT / "data" / "experiments" / "analysis_report.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report, encoding="utf-8")
        print(f"  Report saved: {report_path}")
        return

    # --- Experiment mode ---
    name = args.name or f"experiment_{datetime.now().strftime('%Y%m%d')}"
    models_list = args.models or ["DecisionTree", "RandomForest", "GradientBoosting"]

    # Validate model names
    for m in models_list:
        if m not in _MODEL_SHORTHAND:
            print(
                f"Error: Unknown model '{m}'. "
                f"Available: {list(_MODEL_SHORTHAND.keys())}",
                file=sys.stderr,
            )
            sys.exit(1)

    model_configs = [_MODEL_SHORTHAND[m] for m in models_list]

    runner = ExperimentRunner()
    result = runner.run_experiment(
        name, model_configs, args.data_path, args.cv_folds
    )

    if result.get("error"):
        print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)

    print_experiment_results(result)

    # Save
    path = runner.save_experiment(result)
    print(f"  Saved: {path}")
    print()


if __name__ == "__main__":
    main()
