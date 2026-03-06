"""scripts/merge_eval_batch.py

Merge multiple eval batch JSON files into a single deduplicated eval set.

Usage:
  python scripts/merge_eval_batch.py data/human_eval/swars_batch/*.json
  python scripts/merge_eval_batch.py data/human_eval/swars_batch/*.json -o data/human_eval/swars_eval_merged.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def load_records(path: Path) -> list[dict]:
    """Load records from JSON. Supports {"records":[...]} and plain [...]."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "records" in data:
        return data["records"]
    print(f"  [warn] Unknown format in {path.name}, skipping")
    return []


def merge(files: list[Path]) -> tuple[list[dict], int, dict]:
    """Merge records from files, dedup by (sfen, user_move, ply).

    Returns (records, duplicates_removed, scoring_guide).
    """
    all_records: list[dict] = []
    seen: set[tuple] = set()
    dupes = 0
    scoring_guide: dict = {}

    for fpath in sorted(files):
        with open(fpath, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            recs = data.get("records", [])
            if not scoring_guide and "scoring_guide" in data:
                scoring_guide = data["scoring_guide"]
        elif isinstance(data, list):
            recs = data
        else:
            print(f"  [warn] Unknown format in {fpath.name}, skipping")
            continue

        for rec in recs:
            key = (rec.get("sfen", ""), rec.get("user_move", ""), rec.get("ply", 0))
            if key in seen:
                dupes += 1
                continue
            seen.add(key)
            all_records.append(rec)

        print(f"  [load] {fpath.name}: {len(recs)} records")

    return all_records, dupes, scoring_guide


def main():
    parser = argparse.ArgumentParser(description="Merge eval batch JSONs")
    parser.add_argument("inputs", nargs="+", help="JSON files to merge")
    parser.add_argument(
        "-o", "--output",
        default="data/human_eval/swars_eval_merged.json",
        help="Output path (default: data/human_eval/swars_eval_merged.json)",
    )
    args = parser.parse_args()

    import glob as glob_mod
    files: list[Path] = []
    for pattern in args.inputs:
        expanded = glob_mod.glob(pattern)
        if expanded:
            files.extend(Path(p) for p in sorted(expanded))
        else:
            files.append(Path(pattern))

    if not files:
        print("[merge] No input files")
        sys.exit(1)

    print(f"[merge] {len(files)} file(s)")
    records, dupes, scoring_guide = merge(files)

    # Re-assign sequential IDs
    for i, rec in enumerate(records):
        rec["id"] = f"eval_{i+1:03d}"

    payload = {
        "version": "2.0",
        "created": datetime.now(timezone.utc).isoformat(),
        "total": len(records),
        "scoring_guide": scoring_guide,
        "records": records,
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"\n[merge] Input records: {len(records) + dupes}")
    print(f"[merge] Duplicates removed: {dupes}")
    print(f"[merge] Output: {len(records)} records -> {out_path}")


if __name__ == "__main__":
    main()
