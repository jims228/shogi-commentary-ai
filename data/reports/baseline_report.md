# 将棋AI解説システム - ベースラインレポート

Generated: 2026-03-02T20:23:26 UTC

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
| Training log records | 356 |
| Batch commentary records | 50 |
| Feature dimensions | 8 |

### Phase Distribution

| Phase | Count | Percentage |
|-------|-------|-----------|
| opening | 56 | 36.8% |
| midgame | 46 | 30.3% |
| endgame | 50 | 32.9% |

## 3. Quality Evaluation

- Evaluated records: 356
- Average total score: 69.0
- Low quality count (< 40): 0

### Per-Axis Scores

| Axis | Weight | Average |
|------|--------|---------|
| context_relevance | 0.30 | 82.9 |
| naturalness | 0.25 | 65.4 |
| informativeness | 0.25 | 43.9 |
| readability | 0.20 | 83.9 |

### Score by Phase

| Phase | Average Score |
|-------|--------------|
| endgame | 72.6 |
| midgame | 68.1 |
| opening | 69.0 |

## 4. ML Model Comparison

- Samples: 356
- CV folds: 5
- Best model: **RandomForest**

| Model | Accuracy | F1-macro | Train Time (s) |
|-------|----------|----------|----------------|
| DecisionTree | 0.96 +/- 0.02 | 0.96 +/- 0.02 | 0.02 |
| **RandomForest** | 0.96 +/- 0.02 | 0.96 +/- 0.02 | 0.66 |
| GradientBoosting | 0.96 +/- 0.02 | 0.96 +/- 0.02 | 0.48 |

### Training Data Style Distribution

| Style | Count | Percentage |
|-------|-------|-----------|
| technical | 0 | 0.0% |
| encouraging | 191 | 53.7% |
| dramatic | 0 | 0.0% |
| neutral | 165 | 46.3% |

## 5. Feature Importance

### Consensus Ranking (3 methods: tree, permutation, correlation)

| Rank | Feature | Avg Rank |
|------|---------|----------|
| 1 | ply | 1.33 |
| 2 | king_safety | 2.67 |
| 3 | piece_activity | 3.00 |
| 4 | d_king_safety | 4.33 |
| 5 | d_piece_activity | 5.33 |
| 6 | phase_num | 6.00 |
| 7 | attack_pressure | 6.67 |
| 8 | d_attack_pressure | 6.67 |

### Tree-based (RandomForest)

- ply: 0.3505
- piece_activity: 0.2075
- king_safety: 0.1359
- d_piece_activity: 0.1328
- d_king_safety: 0.1248
- d_attack_pressure: 0.0209
- attack_pressure: 0.0139
- phase_num: 0.0136

### Permutation Importance

- piece_activity: 0.1486
- ply: 0.0992
- king_safety: 0.0357
- d_piece_activity: 0.0124
- d_king_safety: 0.0028
- phase_num: 0.0008
- d_attack_pressure: 0.0003
- attack_pressure: 0.0000

### Target Correlation (|r|)

- ply: 0.7031
- king_safety: 0.3490
- d_king_safety: 0.2844
- phase_num: 0.2841
- attack_pressure: 0.2759
- piece_activity: 0.1376
- d_attack_pressure: 0.0355
- d_piece_activity: 0.0281

## 6. Style Classification Analysis

### Class Balance

| Style | Percentage |
|-------|-----------|
| technical | 0.0% |
| encouraging | 53.7% |
| dramatic | 0.0% |
| neutral | 46.3% |

### Phase x Style Cross-tabulation

| Phase | technical | encouraging | dramatic | neutral |
|-------|-------|-------|-------|-------|
| endgame | 0 | 2 | 0 | 0 |
| midgame | 0 | 30 | 0 | 0 |
| opening | 0 | 159 | 0 | 165 |

### Warnings

> **Warning**: Class imbalance: 'technical' has only 0.0% of samples (0/356)
> **Warning**: Class imbalance: 'dramatic' has only 0.0% of samples (0/356)

## 7. Issues and Next Steps

### Known Issues

- Class imbalance: 'technical' has only 0.0% of samples (0/356)
- Class imbalance: 'dramatic' has only 0.0% of samples (0/356)

### Next Steps

- Gemini API連携による解説品質の向上
- 訓練データ500件目標への蓄積
- クラス不均衡への対処 (データ拡張・リサンプリング)
- ハイパーパラメータチューニングの実施
- 追加特徴量の検討 (material balance, tempo)
