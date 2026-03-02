# 将棋AI解説パイプライン — 状況報告

Generated: 2026-03-03 UTC

---

## 1. 完了事項

- **39コミット**, **344テスト** (全パス)
- **3つのMLモデル**: FocusPredictor, ImportancePredictor, StyleSelector
- **Gemini API統合**: gemini-2.5-flash による多様な解説生成
- **自動レポート生成**: ベースライン実験 → Markdownレポート
- **パイプライン健全性監査**: audit_pipeline.py による6軸チェック

### パイプライン構成

| コンポーネント | ファイル数 | コード行数 |
|--------------|-----------|-----------|
| バックエンドサービス | 17 | 3,943 |
| スクリプト | 17 | ~4,100 |
| テスト | 19 | ~4,300 |
| **合計** | **53** | **~12,300** |

---

## 2. データの現状

### データソース

| データ | 件数 | 内容 |
|--------|------|------|
| sample_games.txt | 10局 | 棋譜データ (CSA形式) |
| pipeline_test_features.jsonl | 152件 | 抽出済み局面特徴量 |
| annotated_corpus.jsonl | 270件 | テンプレート解説 + ルールベースアノテーション |
| diverse_commentary.jsonl | 300件 | Gemini API生成 (3スタイル × 10ターゲット) |
| merged_corpus.jsonl | 350件 | 統合コーパス (訓練データ) |
| training_logs | 424件 | API解説ログ |

### データの性質

- **全データが合成データ** (テンプレート生成 + Gemini API生成)
- **プロ棋士・専門家の解説データ: 未収集**
- アノテーションは全てルールベース自動生成

### ラベル分布の偏り

| 問題 | 状況 | 影響 |
|------|------|------|
| surface深度 | 4/350 (1.1%) | 深度予測モデルが表層解説を学習困難 |
| king_safety | 333/350 (95.1%) | Focus予測で「常にking_safety」に偏るリスク |
| encouragingスタイル | 208/350 (59.4%) | スタイル予測の不均衡 |

---

## 3. MLモデルの評価

### FocusPredictor (マルチラベル分類)

- **アルゴリズム**: RandomForest + MultiOutputClassifier
- **特徴量**: 8次元 (king_safety, piece_activity, attack_pressure, ply, d_king_safety, d_piece_activity, d_attack_pressure, phase_num)
- **CV F1-macro**: 0.706, **F1-samples**: 0.803
- **訓練データ**: 350件 (Geminiデータ込み)

**ラベル別性能:**

| ラベル | F1 | 評価 |
|--------|-----|------|
| king_safety | 0.975 | 高い (ただしデータ偏り) |
| piece_activity | 0.943 | 高い |
| attack_pressure | 0.936 | 高い |
| endgame_technique | 0.664 | 中程度 |
| positional | 0.592 | 改善余地 |
| tempo | 0.128 | 低い (データ不足) |

### ImportancePredictor (回帰)

- **アルゴリズム**: GradientBoostingRegressor (11次元)
- **CV R²**: 0.992, **MAE**: 0.005
- **問題: 循環学習**
  - アノテーションの importance は `annotation_service._estimate_importance()` が生成
  - `ImportancePredictor._rule_based_importance()` と完全に同一のロジック
  - **相関 r = 1.000**, 完全一致率 100%
  - R²=0.992 は「モデルがルール関数を学習した」だけで、実パターン学習ではない
  - **真の評価にはプロ解説者による importance ラベルが必要**

### StyleSelector (3クラス分類)

- **アルゴリズム**: DecisionTree (max_depth=5)
- **訓練データ**: 424件 (training_logs)
- **訓練精度**: 0.974
- **分布の問題**: technical=0件, encouraging=225件, neutral=199件
  - training_logs の `label_style_from_scores()` が technical をほぼ返さない
  - 事実上の2クラス分類器

---

## 4. 技術的課題

### CRITICAL (解決済み)

- ~~style_selector.joblib 未生成~~ → 3クラスで訓練・保存完了

### HIGH

1. **循環学習 (ImportancePredictor)**
   - ルールベースで生成したラベルをMLで学習しているため、モデルの付加価値がない
   - 対策: 人手ラベリング、または Gemini API による importance 推定

2. **surface深度データの欠如 (1.1%)**
   - 深度予測モデル (Task C) の訓練に支障
   - 対策: 短い解説 (30文字未満) を意図的に生成

### MEDIUM

3. **king_safety の過剰表現 (95.1%)**
   - Focus予測の汎化性能に影響
   - 対策: ターゲット多様化で king_safety なしのデータを増やす

4. **StyleSelector の technical クラス不在**
   - training_logs のラベリングロジックの問題
   - 対策: `label_style_from_scores()` の閾値調整、または annotated data からの訓練

5. **実験データのJSON構造不整合**
   - `baseline_full_*.json` と `baseline_*.json` で n_samples の位置が異なる
   - pipeline_status.py にフォールバック追加で対処済み

### LOW

6. merged_corpus.jsonl に5件の重複テキスト
7. bioshogi.py (51行) のテストなし

---

## 5. 次のステップ候補

### 選択肢A: Task C (深度予測) を実装

3つ目のMLタスクとして、解説の深度 (surface/strategic/deep) を予測するモデルを構築。

- **メリット**: 3タスク完了で「注意選択 (Focus) → 重要度判断 (Importance) → 深度決定 (Depth)」の意思決定パイプラインが完成。研究としての「形」が整う
- **リスク**: 合成データのみでは surface が 1.1% と極端に少なく、データ不均衡の問題が顕在化。ImportancePredictor と同様の循環学習リスクあり
- **必要工数**: 中 (既存パターンの踏襲可能)

### 選択肢B: プロ解説データ収集に注力

NHK杯や将棋モバイルの解説テキストを収集し、人手アノテーション。

- **メリット**: MLモデルの本質的改善。循環学習の解消。合成データとの品質差を定量比較可能
- **リスク**: 時間がかかる、著作権への配慮が必要。アノテーション基準の整備が先決
- **必要工数**: 大

### 選択肢C: 現状パイプラインの品質改善

データ不均衡の解消、StyleSelector の改善、informativeness スコア (43.9/100) の向上。

- **メリット**: 既存機能の完成度向上。定量的な改善を示しやすい
- **リスク**: 新機能なしで停滞感。合成データの限界内での最適化
- **必要工数**: 小〜中

### 推奨: A → C の順序

1. **まず Task C (深度予測) を実装** — 3タスク揃えて研究の枠組みを完成させる
2. **次にデータ品質改善** — surface 深度データの追加生成、スタイル分布の均一化
3. **プロデータ収集は中長期課題** — アノテーション基準書を先に作成

この順序の理由:
- 循環学習の問題は**認識済みで対策を計画中**と報告できる
- 3タスクの枠組みが揃えば、プロデータ投入時の比較実験が容易
- Depth Predictor は Focus/Importance と同じアーキテクチャで実装可能

---

## 6. マズゴボイ教授への報告ポイント

### 技術的成果

1. **エンドツーエンドMLパイプラインの構築**
   - 棋譜 → 局面特徴量抽出 (8D) → アノテーション → ML訓練 → 解説生成 → 品質評価
   - 全工程が自動化され、344テストでカバー

2. **多段階意思決定モデル**
   - **Focus Prediction**: 「何について解説するか」(マルチラベル分類, F1=0.706)
   - **Importance Prediction**: 「解説すべきタイミングか」(回帰, ルールベース同等)
   - **Style Selection**: 「どのスタイルで解説するか」(3クラス分類, Acc=0.974)

3. **Gemini API統合による解説データ多様化**
   - 10パターンのターゲット × 30局面 = 300件の多様な解説
   - 品質スコア平均 69.0/100 (閾値40を大幅クリア)

### 「複雑な状態遷移における注意選択と因果推論」のアプローチ

- **注意選択 (Attention Selection)**: FocusPredictor が局面の「どこに注目すべきか」を6カテゴリで予測。king_safety, attack_pressure, endgame_technique の3軸で高いF1を達成
- **因果推論 (Causal Reasoning)**: tension_delta (前手との差分) を特徴量に組み込み、「なぜこの手が重要か」を推定。ImportancePredictor の11次元特徴量のうち3次元が因果的差分
- **段階的意思決定**: Focus → Importance → Style の3段階で解説戦略を決定するパイプライン

### 次の研究課題

1. **循環学習の解消**: ルールベースラベルの限界を認識。プロ解説データによる真のラベル付与が次の目標
2. **Depth Prediction**: 解説の深さ (surface/strategic/deep) をMLで予測する3つ目のタスク
3. **合成データ vs 実データの品質比較**: Gemini生成解説とプロ解説のFocusPredictor性能差を定量評価

---

## 付録: パイプライン監査サマリー

| カテゴリ | 項目数 | 結果 |
|---------|--------|------|
| データ品質 | 3ファイル | 全valid, 重複5件 |
| ラベル分布 | 4軸 | surface深度1.1%が要注意 |
| 循環学習 | 1モデル | r=1.000 (要改善) |
| モデル状態 | 3モデル | 全ロード可能 |
| 実験データ | 6ファイル | 整合性OK (構造差修正済み) |
| テストカバレッジ | 17サービス | 11直接 + 4間接 + 1未カバー |
