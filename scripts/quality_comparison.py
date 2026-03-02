#!/usr/bin/env python3
"""テンプレート vs Gemini 解説品質A/B比較ツール.

Usage:
    python scripts/quality_comparison.py --samples 10 --dry-run
    python scripts/quality_comparison.py --samples 20 --output comparison.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import random
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from backend.api.services.template_commentary import generate_template_commentary  # noqa: E402
from backend.api.services.explanation_evaluator import evaluate_explanation  # noqa: E402


def load_features(
    features_path: str,
    samples: int = 10,
    seed: int = 42,
) -> List[Dict[str, Any]]:
    """pipeline_test_features.jsonl からサンプルを読み込む."""
    records: List[Dict[str, Any]] = []
    with open(features_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    if not records:
        return []

    rng = random.Random(seed)
    n = min(samples, len(records))
    return rng.sample(records, n)


def generate_mock_gemini_commentary(
    features: Dict[str, Any],
    seed: int = 0,
) -> str:
    """dry-run用: テンプレートより長めのモック解説を生成.

    2つのテンプレート出力を接続詞で結合してLLM風の長さにする。
    """
    text1 = generate_template_commentary(features, seed=seed)
    text2 = generate_template_commentary(features, seed=seed + 500)
    connector = random.Random(seed).choice(["しかし", "また", "さらに"])
    return f"{text1}{connector}{text2}"


async def generate_gemini_commentary(
    features: Dict[str, Any],
    sfen: str,
    ply: int,
) -> str:
    """Gemini API 経由で解説を生成."""
    from backend.api.services.ai_service import AIService
    return await AIService.generate_position_comment(
        ply=ply,
        sfen=sfen,
        candidates=[],
        user_move=None,
        delta_cp=None,
        features=features,
    )


def compare_single(
    features: Dict[str, Any],
    template_text: str,
    gemini_text: str,
) -> Dict[str, Any]:
    """1つの局面に対してA/B比較結果を生成."""
    template_quality = evaluate_explanation(template_text, features)
    gemini_quality = evaluate_explanation(gemini_text, features)

    diff: Dict[str, Any] = {
        "total": round(gemini_quality["total"] - template_quality["total"], 1),
    }
    for axis in template_quality["scores"]:
        diff[axis] = gemini_quality["scores"][axis] - template_quality["scores"][axis]

    return {
        "phase": features.get("phase", "unknown"),
        "move_intent": features.get("move_intent"),
        "ply": features.get("ply", 0),
        "template": {"text": template_text, "quality": template_quality},
        "gemini": {"text": gemini_text, "quality": gemini_quality},
        "quality_diff": diff,
    }


def compute_phase_breakdown(
    results: List[Dict[str, Any]],
) -> Dict[str, Dict[str, float]]:
    """フェーズ別の平均スコアを計算."""
    phase_groups: Dict[str, List[Dict[str, Any]]] = {}
    for r in results:
        phase = r.get("phase", "unknown")
        phase_groups.setdefault(phase, []).append(r)

    breakdown: Dict[str, Dict[str, float]] = {}
    for phase, group in sorted(phase_groups.items()):
        t_scores = [r["template"]["quality"]["total"] for r in group]
        g_scores = [r["gemini"]["quality"]["total"] for r in group]
        d_scores = [r["quality_diff"]["total"] for r in group]
        breakdown[phase] = {
            "template_avg": round(sum(t_scores) / len(t_scores), 1),
            "gemini_avg": round(sum(g_scores) / len(g_scores), 1),
            "diff_avg": round(sum(d_scores) / len(d_scores), 1),
            "count": len(group),
        }
    return breakdown


def print_comparison_report(
    results: List[Dict[str, Any]],
    phase_breakdown: Dict[str, Dict[str, float]],
) -> None:
    """結果をコンソールに見やすく表示."""
    print()
    print("=" * 64)
    print("  A/B Quality Comparison: Template vs Gemini")
    print("=" * 64)

    for i, r in enumerate(results):
        t_total = r["template"]["quality"]["total"]
        g_total = r["gemini"]["quality"]["total"]
        diff = r["quality_diff"]["total"]
        sign = "+" if diff >= 0 else ""

        print(f"\n  [{i + 1}] Phase: {r['phase']}, Ply: {r['ply']}, Intent: {r.get('move_intent', 'N/A')}")
        print(f"    Template ({t_total:>5.1f}): {r['template']['text'][:60]}...")
        print(f"    Gemini   ({g_total:>5.1f}): {r['gemini']['text'][:60]}...")
        print(f"    Diff: {sign}{diff:.1f}", end="")

        axis_diffs = []
        for axis in ["context_relevance", "naturalness", "informativeness", "readability"]:
            d = r["quality_diff"].get(axis, 0)
            s = "+" if d >= 0 else ""
            axis_diffs.append(f"{axis}: {s}{d}")
        print(f" ({', '.join(axis_diffs)})")

    # Phase breakdown table
    print()
    print("-" * 64)
    print(f"  {'Phase':<12} {'Template':>10} {'Gemini':>10} {'Diff':>10} {'Count':>8}")
    print(f"  {'-' * 52}")

    all_t = [r["template"]["quality"]["total"] for r in results]
    all_g = [r["gemini"]["quality"]["total"] for r in results]

    for phase in ["opening", "midgame", "endgame"]:
        if phase in phase_breakdown:
            b = phase_breakdown[phase]
            sign = "+" if b["diff_avg"] >= 0 else ""
            print(f"  {phase:<12} {b['template_avg']:>10.1f} {b['gemini_avg']:>10.1f} {sign}{b['diff_avg']:>9.1f} {b['count']:>8}")

    if results:
        overall_t = round(sum(all_t) / len(all_t), 1)
        overall_g = round(sum(all_g) / len(all_g), 1)
        overall_d = round(overall_g - overall_t, 1)
        sign = "+" if overall_d >= 0 else ""
        print(f"  {'-' * 52}")
        print(f"  {'Overall':<12} {overall_t:>10.1f} {overall_g:>10.1f} {sign}{overall_d:>9.1f} {len(results):>8}")

    print("=" * 64)
    print()


async def run_comparison(
    features_path: str,
    samples: int = 10,
    dry_run: bool = True,
    seed: int = 42,
) -> List[Dict[str, Any]]:
    """A/B比較を実行."""
    features_list = load_features(features_path, samples, seed)
    results: List[Dict[str, Any]] = []

    for i, feat in enumerate(features_list):
        template_text = generate_template_commentary(feat, seed=seed + i)

        if dry_run:
            gemini_text = generate_mock_gemini_commentary(feat, seed=seed + i + 1000)
        else:
            sfen = feat.get("sfen", "position startpos")
            ply = feat.get("ply", 0)
            gemini_text = await generate_gemini_commentary(feat, sfen, ply)

        result = compare_single(feat, template_text, gemini_text)
        results.append(result)

    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="テンプレート vs Gemini 解説品質A/B比較"
    )
    parser.add_argument(
        "--samples", type=int, default=10,
        help="比較するサンプル数 (default: 10)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Geminiの代わりにモック解説を使用",
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="結果をJSONファイルに保存 (省略時はstdoutのみ)",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="乱数シード (default: 42)",
    )
    parser.add_argument(
        "--features-path",
        default=str(_PROJECT_ROOT / "data" / "pipeline_test_features.jsonl"),
        help="特徴量ファイルパス",
    )
    args = parser.parse_args()

    results = asyncio.run(run_comparison(
        features_path=args.features_path,
        samples=args.samples,
        dry_run=args.dry_run,
        seed=args.seed,
    ))

    phase_breakdown = compute_phase_breakdown(results)
    print_comparison_report(results, phase_breakdown)

    if args.output:
        output_data = {
            "results": results,
            "phase_breakdown": phase_breakdown,
            "config": {
                "samples": args.samples,
                "dry_run": args.dry_run,
                "seed": args.seed,
            },
        }
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        print(f"Saved to {args.output}")


if __name__ == "__main__":
    main()
