#!/usr/bin/env python3
"""パイプライン全体の結合テスト:
1. sample_games.txt から特徴量バッチ抽出
2. 抽出結果に対して品質ベンチマーク
3. 統計サマリー出力
4. (--full-cycle) バッチ解説生成 + モデル訓練 + スタイル予測テスト

Gemini APIは一切使わない。
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

# プロジェクトルートをパスに追加
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.batch_extract_features import batch_extract
from backend.api.services.template_commentary import generate_template_commentary
from backend.api.services.explanation_evaluator import evaluate_explanation

_SAMPLE_GAMES = _PROJECT_ROOT / "data" / "sample_games.txt"
_PIPELINE_OUTPUT = _PROJECT_ROOT / "data" / "pipeline_test_features.jsonl"


def _stats(values: List[float]) -> Dict[str, float]:
    """基本統計量を計算."""
    if not values:
        return {"mean": 0, "min": 0, "max": 0, "count": 0}
    return {
        "mean": round(sum(values) / len(values), 1),
        "min": min(values),
        "max": max(values),
        "count": len(values),
    }


def _text_bar(label: str, count: int, total: int, width: int = 30) -> str:
    """テキストベースのバーを生成."""
    if total == 0:
        ratio = 0
    else:
        ratio = count / total
    filled = int(width * ratio)
    bar = "█" * filled + "░" * (width - filled)
    pct = f"{ratio * 100:.1f}%"
    return f"  {label:<12} {bar} {count:>3} ({pct})"


def run_pipeline(sample_interval: int = 5, full_cycle: bool = False) -> Dict[str, Any]:
    """パイプライン全体を実行."""
    print("=" * 60)
    print("  Full Pipeline Integration Test")
    print("=" * 60)

    # ------------------------------------------------------------------
    # Step 1: バッチ特徴量抽出
    # ------------------------------------------------------------------
    print("\n[Step 1] Batch Feature Extraction")
    print(f"  Input:  {_SAMPLE_GAMES}")
    print(f"  Output: {_PIPELINE_OUTPUT}")
    print(f"  Interval: {sample_interval}")

    extract_stats = batch_extract(
        str(_SAMPLE_GAMES),
        str(_PIPELINE_OUTPUT),
        sample_interval=sample_interval,
    )

    # ------------------------------------------------------------------
    # Step 2: 抽出した特徴量の統計
    # ------------------------------------------------------------------
    print("\n[Step 2] Feature Statistics")

    records: List[Dict[str, Any]] = []
    with open(_PIPELINE_OUTPUT, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))

    if not records:
        print("  No records extracted!")
        return {"error": "no_records"}

    # Phase 分布
    phase_counts = Counter(r.get("phase", "unknown") for r in records)
    total = len(records)
    print(f"\n  Phase distribution ({total} positions):")
    for phase in ["opening", "midgame", "endgame"]:
        count = phase_counts.get(phase, 0)
        print(_text_bar(phase, count, total))

    # 数値特徴量の統計
    ks_values = [r["king_safety"] for r in records if "king_safety" in r]
    pa_values = [r["piece_activity"] for r in records if "piece_activity" in r]
    ap_values = [r["attack_pressure"] for r in records if "attack_pressure" in r]

    ks_stats = _stats(ks_values)
    pa_stats = _stats(pa_values)
    ap_stats = _stats(ap_values)

    print(f"\n  Feature statistics:")
    print(f"  {'Metric':<20} {'Mean':>6} {'Min':>6} {'Max':>6}")
    print(f"  {'-'*44}")
    print(f"  {'king_safety':<20} {ks_stats['mean']:>6} {ks_stats['min']:>6} {ks_stats['max']:>6}")
    print(f"  {'piece_activity':<20} {pa_stats['mean']:>6} {pa_stats['min']:>6} {pa_stats['max']:>6}")
    print(f"  {'attack_pressure':<20} {ap_stats['mean']:>6} {ap_stats['min']:>6} {ap_stats['max']:>6}")

    # Move intent 分布
    intent_counts = Counter(
        r.get("move_intent", "none") for r in records
    )
    print(f"\n  Move intent distribution:")
    for intent in ["attack", "defense", "development", "exchange", "sacrifice", "none", None]:
        label = str(intent) if intent else "none"
        count = intent_counts.get(intent, 0)
        if count > 0:
            print(_text_bar(label, count, total))

    # ------------------------------------------------------------------
    # Step 3: テンプレート解説生成 + 品質評価
    # ------------------------------------------------------------------
    print("\n[Step 3] Template Commentary + Quality Evaluation")

    scores: List[float] = []
    axis_scores: Dict[str, List[float]] = {
        "context_relevance": [],
        "naturalness": [],
        "informativeness": [],
        "readability": [],
    }

    for i, record in enumerate(records):
        commentary = generate_template_commentary(record, seed=i)
        evaluation = evaluate_explanation(commentary, features=record)
        scores.append(evaluation["total"])
        for axis in axis_scores:
            axis_scores[axis].append(evaluation["scores"][axis])

    score_stats = _stats(scores)
    print(f"\n  Quality scores ({len(scores)} commentaries):")
    print(f"  {'Axis':<22} {'Mean':>6} {'Min':>6} {'Max':>6}")
    print(f"  {'-'*44}")
    for axis, vals in axis_scores.items():
        s = _stats(vals)
        print(f"  {axis:<22} {s['mean']:>6} {s['min']:>6} {s['max']:>6}")
    print(f"  {'-'*44}")
    print(f"  {'TOTAL':<22} {score_stats['mean']:>6} {score_stats['min']:>6} {score_stats['max']:>6}")

    # ------------------------------------------------------------------
    # Full-cycle: Steps 4-6
    # ------------------------------------------------------------------
    batch_stats = None
    train_result = None
    style_dist: Dict[str, int] = {}

    if full_cycle:
        from scripts.batch_generate_commentary import batch_generate
        from backend.api.services.ml_trainer import (
            CommentaryStyleSelector,
            rule_based_predict,
            _HAS_SKLEARN,
        )

        # Step 4: バッチ解説生成 (dry-run)
        print("\n[Step 4] Batch Commentary Generation (dry-run)")
        _BATCH_OUTPUT_DIR = _PROJECT_ROOT / "data" / "batch_commentary"
        batch_stats = asyncio.run(batch_generate(
            input_file=str(_SAMPLE_GAMES),
            output_dir=str(_BATCH_OUTPUT_DIR),
            sample_interval=sample_interval,
            max_requests=50,
            dry_run=True,
        ))
        print(f"  Processed: {batch_stats['processed']}, Avg quality: {batch_stats['avg_quality']}")

        # Step 5: モデル訓練
        print("\n[Step 5] Style Selector Training")
        selector = CommentaryStyleSelector()
        train_result = selector.train()
        if "error" in train_result:
            print(f"  Training skipped: {train_result['error']}")
            print(f"  Samples found: {train_result['samples']}")
        else:
            print(f"  Samples: {train_result['samples']}")
            print(f"  Accuracy: {train_result['accuracy']}")
            print(f"  Distribution: {train_result['distribution']}")
            if _HAS_SKLEARN:
                saved_path = selector.save()
                print(f"  Model saved: {saved_path}")

        # Step 6: スタイル予測テスト
        print("\n[Step 6] Style Prediction Test")
        style_counter = Counter()
        test_records = records[:20]
        for record in test_records:
            if selector.is_trained:
                predicted = selector.predict(record)
            else:
                predicted = rule_based_predict(record)
            style_counter[predicted] += 1
        style_total = sum(style_counter.values())
        for style in ["technical", "encouraging", "neutral"]:
            count = style_counter.get(style, 0)
            print(_text_bar(style, count, style_total))
        style_dist = dict(style_counter)

    # ------------------------------------------------------------------
    # Results Summary
    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("  Pipeline Results")
    print("=" * 60)
    print(f"  Games processed:    {extract_stats['games']}")
    print(f"  Positions extracted: {extract_stats['positions']}")
    print(f"  Elapsed time:       {extract_stats['elapsed_sec']}s")
    print(f"  Avg quality score:  {score_stats['mean']}")
    print(f"  Min quality score:  {score_stats['min']}")

    quality_pass = score_stats["mean"] >= 40
    print(f"\n  Quality threshold (avg >= 40): {'PASS' if quality_pass else 'FAIL'}")

    if full_cycle:
        print(f"\n  [Full Cycle]")
        if batch_stats:
            print(f"  Batch commentary:   {batch_stats['processed']} generated")
        if train_result and "error" not in train_result:
            print(f"  Model accuracy:     {train_result['accuracy']}")
        if style_dist:
            print(f"  Style distribution: {style_dist}")

    print("=" * 60)

    result: Dict[str, Any] = {
        "extract_stats": extract_stats,
        "feature_stats": {
            "king_safety": ks_stats,
            "piece_activity": pa_stats,
            "attack_pressure": ap_stats,
        },
        "phase_distribution": dict(phase_counts),
        "intent_distribution": {str(k): v for k, v in intent_counts.items()},
        "quality": {
            "total": score_stats,
            "axes": {k: _stats(v) for k, v in axis_scores.items()},
        },
        "quality_pass": quality_pass,
    }

    if full_cycle:
        result["batch_stats"] = batch_stats
        result["train_result"] = train_result
        result["style_distribution"] = style_dist

    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Full pipeline integration test")
    parser.add_argument(
        "--interval", type=int, default=5,
        help="Sample interval for feature extraction (default: 5)",
    )
    parser.add_argument(
        "--full-cycle", action="store_true",
        help="Run extended pipeline: batch commentary, model training, style prediction test",
    )
    args = parser.parse_args()

    result = run_pipeline(sample_interval=args.interval, full_cycle=args.full_cycle)
    sys.exit(0 if result.get("quality_pass", False) else 1)
