#!/usr/bin/env python3
"""アノテーションデータ統合ユーティリティ.

data/annotated/ 以下の全JSONLファイルを統合して
merged_corpus.jsonl を生成する。

Usage:
    python scripts/merge_annotations.py
    python scripts/merge_annotations.py --dry-run
    python scripts/merge_annotations.py --output data/annotated/custom_merged.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from backend.api.schemas.annotation import DEPTH_LEVELS, FOCUS_LABELS
from backend.api.services.ml_trainer import STYLES

_DATA_DIR = _PROJECT_ROOT / "data"
_ANNOTATED_DIR = _DATA_DIR / "annotated"
_DEFAULT_OUTPUT = _ANNOTATED_DIR / "merged_corpus.jsonl"


def _dedup_key(record: Dict[str, Any]) -> str:
    """sfen + ply + source で重複判定キーを生成."""
    sfen = record.get("sfen", "")
    ply = record.get("ply", 0)
    source = record.get("source", "")
    text = record.get("original_text", "")[:50]
    return f"{sfen}|{ply}|{source}|{text}"


def merge_annotations(
    input_dir: Path = _ANNOTATED_DIR,
    output_path: Path = _DEFAULT_OUTPUT,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """全JSONLファイルを統合.

    Parameters
    ----------
    input_dir : Path
        入力ディレクトリ。
    output_path : Path
        出力先 JSONL ファイル。
    dry_run : bool
        True の場合ファイル書き出しをスキップ。

    Returns
    -------
    dict
        統計情報。
    """
    if not input_dir.is_dir():
        print(f"  Input directory not found: {input_dir}")
        return {"total": 0, "merged": 0, "duplicates": 0}

    # Collect all JSONL files except the output itself
    jsonl_files = sorted([
        f for f in input_dir.iterdir()
        if f.suffix == ".jsonl" and f.name != output_path.name
    ])

    if not jsonl_files:
        print("  No JSONL files found to merge.")
        return {"total": 0, "merged": 0, "duplicates": 0}

    seen_keys: Set[str] = set()
    merged: List[Dict[str, Any]] = []
    file_stats: List[Dict[str, Any]] = []
    total_read = 0
    duplicates = 0

    style_counts: Counter[str] = Counter()
    focus_counts: Counter[str] = Counter()
    depth_counts: Counter[str] = Counter()
    importance_sum = 0.0

    for path in jsonl_files:
        file_count = 0
        file_dups = 0
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue

                total_read += 1
                key = _dedup_key(obj)
                if key in seen_keys:
                    duplicates += 1
                    file_dups += 1
                    continue
                seen_keys.add(key)

                merged.append(obj)
                file_count += 1

                ann = obj.get("annotation", {})
                style_counts[ann.get("style", "unknown")] += 1
                for lbl in ann.get("focus", []):
                    focus_counts[lbl] += 1
                depth_counts[ann.get("depth", "unknown")] += 1
                importance_sum += ann.get("importance", 0)

        file_stats.append({
            "file": path.name,
            "records": file_count,
            "duplicates": file_dups,
        })

    n = len(merged)

    # Print summary
    print()
    print("=" * 60)
    print("  Annotation Merge Summary")
    print("=" * 60)

    print()
    print("  [Source Files]")
    for fs in file_stats:
        dup_note = f" ({fs['duplicates']} dups)" if fs["duplicates"] else ""
        print(f"    {fs['file']:<35} {fs['records']:>4} records{dup_note}")

    print()
    print(f"  Total read:    {total_read}")
    print(f"  Duplicates:    {duplicates}")
    print(f"  Merged:        {n}")

    if n > 0:
        print()
        print("  [Style Distribution]")
        for s in STYLES:
            cnt = style_counts.get(s, 0)
            pct = f"{cnt / n * 100:.1f}%"
            print(f"    {s:<14} {cnt:>4} ({pct})")
        unknown_style = style_counts.get("unknown", 0)
        if unknown_style:
            print(f"    {'unknown':<14} {unknown_style:>4}")

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
        avg_imp = round(importance_sum / n, 3)
        print(f"  Avg importance: {avg_imp}")

    if dry_run:
        print()
        print("  [DRY RUN] No files written.")
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            for rec in merged:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print()
        print(f"  Output: {output_path}")

    print()
    print("=" * 60)
    print()

    return {
        "total_read": total_read,
        "merged": n,
        "duplicates": duplicates,
        "files": file_stats,
        "style_distribution": dict(style_counts),
        "focus_distribution": dict(focus_counts),
        "depth_distribution": dict(depth_counts),
        "avg_importance": round(importance_sum / max(1, n), 3),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Merge all annotation JSONL files"
    )
    parser.add_argument(
        "--input-dir", default=None,
        help=f"Input directory (default: {_ANNOTATED_DIR})",
    )
    parser.add_argument(
        "--output", default=None,
        help=f"Output path (default: {_DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show summary without writing files",
    )
    args = parser.parse_args()

    in_dir = Path(args.input_dir) if args.input_dir else _ANNOTATED_DIR
    out = Path(args.output) if args.output else _DEFAULT_OUTPUT
    merge_annotations(input_dir=in_dir, output_path=out, dry_run=args.dry_run)
