#!/usr/bin/env python3
"""解説スタイル選択モデルの学習CLI.

Usage:
    python scripts/train_style_model.py
    python scripts/train_style_model.py --log-dir data/training_logs --model-path data/models/style_selector.joblib
    python scripts/train_style_model.py --evaluate
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from backend.api.services.ml_trainer import CommentaryStyleSelector, _HAS_SKLEARN


def main() -> None:
    parser = argparse.ArgumentParser(
        description="解説スタイル選択モデルの学習"
    )
    parser.add_argument(
        "--log-dir",
        default=None,
        help="トレーニングログのディレクトリ (default: data/training_logs)",
    )
    parser.add_argument(
        "--model-path",
        default=None,
        help="モデル保存先 (default: data/models/style_selector.joblib)",
    )
    parser.add_argument(
        "--min-samples",
        type=int,
        default=10,
        help="最小サンプル数 (default: 10)",
    )
    parser.add_argument(
        "--evaluate",
        action="store_true",
        help="学習後に全データで評価を表示",
    )
    args = parser.parse_args()

    if not _HAS_SKLEARN:
        print("Error: scikit-learn is not installed.", file=sys.stderr)
        print("Run: pip install scikit-learn joblib", file=sys.stderr)
        sys.exit(1)

    print("Training style selector model...")
    sel = CommentaryStyleSelector()
    result = sel.train(log_dir=args.log_dir)

    if "error" in result:
        print(f"Error: {result['error']}", file=sys.stderr)
        print(f"  Samples found: {result['samples']}", file=sys.stderr)
        if result["samples"] < args.min_samples:
            print(
                f"  Need at least {args.min_samples} samples. "
                "Generate more commentary data first.",
                file=sys.stderr,
            )
        sys.exit(1)

    print(f"  Samples: {result['samples']}")
    print(f"  Accuracy: {result['accuracy']}")
    print(f"  Distribution: {result['distribution']}")

    saved_path = sel.save(args.model_path)
    print(f"  Model saved to: {saved_path}")

    if args.evaluate:
        print("\nEvaluation on training data:")
        from backend.api.services.ml_trainer import rule_based_predict, _features_to_vector
        # Already printed accuracy above
        print(f"  Training accuracy: {result['accuracy']}")

    print("\nDone.")


if __name__ == "__main__":
    main()
