"""scripts/enrich_eval_set.py

Generate legacy + planner explanations for an eval set.

Reuses compare_legacy_vs_planner.compare_single() for generation,
then maps results back into the eval set format.

Usage:
  # Dry run (10 records, no LLM)
  python scripts/enrich_eval_set.py data/human_eval/swars_eval_merged.json --limit 10

  # Dry run with LLM
  USE_LLM=1 python scripts/enrich_eval_set.py data/human_eval/swars_eval_merged.json --limit 10

  # Full run
  USE_LLM=1 python scripts/enrich_eval_set.py data/human_eval/swars_eval_merged.json

  # Custom output
  USE_LLM=1 python scripts/enrich_eval_set.py input.json -o output.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.compare_legacy_vs_planner import compare_single


async def enrich_records(
    records: List[Dict[str, Any]],
    use_llm: bool,
    style: str = "neutral",
    rate_limit_sec: float = 1.0,
) -> List[Dict[str, Any]]:
    """Generate both explanations for each record."""
    enriched = []
    errors = 0
    fallbacks = 0

    for i, rec in enumerate(records):
        try:
            result = await compare_single(rec, use_llm=use_llm, style=style)
        except Exception as e:
            print(f"  [{i+1}/{len(records)}] ERROR: {e}")
            errors += 1
            enriched.append(rec)
            continue

        # Map compare result back into eval record fields
        rec["legacy_explanation"] = result["legacy_explanation"]
        rec["planner_explanation"] = result["planner_explanation"]

        plan = result.get("planner_plan") or {}
        rec["planner_plan_flow"] = plan.get("flow", "")
        rec["planner_plan_topic_keyword"] = plan.get("topic_keyword", "")
        rec["planner_plan_surface_reason"] = plan.get("surface_reason", "")
        rec["planner_plan_deep_reason"] = plan.get("deep_reason", "")

        rec["auto_legacy_score"] = result.get("legacy_eval", {}).get("total")
        rec["auto_planner_score"] = result.get("planner_eval", {}).get("total")
        rec["is_fallback"] = result.get("is_fallback", False)

        fb = " [fallback]" if rec["is_fallback"] else ""
        print(
            f"  [{i+1}/{len(records)}] ply={rec['ply']:>3d}  "
            f"legacy={len(rec['legacy_explanation']):>2d}ch  "
            f"planner={len(rec['planner_explanation']):>2d}ch{fb}"
        )

        if rec["is_fallback"]:
            fallbacks += 1

        enriched.append(rec)

        # Rate limit for LLM calls
        if use_llm and i < len(records) - 1:
            time.sleep(rate_limit_sec)

    return enriched


def main():
    parser = argparse.ArgumentParser(description="Enrich eval set with explanations")
    parser.add_argument("input", help="Eval set JSON (with 'records' key or plain array)")
    parser.add_argument("-o", "--output", default=None, help="Output path")
    parser.add_argument("--limit", "-n", type=int, default=None, help="Process only first N records")
    parser.add_argument("--style", default="neutral", choices=["neutral", "technical", "encouraging"])
    parser.add_argument("--rate-limit", type=float, default=1.0, help="Seconds between LLM calls (default: 1.0)")
    args = parser.parse_args()

    use_llm = os.getenv("USE_LLM", "0") == "1"
    input_path = Path(args.input)

    with open(input_path, encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict) and "records" in data:
        records = data["records"]
        wrapper = data
    elif isinstance(data, list):
        records = data
        wrapper = None
    else:
        print("[enrich] Unknown input format")
        sys.exit(1)

    if args.limit:
        records = records[:args.limit]

    print(f"[enrich] {len(records)} records from {input_path.name}")
    print(f"[enrich] use_llm={use_llm}, style={args.style}")

    enriched = asyncio.run(enrich_records(
        records, use_llm=use_llm, style=args.style,
        rate_limit_sec=args.rate_limit,
    ))

    # Stats
    has_both = sum(1 for r in enriched if r.get("legacy_explanation") and r.get("planner_explanation"))
    empty_legacy = sum(1 for r in enriched if not r.get("legacy_explanation"))
    empty_planner = sum(1 for r in enriched if not r.get("planner_explanation"))
    fallback_count = sum(1 for r in enriched if r.get("is_fallback"))
    legacy_lens = [len(r["legacy_explanation"]) for r in enriched if r.get("legacy_explanation")]
    planner_lens = [len(r["planner_explanation"]) for r in enriched if r.get("planner_explanation")]

    print(f"\n[enrich] === Results ===")
    print(f"  Total:           {len(enriched)}")
    print(f"  Both filled:     {has_both}")
    print(f"  Empty legacy:    {empty_legacy}")
    print(f"  Empty planner:   {empty_planner}")
    print(f"  Fallbacks:       {fallback_count}")
    if legacy_lens:
        print(f"  Legacy avg len:  {sum(legacy_lens)/len(legacy_lens):.0f} chars")
    if planner_lens:
        print(f"  Planner avg len: {sum(planner_lens)/len(planner_lens):.0f} chars")

    # Output
    if args.output:
        out_path = Path(args.output)
    else:
        stem = input_path.stem.replace("_merged", "")
        out_path = input_path.parent / f"{stem}_with_explanations.json"

    if wrapper is not None:
        wrapper["records"] = enriched
        wrapper["total"] = len(enriched)
        output = wrapper
    else:
        output = enriched

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n[enrich] Output: {out_path}")


if __name__ == "__main__":
    main()
