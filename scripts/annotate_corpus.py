#!/usr/bin/env python3
"""既存解説データの自動アノテーション.

training_logs と batch_commentary のデータにルールベースの
アノテーションを付与して annotated_corpus.jsonl に保存する。

Usage:
    python scripts/annotate_corpus.py
    python scripts/annotate_corpus.py --dry-run
    python scripts/annotate_corpus.py --output data/annotated/custom.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

_DATA_DIR = _PROJECT_ROOT / "data"
_DEFAULT_OUTPUT = _DATA_DIR / "annotated" / "annotated_corpus.jsonl"


def _load_training_logs(log_dir: Path) -> List[Dict[str, Any]]:
    """training_logs/*.jsonl からレコードを読み込む."""
    records: List[Dict[str, Any]] = []
    if not log_dir.is_dir():
        return records
    for path in sorted(log_dir.iterdir()):
        if path.suffix != ".jsonl":
            continue
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    text = (obj.get("output") or {}).get("explanation", "")
                    features = (obj.get("input") or {}).get("features")
                    if text and features:
                        records.append({
                            "source_type": "training_log",
                            "source_file": path.name,
                            "text": text,
                            "features": features,
                            "sfen": (obj.get("input") or {}).get("sfen", ""),
                            "ply": features.get("ply", 0),
                            "model": (obj.get("output") or {}).get("model", ""),
                        })
                except Exception:
                    continue
    return records


def _load_batch_commentary(path: Path) -> List[Dict[str, Any]]:
    """batch_commentary.jsonl からレコードを読み込む."""
    records: List[Dict[str, Any]] = []
    if not path.exists():
        return records
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                text = obj.get("commentary", "")
                if not text:
                    continue
                # batch_commentary has quality.scores but features
                # need to be reconstructed from available fields
                features: Dict[str, Any] = {
                    "phase": obj.get("style", "midgame"),
                    "ply": obj.get("ply", 0),
                    "king_safety": 50,
                    "piece_activity": 50,
                    "attack_pressure": 0,
                    "tension_delta": {
                        "d_king_safety": 0.0,
                        "d_piece_activity": 0.0,
                        "d_attack_pressure": 0.0,
                    },
                }
                records.append({
                    "source_type": "batch_commentary",
                    "source_file": path.name,
                    "text": text,
                    "features": features,
                    "sfen": obj.get("sfen", ""),
                    "ply": obj.get("ply", 0),
                    "move": obj.get("move", ""),
                    "model": obj.get("source", ""),
                })
            except Exception:
                continue
    return records


def annotate_corpus(
    output_path: Path = _DEFAULT_OUTPUT,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """既存データを自動アノテーションして保存."""
    from backend.api.services.annotation_service import annotate_text
    from backend.api.schemas.annotation import validate_annotation

    # Load all records
    records: List[Dict[str, Any]] = []
    records.extend(_load_training_logs(_DATA_DIR / "training_logs"))
    records.extend(
        _load_batch_commentary(
            _DATA_DIR / "batch_commentary" / "batch_commentary.jsonl"
        )
    )

    if not records:
        print("  No records found to annotate.")
        return {"total": 0, "valid": 0}

    # Annotate
    annotated: List[Dict[str, Any]] = []
    focus_counts: Counter[str] = Counter()
    depth_counts: Counter[str] = Counter()
    importance_sum = 0.0
    validation_errors = 0

    for rec in records:
        ann = annotate_text(rec["text"], rec["features"])

        annotated_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": rec.get("model", "unknown"),
            "sfen": rec.get("sfen", ""),
            "ply": rec.get("ply", 0),
            "move": rec.get("move", ""),
            "features": rec["features"],
            "annotation": ann,
            "original_text": rec["text"],
            "annotator": "rule-based",
        }

        valid, errs = validate_annotation(annotated_record)
        if not valid:
            validation_errors += 1
            continue

        annotated.append(annotated_record)

        for label in ann["focus"]:
            focus_counts[label] += 1
        depth_counts[ann["depth"]] += 1
        importance_sum += ann["importance"]

    n = len(annotated)

    # Print summary
    print()
    print("=" * 56)
    print("  Annotation Summary")
    print("=" * 56)
    print(f"  Total records:       {len(records)}")
    print(f"  Annotated:           {n}")
    if validation_errors:
        print(f"  Validation errors:   {validation_errors}")
    print()

    print("  [Focus Distribution]")
    from backend.api.schemas.annotation import FOCUS_LABELS
    for label in FOCUS_LABELS:
        count = focus_counts.get(label, 0)
        pct = f"{count / n * 100:.1f}%" if n else "0%"
        print(f"    {label:<22} {count:>4} ({pct})")
    print()

    print("  [Depth Distribution]")
    from backend.api.schemas.annotation import DEPTH_LEVELS
    for level in DEPTH_LEVELS:
        count = depth_counts.get(level, 0)
        pct = f"{count / n * 100:.1f}%" if n else "0%"
        print(f"    {level:<22} {count:>4} ({pct})")
    print()

    avg_imp = round(importance_sum / n, 3) if n else 0
    print(f"  Avg importance:      {avg_imp}")
    print()

    if dry_run:
        print("  [DRY RUN] No files written.")
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            for rec in annotated:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"  Output: {output_path}")

    print("=" * 56)
    print()

    return {
        "total": len(records),
        "annotated": n,
        "validation_errors": validation_errors,
        "focus_distribution": dict(focus_counts),
        "depth_distribution": dict(depth_counts),
        "avg_importance": avg_imp,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Auto-annotate existing commentary data"
    )
    parser.add_argument(
        "--output", default=None,
        help=f"Output path (default: {_DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show results without writing files",
    )
    args = parser.parse_args()
    out = Path(args.output) if args.output else _DEFAULT_OUTPUT
    annotate_corpus(output_path=out, dry_run=args.dry_run)
