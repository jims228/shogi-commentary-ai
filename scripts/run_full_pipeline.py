#!/usr/bin/env python3
"""パイプライン全体の結合テスト:
1. sample_games.txt から特徴量バッチ抽出
2. 抽出結果に対して品質ベンチマーク
3. 統計サマリー出力

Gemini APIは一切使わない。
"""
from __future__ import annotations

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


def run_pipeline() -> Dict[str, Any]:
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

    extract_stats = batch_extract(
        str(_SAMPLE_GAMES),
        str(_PIPELINE_OUTPUT),
        sample_interval=5,
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
    # Step 4: 結果まとめ
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
    print("=" * 60)

    return {
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


if __name__ == "__main__":
    result = run_pipeline()
    sys.exit(0 if result.get("quality_pass", False) else 1)
