#!/usr/bin/env python3
"""Train FocusPredictor on merged annotated corpus."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.api.services.focus_predictor import FocusPredictor


def main():
    predictor = FocusPredictor()

    # 訓練
    data_path = PROJECT_ROOT / "data" / "annotated" / "merged_corpus.jsonl"
    if not data_path.exists():
        # merged がなければ annotated_corpus.jsonl + diverse_commentary.jsonl を直接使う
        data_path = PROJECT_ROOT / "data" / "annotated"

    print("Training FocusPredictor...")
    train_result = predictor.train(str(data_path))
    print(f"  Samples: {train_result.get('n_samples', 0)}")
    print(f"  Labels:  {train_result.get('n_labels', 0)}")
    print(f"  Distribution: {train_result.get('label_distribution', {})}")

    # 評価
    print("\nEvaluating (5-fold CV)...")
    eval_result = predictor.evaluate(str(data_path), n_splits=5)
    print(f"  Accuracy:  {eval_result.get('mean_accuracy', 0):.4f} ± {eval_result.get('std_accuracy', 0):.4f}")
    print(f"  F1 macro:  {eval_result.get('mean_f1_macro', 0):.4f}")
    print(f"  F1 sample: {eval_result.get('mean_f1_samples', 0):.4f}")

    if 'per_label_f1' in eval_result:
        print("\n  Per-label F1:")
        for label, f1 in eval_result['per_label_f1'].items():
            print(f"    {label:25s} {f1:.4f}")

    # 保存
    save_path = predictor.save()
    print(f"\nModel saved: {save_path}")

    # 確認: predict してみる
    test_features = {
        "king_safety": 30, "piece_activity": 65, "attack_pressure": 45,
        "phase": "midgame", "ply": 50,
        "tension_delta": {"d_king_safety": -10.0, "d_piece_activity": 5.0, "d_attack_pressure": 15.0}
    }
    prediction = predictor.predict(test_features)
    print(f"\nTest prediction: {prediction}")


if __name__ == "__main__":
    main()
