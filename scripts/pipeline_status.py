#!/usr/bin/env python3
"""ML パイプラインの状況ダッシュボード.

Usage:
    python scripts/pipeline_status.py
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

_DATA_DIR = _PROJECT_ROOT / "data"


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


def _load_phase_distribution(path: Path) -> dict:
    """pipeline_test_features.jsonl からフェーズ分布を取得."""
    if not path.exists():
        return {}
    counts: Counter = Counter()
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                counts[obj.get("phase", "unknown")] += 1
            except Exception:
                continue
    return dict(counts)


def main() -> None:
    print()
    print("=" * 56)
    print("  Shogi Commentary AI - Pipeline Status")
    print("=" * 56)

    # --- Data Sources ---
    print()
    print("  [Data Sources]")

    game_count = _count_lines(_DATA_DIR / "sample_games.txt")
    print(f"  Sample games:           {game_count} games")

    benchmark_count = 0
    benchmark_path = _DATA_DIR / "benchmark_positions.json"
    if benchmark_path.exists():
        try:
            with open(benchmark_path, encoding="utf-8") as f:
                benchmark_count = len(json.load(f))
        except Exception:
            pass
    print(f"  Benchmark positions:    {benchmark_count} positions")

    features_path = _DATA_DIR / "pipeline_test_features.jsonl"
    features_count = _count_jsonl(features_path)
    print(f"  Pipeline features:      {features_count} records")

    if features_count > 0:
        phase_dist = _load_phase_distribution(features_path)
        for phase in ["opening", "midgame", "endgame"]:
            count = phase_dist.get(phase, 0)
            pct = f"{count / features_count * 100:.0f}%" if features_count else "0%"
            print(f"    {phase:<12} {count:>4} ({pct})")

    # --- Training Data ---
    print()
    print("  [Training Data]")

    from backend.api.services.training_logger import TrainingLogger
    logger = TrainingLogger()
    stats = logger.get_stats()
    log_files = stats.get("files", [])
    total_records = sum(f.get("records", 0) for f in log_files)
    print(f"  Training log files:     {len(log_files)} files, {total_records} records")

    batch_commentary_path = _DATA_DIR / "batch_commentary" / "batch_commentary.jsonl"
    batch_count = _count_jsonl(batch_commentary_path)
    print(f"  Batch commentary:       {batch_count} records")

    # --- Quality ---
    if total_records > 0:
        print()
        print("  [Quality]")
        from backend.api.services.explanation_evaluator import evaluate_training_logs
        log_dir = stats.get("log_dir", "")
        if log_dir:
            eval_stats = evaluate_training_logs(log_dir)
            if eval_stats.get("total_records", 0) > 0:
                print(f"  Evaluated records:      {eval_stats['total_records']}")
                print(f"  Avg quality score:      {eval_stats.get('avg_total', 0)}")
                print(f"  Low quality (<40):      {eval_stats.get('low_quality_count', 0)}")
            else:
                print("  No evaluable records yet")

    # --- Annotated Data ---
    print()
    print("  [Annotated Data]")
    annotated_path = _DATA_DIR / "annotated" / "annotated_corpus.jsonl"
    if annotated_path.exists():
        ann_count = _count_jsonl(annotated_path)
        print(f"  Annotated records:      {ann_count} records")
        if ann_count > 0:
            from backend.api.schemas.annotation import FOCUS_LABELS, DEPTH_LEVELS
            focus_counts: Counter = Counter()
            depth_counts: Counter = Counter()
            imp_sum = 0.0
            with open(annotated_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        ann = obj.get("annotation", {})
                        for lbl in ann.get("focus", []):
                            focus_counts[lbl] += 1
                        depth_counts[ann.get("depth", "unknown")] += 1
                        imp_sum += ann.get("importance", 0)
                    except Exception:
                        continue
            print(f"  Avg importance:         {imp_sum / ann_count:.2f}")
            print(f"  Depth: ", end="")
            parts = []
            for d in DEPTH_LEVELS:
                parts.append(f"{d}={depth_counts.get(d, 0)}")
            print(", ".join(parts))
            top_focus = focus_counts.most_common(3)
            if top_focus:
                fstr = ", ".join(f"{k}({v})" for k, v in top_focus)
                print(f"  Top focus:              {fstr}")
    else:
        print("  No annotated data yet")
        print("  → Run: python3 scripts/annotate_corpus.py")

    # --- Model ---
    print()
    print("  [Model]")

    from backend.api.services.ml_trainer import CommentaryStyleSelector, _HAS_SKLEARN
    print(f"  scikit-learn:           {'YES' if _HAS_SKLEARN else 'NO'}")

    model_path = _DATA_DIR / "models" / "style_selector.joblib"
    if model_path.exists():
        selector = CommentaryStyleSelector()
        loaded = selector.load(str(model_path))
        if loaded:
            print(f"  Style selector:         TRAINED (loaded from {model_path.name})")
        else:
            print(f"  Style selector:         FILE EXISTS but failed to load")
    else:
        print(f"  Style selector:         rule-based (未訓練)")

    focus_model_path = _DATA_DIR / "models" / "focus_predictor.joblib"
    if focus_model_path.exists():
        from backend.api.services.focus_predictor import FocusPredictor
        fp = FocusPredictor()
        loaded_fp = fp.load(str(focus_model_path))
        if loaded_fp:
            print(f"  Focus predictor:        TRAINED (loaded from {focus_model_path.name})")
        else:
            print(f"  Focus predictor:        FILE EXISTS but failed to load")
    else:
        print(f"  Focus predictor:        rule-based (未訓練)")

    # --- Experiments ---
    print()
    print("  [Experiments]")
    experiments_dir = _DATA_DIR / "experiments"
    if experiments_dir.is_dir():
        exp_files = sorted([
            f for f in experiments_dir.iterdir()
            if f.suffix == ".json" and not f.name.startswith("analysis")
        ])
        if exp_files:
            latest = exp_files[-1]
            try:
                with open(latest, encoding="utf-8") as f:
                    exp = json.load(f)
                print(f"  Latest experiment:      {exp.get('name', latest.stem)}")
                print(f"  Timestamp:              {exp.get('timestamp', 'unknown')[:19]}")
                print(f"  Samples:                {exp.get('n_samples', 0)}")
                best_name = exp.get("best_model", "")
                best_result = next(
                    (m for m in exp.get("models", []) if m["name"] == best_name),
                    {},
                )
                if best_result:
                    f1 = best_result.get("f1_macro_mean", 0)
                    acc = best_result.get("accuracy_mean", 0)
                    print(f"  Best model:             {best_name} (F1={f1:.3f}, Acc={acc:.3f})")
                    fi = best_result.get("feature_importance", {})
                    if fi:
                        top3 = sorted(fi.items(), key=lambda x: -x[1])[:3]
                        feats_str = ", ".join(f"{k}({v:.3f})" for k, v in top3)
                        print(f"  Top-3 features:         {feats_str}")
            except Exception as e:
                print(f"  Error loading experiment: {e}")
        else:
            print("  No experiments yet")
            print("  → Run: python3 scripts/run_experiment.py --name baseline")
    else:
        print("  No experiments yet")
        print("  → Run: python3 scripts/run_experiment.py --name baseline")

    # --- Reports ---
    print()
    print("  [Reports]")
    reports_dir = _DATA_DIR / "reports"
    if reports_dir.is_dir():
        md_files = sorted([
            f for f in reports_dir.iterdir()
            if f.suffix == ".md"
        ])
        if md_files:
            latest_report = md_files[-1]
            import datetime as _dt
            mod_time = _dt.datetime.fromtimestamp(latest_report.stat().st_mtime)
            print(f"  Latest report:          {latest_report.name}")
            print(f"  Generated:              {mod_time.strftime('%Y-%m-%d %H:%M')}")
            print(f"  Path:                   {latest_report}")
        else:
            print("  No reports yet")
            print("  → Run: python3 scripts/generate_report.py")
    else:
        print("  No reports yet")
        print("  → Run: python3 scripts/run_baseline.py && python3 scripts/generate_report.py")

    # --- Next Action ---
    print()
    print("  [Next Action]")
    if total_records == 0 and batch_count == 0:
        print("  → Run: python3 scripts/batch_generate_commentary.py --dry-run")
    elif total_records < 10:
        print(f"  → あと {10 - total_records} 件でML訓練可能")
    elif not model_path.exists():
        print("  → Run: python3 scripts/train_style_model.py")
    else:
        print("  → パイプライン稼働中。API解説生成でデータ蓄積を継続")

    print()
    print("=" * 56)
    print()


if __name__ == "__main__":
    main()
