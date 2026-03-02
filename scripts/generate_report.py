#!/usr/bin/env python3
"""Generate Markdown research report from experiment results.

Usage:
    python scripts/generate_report.py
    python scripts/generate_report.py --experiment baseline
    python scripts/generate_report.py --output data/reports/custom_report.md
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

_DATA_DIR = _PROJECT_ROOT / "data"
_EXPERIMENTS_DIR = _DATA_DIR / "experiments"
_REPORTS_DIR = _DATA_DIR / "reports"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_latest_experiment(name: str = "baseline") -> Optional[Dict[str, Any]]:
    """Load the most recent experiment JSON matching name prefix."""
    if not _EXPERIMENTS_DIR.is_dir():
        return None
    matches = sorted([
        f for f in _EXPERIMENTS_DIR.iterdir()
        if f.name.startswith(name) and f.suffix == ".json"
    ])
    if not matches:
        return None
    with open(matches[-1], encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Section generators — each returns List[str] of Markdown lines
# ---------------------------------------------------------------------------
def _section_overview(data: Dict[str, Any]) -> List[str]:
    """Section 1: Project overview."""
    ts = data.get("timestamp", datetime.now(timezone.utc).isoformat())[:19]
    return [
        "# 将棋AI解説システム - ベースラインレポート",
        "",
        f"Generated: {ts} UTC",
        "",
        "## 1. Project Overview",
        "",
        "将棋局面の自然言語解説を自動生成するMLパイプラインのベースライン実験結果。",
        "",
        "### Pipeline Components",
        "",
        "1. **Feature Extraction**: 8次元の局面特徴量 "
        "(king_safety, piece_activity, attack_pressure, ply, "
        "d_king_safety, d_piece_activity, d_attack_pressure, phase_num)",
        "2. **Commentary Generation**: テンプレートベース (dry-run) および Gemini API",
        "3. **Quality Evaluation**: ルールベース4軸スコアリング "
        "(context_relevance, naturalness, informativeness, readability)",
        "4. **Style Classification**: ML自動ラベリング → 4スタイル "
        "(technical, encouraging, dramatic, neutral)",
        "",
    ]


def _section_dataset(data: Dict[str, Any]) -> List[str]:
    """Section 2: Dataset statistics."""
    lines: List[str] = ["## 2. Dataset Statistics", ""]
    corpus = data.get("corpus", {})
    phase = data.get("phase_distribution", {})
    commentary = data.get("commentary_stats", {})

    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Sample games | {corpus.get('sample_games', 0)} |")
    lines.append(f"| Pipeline features | {corpus.get('pipeline_features', 0)} |")
    lines.append(
        f"| Training log records | {commentary.get('training_log_records', 0)} |"
    )
    lines.append(
        f"| Batch commentary records | {commentary.get('batch_commentary_records', 0)} |"
    )
    lines.append("| Feature dimensions | 8 |")
    lines.append("")

    phases = phase.get("phases", {})
    total = phase.get("total", 0)
    if phases:
        lines.append("### Phase Distribution")
        lines.append("")
        lines.append("| Phase | Count | Percentage |")
        lines.append("|-------|-------|-----------|")
        for p in ["opening", "midgame", "endgame"]:
            count = phases.get(p, 0)
            pct = f"{count / total * 100:.1f}%" if total else "0.0%"
            lines.append(f"| {p} | {count} | {pct} |")
        lines.append("")
    return lines


def _section_quality(data: Dict[str, Any]) -> List[str]:
    """Section 3: Quality evaluation."""
    lines: List[str] = ["## 3. Quality Evaluation", ""]
    quality = data.get("commentary_stats", {}).get("quality_evaluation", {})
    if not quality or quality.get("total_records", 0) == 0:
        lines.append("*No quality evaluation data available.*")
        lines.append("")
        return lines

    lines.append(f"- Evaluated records: {quality['total_records']}")
    lines.append(f"- Average total score: {quality.get('avg_total', 0)}")
    lines.append(f"- Low quality count (< 40): {quality.get('low_quality_count', 0)}")
    lines.append("")

    avg_scores = quality.get("avg_scores", {})
    if avg_scores:
        lines.append("### Per-Axis Scores")
        lines.append("")
        lines.append("| Axis | Weight | Average |")
        lines.append("|------|--------|---------|")
        weights = {
            "context_relevance": 0.30,
            "naturalness": 0.25,
            "informativeness": 0.25,
            "readability": 0.20,
        }
        for axis in ["context_relevance", "naturalness",
                      "informativeness", "readability"]:
            w = weights.get(axis, 0)
            val = avg_scores.get(axis, 0)
            lines.append(f"| {axis} | {w:.2f} | {val:.1f} |")
        lines.append("")

    by_phase = quality.get("by_phase", {})
    if by_phase:
        lines.append("### Score by Phase")
        lines.append("")
        lines.append("| Phase | Average Score |")
        lines.append("|-------|--------------|")
        for phase_name, val in sorted(by_phase.items()):
            lines.append(f"| {phase_name} | {val:.1f} |")
        lines.append("")
    return lines


def _section_model_comparison(data: Dict[str, Any]) -> List[str]:
    """Section 4: ML model comparison."""
    lines: List[str] = ["## 4. ML Model Comparison", ""]
    exp = data.get("experiment", {})
    if exp.get("error"):
        lines.append(f"*Model training failed: {exp['error']}*")
        lines.append("")
        return lines

    n_samples = exp.get("n_samples", 0)
    n_splits = exp.get("n_splits", 5)
    lines.append(f"- Samples: {n_samples}")
    lines.append(f"- CV folds: {n_splits}")
    lines.append(f"- Best model: **{exp.get('best_model', 'N/A')}**")
    lines.append("")

    models = exp.get("models", [])
    if models:
        lines.append("| Model | Accuracy | F1-macro | Train Time (s) |")
        lines.append("|-------|----------|----------|----------------|")
        for m in models:
            acc = f"{m['accuracy_mean']:.2f} +/- {m['accuracy_std']:.2f}"
            f1 = f"{m['f1_macro_mean']:.2f} +/- {m['f1_macro_std']:.2f}"
            t = f"{m['train_time_seconds']:.2f}"
            bold = m["name"] == exp.get("best_model")
            name = f"**{m['name']}**" if bold else m["name"]
            lines.append(f"| {name} | {acc} | {f1} | {t} |")
        lines.append("")

    dist = exp.get("style_distribution", {})
    if dist:
        lines.append("### Training Data Style Distribution")
        lines.append("")
        lines.append("| Style | Count | Percentage |")
        lines.append("|-------|-------|-----------|")
        total = sum(dist.values()) or 1
        for style in ["technical", "encouraging", "dramatic", "neutral"]:
            count = dist.get(style, 0)
            pct = f"{count / total * 100:.1f}%"
            lines.append(f"| {style} | {count} | {pct} |")
        lines.append("")
    return lines


def _section_feature_importance(data: Dict[str, Any]) -> List[str]:
    """Section 5: Feature importance (consensus ranking)."""
    lines: List[str] = ["## 5. Feature Importance", ""]
    imp = data.get("feature_importance", {})
    if imp.get("error"):
        lines.append(f"*Feature importance analysis failed: {imp['error']}*")
        lines.append("")
        return lines

    ranking = imp.get("consensus_ranking", [])
    if ranking:
        lines.append(
            "### Consensus Ranking (3 methods: tree, permutation, correlation)"
        )
        lines.append("")
        lines.append("| Rank | Feature | Avg Rank |")
        lines.append("|------|---------|----------|")
        for i, item in enumerate(ranking, 1):
            feat = item[0] if isinstance(item, (list, tuple)) else item
            avg_rank = item[1] if isinstance(item, (list, tuple)) else 0
            lines.append(f"| {i} | {feat} | {avg_rank:.2f} |")
        lines.append("")

    for method_key, title in [
        ("tree", "Tree-based (RandomForest)"),
        ("permutation", "Permutation Importance"),
        ("correlation", "Target Correlation (|r|)"),
    ]:
        method_data = imp.get(method_key)
        if method_data:
            lines.append(f"### {title}")
            lines.append("")
            sorted_feats = sorted(method_data.items(), key=lambda x: -x[1])
            for feat, val in sorted_feats:
                lines.append(f"- {feat}: {val:.4f}")
            lines.append("")
    return lines


def _section_style_classification(data: Dict[str, Any]) -> List[str]:
    """Section 6: Style classification analysis."""
    lines: List[str] = ["## 6. Style Classification Analysis", ""]
    dist = data.get("style_distribution", {})
    if dist.get("n_samples", 0) == 0:
        lines.append("*No style distribution data available.*")
        lines.append("")
        return lines

    balance = dist.get("class_balance", {})
    if balance:
        lines.append("### Class Balance")
        lines.append("")
        lines.append("| Style | Percentage |")
        lines.append("|-------|-----------|")
        for style in ["technical", "encouraging", "dramatic", "neutral"]:
            pct = balance.get(style, 0)
            lines.append(f"| {style} | {pct:.1f}% |")
        lines.append("")

    crosstab = dist.get("phase_style_crosstab", {})
    if crosstab:
        styles = ["technical", "encouraging", "dramatic", "neutral"]
        lines.append("### Phase x Style Cross-tabulation")
        lines.append("")
        header = "| Phase |" + "|".join(f" {s} " for s in styles) + "|"
        sep = "|-------|" + "|".join("-------" for _ in styles) + "|"
        lines.append(header)
        lines.append(sep)
        for phase_name in sorted(crosstab.keys()):
            row = f"| {phase_name} |"
            for style in styles:
                row += f" {crosstab[phase_name].get(style, 0)} |"
            lines.append(row)
        lines.append("")

    warnings = dist.get("warnings", [])
    if warnings:
        lines.append("### Warnings")
        lines.append("")
        for w in warnings:
            lines.append(f"> **Warning**: {w}")
        lines.append("")
    return lines


def _section_issues_next_steps(data: Dict[str, Any]) -> List[str]:
    """Section 7: Issues and next steps."""
    lines: List[str] = ["## 7. Issues and Next Steps", ""]

    issues: List[str] = []

    exp = data.get("experiment", {})
    dist = data.get("style_distribution", {})

    if exp.get("error"):
        issues.append(f"Model training error: {exp['error']}")

    for w in dist.get("warnings", []):
        issues.append(w)

    corpus = data.get("corpus", {})
    if corpus.get("pipeline_features", 0) < 100:
        issues.append("Small dataset: fewer than 100 pipeline features")

    commentary = data.get("commentary_stats", {})
    quality = commentary.get("quality_evaluation", {})
    if quality.get("avg_total", 100) < 50:
        issues.append(
            f"Low average quality score: {quality.get('avg_total', 0)}"
        )

    if issues:
        lines.append("### Known Issues")
        lines.append("")
        for issue in issues:
            lines.append(f"- {issue}")
        lines.append("")

    lines.append("### Next Steps")
    lines.append("")
    lines.append("- Gemini API連携による解説品質の向上")
    lines.append("- 訓練データ500件目標への蓄積")
    lines.append("- クラス不均衡への対処 (データ拡張・リサンプリング)")
    lines.append("- ハイパーパラメータチューニングの実施")
    lines.append("- 追加特徴量の検討 (material balance, tempo)")
    lines.append("")
    return lines


# ---------------------------------------------------------------------------
# Main generation
# ---------------------------------------------------------------------------
def generate_report(
    experiment_name: str = "baseline",
    output_path: Optional[str] = None,
) -> str:
    """Generate the full Markdown report. Returns output file path."""
    data = load_latest_experiment(experiment_name)
    if data is None:
        data = {
            "name": experiment_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "corpus": {},
            "phase_distribution": {},
            "commentary_stats": {},
            "experiment": {"error": "No experiment data found"},
            "feature_importance": {"error": "No experiment data found"},
            "style_distribution": {"n_samples": 0},
        }

    sections = [
        _section_overview(data),
        _section_dataset(data),
        _section_quality(data),
        _section_model_comparison(data),
        _section_feature_importance(data),
        _section_style_classification(data),
        _section_issues_next_steps(data),
    ]

    report = "\n".join(line for section in sections for line in section)

    out = Path(output_path) if output_path else _REPORTS_DIR / "baseline_report.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report, encoding="utf-8")
    print(f"Report generated: {out}")
    return str(out)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate research report from experiment results"
    )
    parser.add_argument(
        "--experiment", default="baseline",
        help="Experiment name prefix (default: baseline)",
    )
    parser.add_argument(
        "--output", default=None,
        help="Output path (default: data/reports/baseline_report.md)",
    )
    args = parser.parse_args()
    generate_report(
        experiment_name=args.experiment,
        output_path=args.output,
    )
