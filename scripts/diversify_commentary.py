#!/usr/bin/env python3
"""多様性指向バッチ解説生成.

既存局面データに対して、不足しているスタイル・着目点・深度の
組み合わせで解説を生成し、アノテーションデータの多様性を確保する。

Usage:
    python scripts/diversify_commentary.py --dry-run
    python scripts/diversify_commentary.py --dry-run --max-samples 10
    python scripts/diversify_commentary.py --max-samples 30 --max-per-sample 10
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(_PROJECT_ROOT / ".env")
except ImportError:
    pass

from backend.api.schemas.annotation import DEPTH_LEVELS, FOCUS_LABELS
from backend.api.services.annotation_service import annotate_text
from backend.api.services.diverse_prompts import (
    DIVERSITY_TARGETS,
    build_diverse_prompt,
    compute_target_match,
)
from backend.api.services.explanation_evaluator import evaluate_explanation
from backend.api.services.template_commentary import generate_template_commentary
from backend.api.services.ml_trainer import STYLES
from scripts.batch_generate_commentary import (
    _estimate_cost_yen,
    load_collection_config,
)

_DATA_DIR = _PROJECT_ROOT / "data"
_FEATURES_PATH = _DATA_DIR / "pipeline_test_features.jsonl"
_DEFAULT_OUTPUT = _DATA_DIR / "annotated" / "diverse_commentary.jsonl"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def _load_features(path: Path) -> List[Dict[str, Any]]:
    """pipeline_test_features.jsonl から局面データを読み込む."""
    records: List[Dict[str, Any]] = []
    if not path.exists():
        return records
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except Exception:
                continue
    return records


def _sample_balanced(
    records: List[Dict[str, Any]],
    max_samples: int,
    seed: int = 42,
) -> List[Dict[str, Any]]:
    """フェーズ均等にサンプリング.

    opening / midgame / endgame をなるべく均等に取得する。
    """
    by_phase: Dict[str, List[Dict[str, Any]]] = {
        "opening": [],
        "midgame": [],
        "endgame": [],
    }
    for r in records:
        phase = r.get("phase", "midgame")
        if phase in by_phase:
            by_phase[phase].append(r)

    rng = random.Random(seed)
    per_phase = max(1, max_samples // 3)
    sampled: List[Dict[str, Any]] = []
    for phase in ["opening", "midgame", "endgame"]:
        pool = by_phase[phase]
        rng.shuffle(pool)
        sampled.extend(pool[:per_phase])

    return sampled[:max_samples]


# ---------------------------------------------------------------------------
# Dry-run template generator (diversity-aware)
# ---------------------------------------------------------------------------
def _generate_diverse_template(
    features: Dict[str, Any],
    target: Dict[str, Any],
    seed: int = 0,
) -> str:
    """dry-run用: ターゲットに応じたテンプレート解説を生成.

    実際のGemini APIの代わりに、ターゲットの着目点・深度に応じて
    テキストの長さとキーワードを制御する。
    """
    rng = random.Random(seed)
    focus_labels = target.get("focus", ["positional"])
    depth = target.get("depth", "strategic")

    # Focus-aware keyword injection
    _FOCUS_PHRASES: Dict[str, List[str]] = {
        "king_safety": ["玉の囲いを固め", "守りを重視し", "玉の安全度に注目すると"],
        "piece_activity": ["駒の活用を図り", "効率良く駒を動かし", "駒の働きを高め"],
        "attack_pressure": ["攻めの圧力を高め", "相手玉に迫る狙いで", "仕掛けのタイミングを計り"],
        "positional": ["形勢のバランスを保ち", "陣形を整え", "位取りを意識し"],
        "tempo": ["手番の利を活かし", "テンポ良く進め", "手得を狙い"],
        "endgame_technique": ["終盤の寄せに入り", "詰みを見据え", "受けの技術を駆使し"],
    }

    parts: List[str] = []
    for f in focus_labels:
        phrases = _FOCUS_PHRASES.get(f, _FOCUS_PHRASES["positional"])
        parts.append(rng.choice(phrases))

    base = generate_template_commentary(features, seed=seed)

    # Depth control
    if depth == "surface":
        # Short: just the first focus phrase + ending
        text = parts[0] + "ています。"
    elif depth == "deep":
        # Long: combine base + all focus phrases + conditional
        conditionals = [
            "もし相手が受けに回った場合は別の展開も考えられます。",
            "仮に攻めが成功すれば大きなリードとなるでしょう。",
            "一方で慎重に進める選択肢もあり、判断が分かれる局面です。",
        ]
        text = (
            base + " " + "、".join(parts) + "ていく展開です。"
            + rng.choice(conditionals)
        )
    else:
        # Strategic: medium length
        text = "、".join(parts) + "ていく展開です。" + base.split("。")[0] + "。"

    return text


# ---------------------------------------------------------------------------
# Async API call
# ---------------------------------------------------------------------------
async def _generate_api_commentary(
    features: Dict[str, Any],
    target: Dict[str, Any],
) -> str:
    """Gemini API経由でターゲット指定の解説を生成."""
    from backend.api.utils.gemini_client import ensure_configured

    if not ensure_configured():
        raise RuntimeError("GEMINI_API_KEY not set")

    import google.generativeai as genai

    prompt = build_diverse_prompt(
        features,
        target_style=target["style"],
        target_focus=target["focus"],
        target_depth=target["depth"],
    )

    model = genai.GenerativeModel(
        "gemini-2.5-flash-lite",
        generation_config=genai.types.GenerationConfig(max_output_tokens=500),
    )
    res = await model.generate_content_async(prompt)
    return res.text


# ---------------------------------------------------------------------------
# Main batch function
# ---------------------------------------------------------------------------
async def diversify_commentary(
    output_path: Path = _DEFAULT_OUTPUT,
    max_samples: int = 30,
    max_per_sample: int = 10,
    dry_run: bool = True,
    min_quality_score: float = 40.0,
    rate_limit: int = 10,
    daily_budget_yen: float = 100.0,
) -> Dict[str, Any]:
    """多様性指向バッチ解説生成.

    Parameters
    ----------
    output_path : Path
        出力先 JSONL ファイル。
    max_samples : int
        サンプリングする最大局面数。
    max_per_sample : int
        各局面あたりの最大ターゲット数。
    dry_run : bool
        True の場合テンプレートを使用。
    min_quality_score : float
        品質最低スコア。
    rate_limit : int
        API呼び出し回数/分。
    daily_budget_yen : float
        日次予算（円）。

    Returns
    -------
    dict
        統計情報。
    """
    # Load features
    all_features = _load_features(_FEATURES_PATH)
    if not all_features:
        print("  No features data found.")
        return {"generated": 0, "error": "no features data"}

    sampled = _sample_balanced(all_features, max_samples)
    targets = DIVERSITY_TARGETS[:max_per_sample]

    print()
    print("=" * 60)
    print("  Shogi Commentary AI - Diversity Generation")
    print("=" * 60)
    print(f"  Mode:          {'DRY-RUN' if dry_run else 'API'}")
    print(f"  Sampled:       {len(sampled)} positions")
    print(f"  Targets/pos:   {len(targets)} combinations")
    print(f"  Max total:     {len(sampled) * len(targets)} records")
    print()

    sleep_interval = 60.0 / max(1, rate_limit) if not dry_run else 0.0
    start_time = time.time()

    generated = 0
    retries = 0
    api_calls = 0
    style_counts: Counter[str] = Counter()
    focus_counts: Counter[str] = Counter()
    depth_counts: Counter[str] = Counter()
    quality_sum = 0.0
    match_stats = {"style": 0, "focus_recall_sum": 0.0, "depth": 0}

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as out:
        for si, feat_record in enumerate(sampled):
            # Build a features dict compatible with annotate_text
            features: Dict[str, Any] = {
                "king_safety": feat_record.get("king_safety", 50),
                "piece_activity": feat_record.get("piece_activity", 50),
                "attack_pressure": feat_record.get("attack_pressure", 0),
                "phase": feat_record.get("phase", "midgame"),
                "turn": feat_record.get("turn", "b"),
                "ply": feat_record.get("ply", 0),
                "move_intent": feat_record.get("move_intent", "development"),
                "tension_delta": feat_record.get("tension_delta", {
                    "d_king_safety": 0.0,
                    "d_piece_activity": 0.0,
                    "d_attack_pressure": 0.0,
                }),
            }
            after = feat_record.get("after")
            if after:
                features["after"] = after

            sfen = feat_record.get("sfen", "position startpos")
            ply = feat_record.get("ply", 0)
            move = feat_record.get("move", "")

            for ti, target in enumerate(targets):
                # Budget check (API mode)
                if not dry_run:
                    cost = _estimate_cost_yen(api_calls + 1)
                    if cost > daily_budget_yen:
                        print(f"\n  Budget limit: ¥{cost:.2f} > ¥{daily_budget_yen}")
                        break

                # Generate commentary
                seed = si * 1000 + ti
                if dry_run:
                    text = _generate_diverse_template(features, target, seed=seed)
                else:
                    if sleep_interval > 0 and api_calls > 0:
                        time.sleep(sleep_interval)
                    try:
                        text = await _generate_api_commentary(features, target)
                        api_calls += 1
                    except Exception as e:
                        print(f"  API error: {e}", file=sys.stderr)
                        continue

                # Quality evaluation
                quality = evaluate_explanation(text, features)

                # Retry once if low quality
                if quality["total"] < min_quality_score:
                    retries += 1
                    if dry_run:
                        text = _generate_diverse_template(
                            features, target, seed=seed + 500
                        )
                    else:
                        if sleep_interval > 0:
                            time.sleep(sleep_interval)
                        try:
                            text = await _generate_api_commentary(features, target)
                            api_calls += 1
                        except Exception:
                            pass
                    quality = evaluate_explanation(text, features)

                # Annotate
                ann = annotate_text(text, features)

                # Target match
                match = compute_target_match(target, ann)

                # Record
                record = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "source": "template-diverse" if dry_run else "gemini",
                    "sfen": sfen,
                    "ply": ply,
                    "move": move,
                    "features": features,
                    "target": target,
                    "annotation": ann,
                    "target_match": match,
                    "original_text": text,
                    "quality": quality,
                    "annotator": "rule-based" if dry_run else "gemini-auto",
                }
                out.write(json.dumps(record, ensure_ascii=False) + "\n")

                generated += 1
                style_counts[ann["style"]] += 1
                for f in ann["focus"]:
                    focus_counts[f] += 1
                depth_counts[ann["depth"]] += 1
                quality_sum += quality["total"]

                if match["style_match"]:
                    match_stats["style"] += 1
                match_stats["focus_recall_sum"] += match["focus_recall"]
                if match["depth_match"]:
                    match_stats["depth"] += 1

            # Progress
            elapsed = time.time() - start_time
            print(
                f"\r  [{si + 1}/{len(sampled)}] {generated} generated ({elapsed:.1f}s)",
                end="", flush=True,
            )

    elapsed = time.time() - start_time
    print()

    # Summary
    avg_quality = round(quality_sum / max(1, generated), 1)
    n = max(1, generated)

    print()
    print("  [Style Distribution]")
    for s in STYLES:
        cnt = style_counts.get(s, 0)
        pct = f"{cnt / n * 100:.1f}%"
        print(f"    {s:<14} {cnt:>4} ({pct})")

    print()
    print("  [Focus Distribution]")
    for f in FOCUS_LABELS:
        cnt = focus_counts.get(f, 0)
        pct = f"{cnt / n * 100:.1f}%"
        print(f"    {f:<22} {cnt:>4} ({pct})")

    print()
    print("  [Depth Distribution]")
    for d in DEPTH_LEVELS:
        cnt = depth_counts.get(d, 0)
        pct = f"{cnt / n * 100:.1f}%"
        print(f"    {d:<14} {cnt:>4} ({pct})")

    print()
    print("  [Target Match]")
    print(f"    Style match:     {match_stats['style']}/{generated} ({match_stats['style'] / n * 100:.0f}%)")
    print(f"    Focus recall:    {match_stats['focus_recall_sum'] / n:.2f}")
    print(f"    Depth match:     {match_stats['depth']}/{generated} ({match_stats['depth'] / n * 100:.0f}%)")

    print()
    print(f"  Generated:  {generated} records")
    print(f"  Retries:    {retries}")
    print(f"  Avg quality: {avg_quality}")
    if not dry_run:
        print(f"  API calls:  {api_calls}")
        print(f"  Cost:       ¥{_estimate_cost_yen(api_calls):.4f}")
    print(f"  Output:     {output_path}")
    print(f"  Elapsed:    {elapsed:.1f}s")
    print()
    print("=" * 60)
    print()

    return {
        "generated": generated,
        "retries": retries,
        "avg_quality": avg_quality,
        "style_distribution": dict(style_counts),
        "focus_distribution": dict(focus_counts),
        "depth_distribution": dict(depth_counts),
        "target_match": {
            "style_match_rate": round(match_stats["style"] / n, 2),
            "avg_focus_recall": round(match_stats["focus_recall_sum"] / n, 2),
            "depth_match_rate": round(match_stats["depth"] / n, 2),
        },
        "elapsed_sec": round(elapsed, 2),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Diverse commentary generation for data diversification"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="テンプレートを使用（API不使用）",
    )
    parser.add_argument(
        "--max-samples", type=int, default=30,
        help="サンプリング局面数 (default: 30)",
    )
    parser.add_argument(
        "--max-per-sample", type=int, default=10,
        help="局面あたりのターゲット数 (default: 10)",
    )
    parser.add_argument(
        "--output", default=None,
        help=f"出力パス (default: {_DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--config", default=None,
        help="collection_config.json のパス",
    )
    args = parser.parse_args()

    config = load_collection_config(args.config)
    out = Path(args.output) if args.output else _DEFAULT_OUTPUT

    asyncio.run(diversify_commentary(
        output_path=out,
        max_samples=args.max_samples,
        max_per_sample=args.max_per_sample,
        dry_run=args.dry_run,
        min_quality_score=config["min_quality_score"],
        rate_limit=config["rate_limit_per_minute"],
        daily_budget_yen=config["daily_budget_yen"],
    ))


if __name__ == "__main__":
    main()
