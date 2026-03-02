"""特徴量重要度分析・スタイル分布分析.

Tree-based / Permutation / Correlation の3手法で特徴量重要度を分析し、
スタイルラベルの分布パターンとクラス不均衡を検出する。
"""
from __future__ import annotations

import logging
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

_LOG = logging.getLogger("uvicorn.error")

try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.inspection import permutation_importance
    _HAS_SKLEARN = True
except ImportError:
    _HAS_SKLEARN = False

from backend.api.services.ml_trainer import (
    STYLES, _FEATURE_KEYS, load_training_data,
)


def analyze_feature_importance(
    data_path: Optional[str] = None,
    method: str = "all",
) -> Dict[str, Any]:
    """特徴量重要度を複数手法で分析.

    Parameters
    ----------
    data_path : str, optional
        Training log directory.
    method : str
        "tree", "permutation", "correlation", or "all"

    Returns
    -------
    dict
        tree, permutation, correlation results + consensus_ranking
    """
    if not _HAS_SKLEARN and method in ("tree", "permutation", "all"):
        return {"error": "scikit-learn not installed"}

    data = load_training_data(log_dir=data_path)
    if data.get("error"):
        return {"error": data["error"], "n_samples": data["n_samples"]}

    X = np.array(data["X"])
    y = np.array(data["y"])

    result: Dict[str, Any] = {
        "tree": None,
        "permutation": None,
        "correlation": None,
        "feature_correlation_matrix": None,
        "consensus_ranking": [],
        "n_samples": len(X),
    }

    # Shared fitted model for tree and permutation
    rf_model = None
    if method in ("tree", "permutation", "all") and _HAS_SKLEARN:
        rf_model = RandomForestClassifier(
            n_estimators=100, random_state=42, max_depth=8
        )
        rf_model.fit(X, y)

    # --- Tree-based importance ---
    if method in ("tree", "all") and rf_model is not None:
        imp = rf_model.feature_importances_
        result["tree"] = {
            _FEATURE_KEYS[i]: round(float(imp[i]), 4)
            for i in range(len(_FEATURE_KEYS))
        }

    # --- Permutation importance ---
    if method in ("permutation", "all") and rf_model is not None:
        perm = permutation_importance(
            rf_model, X, y, n_repeats=10, random_state=42
        )
        result["permutation"] = {
            _FEATURE_KEYS[i]: round(float(perm.importances_mean[i]), 4)
            for i in range(len(_FEATURE_KEYS))
        }

    # --- Correlation-based importance ---
    if method in ("correlation", "all"):
        # Build (n_samples, n_features+1) matrix with target as last column
        Xy = np.column_stack([X, y.astype(float)])
        corr_full = np.corrcoef(Xy, rowvar=False)

        # Feature correlation matrix (8x8)
        feat_corr = corr_full[:len(_FEATURE_KEYS), :len(_FEATURE_KEYS)]
        result["feature_correlation_matrix"] = [
            [round(float(v), 4) for v in row] for row in feat_corr
        ]

        # Target correlation (absolute values)
        target_corr = corr_full[:len(_FEATURE_KEYS), -1]
        result["correlation"] = {
            _FEATURE_KEYS[i]: round(float(abs(target_corr[i])), 4)
            for i in range(len(_FEATURE_KEYS))
        }

    # --- Consensus ranking ---
    rankings: Dict[str, List[int]] = {k: [] for k in _FEATURE_KEYS}
    for method_key in ("tree", "permutation", "correlation"):
        imp_dict = result.get(method_key)
        if imp_dict is None:
            continue
        sorted_feats = sorted(
            imp_dict.items(), key=lambda x: -x[1]
        )
        for rank, (feat, _) in enumerate(sorted_feats, 1):
            rankings[feat].append(rank)

    if any(rankings[k] for k in rankings):
        avg_ranks: List[Tuple[str, float]] = []
        for feat, ranks in rankings.items():
            if ranks:
                avg_ranks.append((feat, round(sum(ranks) / len(ranks), 2)))
        avg_ranks.sort(key=lambda x: x[1])
        result["consensus_ranking"] = avg_ranks

    return result


def analyze_style_distribution(
    data_path: Optional[str] = None,
) -> Dict[str, Any]:
    """スタイル分布の詳細分析.

    Returns
    -------
    dict
        phase_style_crosstab, per_style_feature_means,
        class_balance, warnings, n_samples
    """
    data = load_training_data(log_dir=data_path)
    if data.get("error") and data["n_samples"] == 0:
        return {
            "phase_style_crosstab": {},
            "per_style_feature_means": {},
            "class_balance": {},
            "warnings": [data["error"]],
            "n_samples": 0,
        }

    X = data["X"]
    labels = data["labels"]
    features_raw = data["features_raw"]
    n = len(X)

    # Phase × style cross-tabulation
    crosstab: Dict[str, Dict[str, int]] = defaultdict(lambda: {s: 0 for s in STYLES})
    for i in range(n):
        phase = features_raw[i].get("phase", "unknown")
        style = labels[i]
        crosstab[phase][style] += 1

    # Per-style feature means
    style_vectors: Dict[str, List[List[float]]] = defaultdict(list)
    for i in range(n):
        style_vectors[labels[i]].append(X[i])

    per_style_means: Dict[str, Dict[str, float]] = {}
    for style in STYLES:
        if style_vectors[style]:
            arr = np.array(style_vectors[style])
            means = arr.mean(axis=0)
            per_style_means[style] = {
                _FEATURE_KEYS[j]: round(float(means[j]), 2)
                for j in range(len(_FEATURE_KEYS))
            }
        else:
            per_style_means[style] = {k: 0.0 for k in _FEATURE_KEYS}

    # Class balance
    class_balance: Dict[str, float] = {}
    warnings: List[str] = []
    dist = data["distribution"]
    for style in STYLES:
        pct = round(dist.get(style, 0) / max(1, n) * 100, 1)
        class_balance[style] = pct
        if pct < 10.0 and n >= 10:
            warnings.append(
                f"Class imbalance: '{style}' has only {pct}% of samples "
                f"({dist.get(style, 0)}/{n})"
            )

    return {
        "phase_style_crosstab": dict(crosstab),
        "per_style_feature_means": per_style_means,
        "class_balance": class_balance,
        "warnings": warnings,
        "n_samples": n,
    }


def generate_analysis_report(
    importance: Dict[str, Any],
    distribution: Dict[str, Any],
) -> str:
    """分析結果をMarkdown形式のレポートとして出力."""
    lines: List[str] = []
    lines.append("# Feature Importance Analysis")
    lines.append("")
    lines.append(f"Samples: {importance.get('n_samples', 0)}")
    lines.append("")

    # Consensus ranking
    ranking = importance.get("consensus_ranking", [])
    if ranking:
        lines.append("## Consensus Ranking")
        lines.append("")
        lines.append("| Rank | Feature | Avg Rank |")
        lines.append("|------|---------|----------|")
        for i, (feat, avg_rank) in enumerate(ranking, 1):
            lines.append(f"| {i} | {feat} | {avg_rank:.2f} |")
        lines.append("")

    # Per-method details
    for method_key in ("tree", "permutation", "correlation"):
        imp = importance.get(method_key)
        if imp is None:
            continue
        title = {
            "tree": "Tree-based (RandomForest)",
            "permutation": "Permutation Importance",
            "correlation": "Target Correlation (|r|)",
        }[method_key]
        lines.append(f"## {title}")
        lines.append("")
        sorted_imp = sorted(imp.items(), key=lambda x: -x[1])
        for feat, val in sorted_imp:
            lines.append(f"- {feat}: {val:.4f}")
        lines.append("")

    # Style distribution
    lines.append("# Style Distribution")
    lines.append("")

    balance = distribution.get("class_balance", {})
    if balance:
        lines.append("## Class Balance")
        lines.append("")
        lines.append("| Style | Percentage |")
        lines.append("|-------|-----------|")
        for style in STYLES:
            pct = balance.get(style, 0)
            lines.append(f"| {style} | {pct:.1f}% |")
        lines.append("")

    warnings = distribution.get("warnings", [])
    if warnings:
        for w in warnings:
            lines.append(f"> **Warning**: {w}")
        lines.append("")

    # Cross-tabulation
    crosstab = distribution.get("phase_style_crosstab", {})
    if crosstab:
        lines.append("## Phase x Style Cross-tabulation")
        lines.append("")
        header = "| Phase |" + "|".join(f" {s} " for s in STYLES) + "|"
        sep = "|-------|" + "|".join("-------" for _ in STYLES) + "|"
        lines.append(header)
        lines.append(sep)
        for phase in sorted(crosstab.keys()):
            row = f"| {phase} |"
            for style in STYLES:
                row += f" {crosstab[phase].get(style, 0)} |"
            lines.append(row)
        lines.append("")

    # Per-style feature means
    means = distribution.get("per_style_feature_means", {})
    if means:
        lines.append("## Per-Style Feature Means")
        lines.append("")
        header = "| Feature |" + "|".join(f" {s} " for s in STYLES) + "|"
        sep = "|---------|" + "|".join("-------" for _ in STYLES) + "|"
        lines.append(header)
        lines.append(sep)
        for feat in _FEATURE_KEYS:
            row = f"| {feat} |"
            for style in STYLES:
                val = means.get(style, {}).get(feat, 0)
                row += f" {val:.1f} |"
            lines.append(row)
        lines.append("")

    return "\n".join(lines)
