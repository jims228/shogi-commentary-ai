# 将棋AI解説システム - ベースラインレポート

Generated: 2026-03-02T19:26:29 UTC

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
| Training log records | 322 |
| Batch commentary records | 50 |
| Feature dimensions | 8 |

### Phase Distribution

| Phase | Count | Percentage |
|-------|-------|-----------|
| opening | 56 | 36.8% |
| midgame | 46 | 30.3% |
| endgame | 50 | 32.9% |

## 3. Quality Evaluation

- Evaluated records: 322
- Average total score: 69.0
- Low quality count (< 40): 0

### Per-Axis Scores

| Axis | Weight | Average |
|------|--------|---------|
| context_relevance | 0.30 | 82.9 |
| naturalness | 0.25 | 65.4 |
| informativeness | 0.25 | 43.8 |
| readability | 0.20 | 83.9 |

### Score by Phase

| Phase | Average Score |
|-------|--------------|
| endgame | 72.6 |
| midgame | 68.1 |
| opening | 69.0 |

## 4. ML Model Comparison

- Samples: 322
- CV folds: 5
- Best model: **DecisionTree**

| Model | Accuracy | F1-macro | Train Time (s) |
|-------|----------|----------|----------------|
| **DecisionTree** | 0.96 +/- 0.03 | 0.96 +/- 0.03 | 0.02 |
| RandomForest | 0.96 +/- 0.01 | 0.96 +/- 0.01 | 0.56 |
| GradientBoosting | 0.96 +/- 0.03 | 0.96 +/- 0.03 | 0.47 |

### Training Data Style Distribution

| Style | Count | Percentage |
|-------|-------|-----------|
| technical | 0 | 0.0% |
| encouraging | 174 | 54.0% |
| dramatic | 0 | 0.0% |
| neutral | 148 | 46.0% |

## 5. Feature Importance

### Consensus Ranking (3 methods: tree, permutation, correlation)

| Rank | Feature | Avg Rank |
|------|---------|----------|
| 1 | ply | 1.00 |
| 2 | king_safety | 2.67 |
| 3 | piece_activity | 3.33 |
| 4 | d_king_safety | 4.67 |
| 5 | d_piece_activity | 5.33 |
| 6 | attack_pressure | 6.33 |
| 7 | d_attack_pressure | 6.33 |
| 8 | phase_num | 6.33 |

### Tree-based (RandomForest)

- ply: 0.3723
- piece_activity: 0.1946
- king_safety: 0.1339
- d_piece_activity: 0.1317
- d_king_safety: 0.1160
- d_attack_pressure: 0.0236
- attack_pressure: 0.0141
- phase_num: 0.0139

### Permutation Importance

- ply: 0.2385
- piece_activity: 0.1342
- king_safety: 0.0422
- d_piece_activity: 0.0102
- d_king_safety: 0.0028
- d_attack_pressure: 0.0003
- attack_pressure: 0.0000
- phase_num: 0.0000

### Target Correlation (|r|)

- ply: 0.6989
- king_safety: 0.3458
- phase_num: 0.2871
- d_king_safety: 0.2743
- attack_pressure: 0.2718
- piece_activity: 0.1288
- d_attack_pressure: 0.0340
- d_piece_activity: 0.0311

## 6. Style Classification Analysis

### Class Balance

| Style | Percentage |
|-------|-----------|
| technical | 0.0% |
| encouraging | 54.0% |
| dramatic | 0.0% |
| neutral | 46.0% |

### Phase x Style Cross-tabulation

| Phase | technical | encouraging | dramatic | neutral |
|-------|-------|-------|-------|-------|
| endgame | 0 | 2 | 0 | 0 |
| midgame | 0 | 28 | 0 | 0 |
| opening | 0 | 144 | 0 | 148 |

### Warnings

> **Warning**: Class imbalance: 'technical' has only 0.0% of samples (0/322)
> **Warning**: Class imbalance: 'dramatic' has only 0.0% of samples (0/322)

## 7. Issues and Next Steps

### Known Issues

- Class imbalance: 'technical' has only 0.0% of samples (0/322)
- Class imbalance: 'dramatic' has only 0.0% of samples (0/322)

### Next Steps

- Gemini API連携による解説品質の向上
- 訓練データ500件目標への蓄積
- クラス不均衡への対処 (データ拡張・リサンプリング)
- ハイパーパラメータチューニングの実施
- 追加特徴量の検討 (material balance, tempo)
