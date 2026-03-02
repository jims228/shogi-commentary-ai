# 将棋AI解説システム - ベースラインレポート

Generated: 2026-03-02T18:52:53 UTC

## 1. Project Overview

将棋局面の自然言語解説を自動生成するMLパイプラインのベースライン実験結果。

### Pipeline Components

1. **Feature Extraction**: 8次元の局面特徴量 (king_safety, piece_activity, attack_pressure, ply, d_king_safety, d_piece_activity, d_attack_pressure, phase_num)
2. **Commentary Generation**: テンプレートベース (dry-run) および Gemini API
3. **Quality Evaluation**: ルールベース4軸スコアリング (context_relevance, naturalness, informativeness, readability)
4. **Style Classification**: ML自動ラベリング → 4スタイル (technical, encouraging, dramatic, neutral)

## 2. Dataset Statistics

| Metric | Value |
|--------|-------|
| Sample games | 10 |
| Pipeline features | 152 |
| Training log records | 220 |
| Batch commentary records | 50 |
| Feature dimensions | 8 |

### Phase Distribution

| Phase | Count | Percentage |
|-------|-------|-----------|
| opening | 56 | 36.8% |
| midgame | 46 | 30.3% |
| endgame | 50 | 32.9% |

## 3. Quality Evaluation

- Evaluated records: 220
- Average total score: 69.0
- Low quality count (< 40): 0

### Per-Axis Scores

| Axis | Weight | Average |
|------|--------|---------|
| context_relevance | 0.30 | 83.0 |
| naturalness | 0.25 | 65.6 |
| informativeness | 0.25 | 43.8 |
| readability | 0.20 | 83.8 |

### Score by Phase

| Phase | Average Score |
|-------|--------------|
| endgame | 72.6 |
| midgame | 68.3 |
| opening | 69.1 |

## 4. ML Model Comparison

- Samples: 220
- CV folds: 5
- Best model: **RandomForest**

| Model | Accuracy | F1-macro | Train Time (s) |
|-------|----------|----------|----------------|
| DecisionTree | 0.95 +/- 0.03 | 0.95 +/- 0.03 | 0.03 |
| **RandomForest** | 0.97 +/- 0.02 | 0.97 +/- 0.02 | 0.49 |
| GradientBoosting | 0.96 +/- 0.03 | 0.96 +/- 0.03 | 0.51 |

### Training Data Style Distribution

| Style | Count | Percentage |
|-------|-------|-----------|
| technical | 0 | 0.0% |
| encouraging | 123 | 55.9% |
| dramatic | 0 | 0.0% |
| neutral | 97 | 44.1% |

## 5. Feature Importance

### Consensus Ranking (3 methods: tree, permutation, correlation)

| Rank | Feature | Avg Rank |
|------|---------|----------|
| 1 | ply | 1.67 |
| 2 | king_safety | 2.33 |
| 3 | piece_activity | 3.00 |
| 4 | d_king_safety | 5.00 |
| 5 | d_piece_activity | 5.00 |
| 6 | phase_num | 5.67 |
| 7 | attack_pressure | 6.00 |
| 8 | d_attack_pressure | 7.33 |

### Tree-based (RandomForest)

- ply: 0.3263
- piece_activity: 0.2132
- king_safety: 0.1440
- d_piece_activity: 0.1364
- d_king_safety: 0.1305
- phase_num: 0.0235
- d_attack_pressure: 0.0140
- attack_pressure: 0.0120

### Permutation Importance

- piece_activity: 0.1500
- king_safety: 0.0695
- ply: 0.0632
- d_piece_activity: 0.0118
- d_king_safety: 0.0041
- attack_pressure: 0.0000
- d_attack_pressure: 0.0000
- phase_num: 0.0000

### Target Correlation (|r|)

- ply: 0.6789
- king_safety: 0.3304
- phase_num: 0.3000
- attack_pressure: 0.2563
- d_king_safety: 0.2269
- piece_activity: 0.0935
- d_piece_activity: 0.0451
- d_attack_pressure: 0.0280

## 6. Style Classification Analysis

### Class Balance

| Style | Percentage |
|-------|-----------|
| technical | 0.0% |
| encouraging | 55.9% |
| dramatic | 0.0% |
| neutral | 44.1% |

### Phase x Style Cross-tabulation

| Phase | technical | encouraging | dramatic | neutral |
|-------|-------|-------|-------|-------|
| endgame | 0 | 2 | 0 | 0 |
| midgame | 0 | 22 | 0 | 0 |
| opening | 0 | 99 | 0 | 97 |

### Warnings

> **Warning**: Class imbalance: 'technical' has only 0.0% of samples (0/220)
> **Warning**: Class imbalance: 'dramatic' has only 0.0% of samples (0/220)

## 7. Issues and Next Steps

### Known Issues

- Class imbalance: 'technical' has only 0.0% of samples (0/220)
- Class imbalance: 'dramatic' has only 0.0% of samples (0/220)

### Next Steps

- Gemini API連携による解説品質の向上
- 訓練データ500件目標への蓄積
- クラス不均衡への対処 (データ拡張・リサンプリング)
- ハイパーパラメータチューニングの実施
- 追加特徴量の検討 (material balance, tempo)
