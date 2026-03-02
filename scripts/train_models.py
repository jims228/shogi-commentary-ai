#!/usr/bin/env python3
"""Train all ML models (FocusPredictor + ImportancePredictor).

Usage:
    python scripts/train_models.py
    python scripts/train_models.py --data data/annotated/merged_corpus.jsonl
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.api.services.focus_predictor import FocusPredictor
from backend.api.services.importance_predictor import ImportancePredictor

_DEFAULT_DATA = PROJECT_ROOT / "data" / "annotated" / "merged_corpus.jsonl"


def _resolve_data_path(path: str | None) -> str:
    if path:
        return path
    if _DEFAULT_DATA.exists():
        return str(_DEFAULT_DATA)
    return str(PROJECT_ROOT / "data" / "annotated")


def train_focus(data_path: str) -> None:
    print("=" * 56)
    print("  FocusPredictor")
    print("=" * 56)

    fp = FocusPredictor()
    result = fp.train(data_path)

    if result.get("error"):
        print(f"  Error: {result['error']}")
        return

    print(f"  Samples:      {result['n_samples']}")
    print(f"  Labels:       {result['n_labels']}")
    print(f"  Train F1:     {result['f1_macro']:.4f} (macro), {result['f1_samples']:.4f} (samples)")
    print(f"  Distribution: {result['label_distribution']}")

    ev = fp.evaluate(data_path, n_splits=5)
    if not ev.get("error"):
        print(f"  CV F1 macro:  {ev['mean_f1_macro']:.4f}")
        print(f"  CV F1 sample: {ev['mean_f1_samples']:.4f}")
        if "per_label_f1" in ev:
            print("  Per-label F1:")
            for lbl, f1 in ev["per_label_f1"].items():
                print(f"    {lbl:25s} {f1:.4f}")

    save_path = fp.save()
    print(f"  Saved: {save_path}")
    print()


def train_importance(data_path: str) -> None:
    print("=" * 56)
    print("  ImportancePredictor")
    print("=" * 56)

    ip = ImportancePredictor()
    result = ip.train(data_path)

    if result.get("error"):
        print(f"  Error: {result['error']}")
        return

    print(f"  Samples:         {result['n_samples']}")
    print(f"  Mean importance: {result['mean_importance']:.4f}")
    print(f"  Std importance:  {result['std_importance']:.4f}")
    print(f"  Train R²:        {result['train_r2']:.4f}")
    print(f"  Train MAE:       {result['train_mae']:.4f}")

    ev = ip.evaluate(data_path, n_splits=5)
    if not ev.get("error"):
        print(f"  CV R²:           {ev['mean_r2']:.4f} ± {ev['std_r2']:.4f}")
        print(f"  CV MAE:          {ev['mean_mae']:.4f} ± {ev['std_mae']:.4f}")

    save_path = ip.save()
    print(f"  Saved: {save_path}")

    # Test prediction
    test_features = {
        "king_safety": 30, "piece_activity": 65, "attack_pressure": 45,
        "phase": "midgame", "ply": 50, "move_intent": "attack",
        "tension_delta": {
            "d_king_safety": -10.0,
            "d_piece_activity": 5.0,
            "d_attack_pressure": 15.0,
        },
    }
    pred = ip.predict(test_features)
    should = ip.should_explain(test_features)
    print(f"  Test: importance={pred:.2f}, should_explain={should}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Train all ML models")
    parser.add_argument(
        "--data", default=None,
        help=f"Data path (default: {_DEFAULT_DATA})",
    )
    args = parser.parse_args()
    data_path = _resolve_data_path(args.data)

    print()
    print("  Shogi Commentary AI - Model Training")
    print()

    train_focus(data_path)
    train_importance(data_path)

    print("  All models trained successfully.")
    print()


if __name__ == "__main__":
    main()
