#!/usr/bin/env python3
"""Pipeline health audit — data quality and consistency checks.

Usage:
    python scripts/audit_pipeline.py
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Tuple

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

_DATA_DIR = _PROJECT_ROOT / "data"
_ANNOTATED_DIR = _DATA_DIR / "annotated"
_MODELS_DIR = _DATA_DIR / "models"
_EXPERIMENTS_DIR = _DATA_DIR / "experiments"
_SERVICES_DIR = _PROJECT_ROOT / "backend" / "api" / "services"
_TESTS_DIR = _PROJECT_ROOT / "tests"

# Tracking
_issues: List[Dict[str, str]] = []  # {severity, message, action}


def _add_issue(severity: str, message: str, action: str = "") -> None:
    _issues.append({"severity": severity, "message": message, "action": action})


def _ok(msg: str) -> None:
    print(f"  \u2713 {msg}")


def _warn(msg: str) -> None:
    print(f"  \u26a0 {msg}")


def _fail(msg: str) -> None:
    print(f"  \u2717 {msg}")


# ---------------------------------------------------------------------------
# 1. Data file integrity
# ---------------------------------------------------------------------------
def audit_data_quality() -> None:
    print("\n  [Data Quality]")

    from backend.api.schemas.annotation import validate_annotation

    if not _ANNOTATED_DIR.is_dir():
        _fail("data/annotated/ directory not found")
        _add_issue("CRITICAL", "Annotated data directory missing", "Run annotate_corpus.py")
        return

    for jsonl_file in sorted(_ANNOTATED_DIR.glob("*.jsonl")):
        total = 0
        invalid = 0
        dramatic_annotation = 0
        dramatic_target = 0
        missing_features = 0
        errors: List[str] = []

        with open(jsonl_file, encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                total += 1
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    invalid += 1
                    errors.append(f"line {line_num}: invalid JSON")
                    continue

                # Validate annotation
                ok, errs = validate_annotation(obj)
                if not ok:
                    invalid += 1
                    if len(errors) < 3:
                        errors.append(f"line {line_num}: {'; '.join(errs)}")

                # Check for "dramatic" in annotation.style
                ann_style = obj.get("annotation", {}).get("style", "")
                if ann_style == "dramatic":
                    dramatic_annotation += 1

                # Check for "dramatic" in target.style (stale metadata)
                tgt_style = obj.get("target", {}).get("style", "")
                if tgt_style == "dramatic":
                    dramatic_target += 1

                # Check features exist
                if not obj.get("features"):
                    missing_features += 1

        name = jsonl_file.name
        parts = [f"{total} records"]
        if invalid > 0:
            parts.append(f"{invalid} invalid")
            _fail(f"{name}: {', '.join(parts)}")
            for e in errors[:3]:
                print(f"      {e}")
        else:
            parts.append("0 invalid")
            _ok(f"{name}: {', '.join(parts)}")

        if dramatic_annotation > 0:
            _fail(f"  {name}: {dramatic_annotation} records with annotation.style='dramatic'")
            _add_issue(
                "HIGH",
                f"{name}: {dramatic_annotation} records with annotation.style='dramatic'",
                "Remap dramatic -> neutral in annotated data",
            )

        if dramatic_target > 0:
            _warn(f"  {name}: {dramatic_target} records with target.style='dramatic' (stale metadata)")
            _add_issue(
                "MEDIUM",
                f"{name}: {dramatic_target} records with stale target.style='dramatic'",
                "Clean target.style field or re-annotate",
            )

        if missing_features > 0:
            _warn(f"  {name}: {missing_features} records missing features")

    # Duplicate check on merged_corpus
    merged = _ANNOTATED_DIR / "merged_corpus.jsonl"
    if merged.exists():
        seen_texts: Counter = Counter()
        with open(merged, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    text = obj.get("original_text", obj.get("commentary", ""))
                    if text:
                        seen_texts[text] += 1
                except Exception:
                    continue
        dupes = sum(1 for c in seen_texts.values() if c > 1)
        dupe_records = sum(c - 1 for c in seen_texts.values() if c > 1)
        if dupes > 0:
            _warn(f"merged_corpus.jsonl: {dupes} duplicate texts ({dupe_records} extra records)")
            _add_issue("LOW", f"{dupes} duplicate texts in merged_corpus.jsonl", "Review merge dedup logic")
        else:
            _ok(f"merged_corpus.jsonl: 0 duplicates")


# ---------------------------------------------------------------------------
# 2. Label distribution analysis
# ---------------------------------------------------------------------------
def audit_label_distribution() -> None:
    print("\n  [Label Distribution]")

    merged = _ANNOTATED_DIR / "merged_corpus.jsonl"
    if not merged.exists():
        _fail("merged_corpus.jsonl not found")
        return

    focus_counts: Counter = Counter()
    depth_counts: Counter = Counter()
    style_counts: Counter = Counter()
    importance_values: List[float] = []
    phase_counts: Counter = Counter()
    phase_focus: Dict[str, Counter] = {}
    total = 0

    with open(merged, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                ann = obj.get("annotation", {})
                features = obj.get("features", {})
                total += 1

                for lbl in ann.get("focus", []):
                    focus_counts[lbl] += 1
                depth_counts[ann.get("depth", "unknown")] += 1
                style_counts[ann.get("style", "unknown")] += 1
                imp = ann.get("importance")
                if imp is not None:
                    importance_values.append(float(imp))

                phase = features.get("phase", "unknown")
                phase_counts[phase] += 1
                if phase not in phase_focus:
                    phase_focus[phase] = Counter()
                for lbl in ann.get("focus", []):
                    phase_focus[phase][lbl] += 1
            except Exception:
                continue

    if total == 0:
        _fail("No records in merged_corpus.jsonl")
        return

    print(f"\n    Total records: {total}")

    # Focus distribution
    print(f"\n    Focus labels:")
    for lbl, count in focus_counts.most_common():
        pct = count / total * 100
        flag = ""
        if pct > 90:
            flag = " <-- SEVERELY OVERREPRESENTED"
            _add_issue("MEDIUM", f"Focus '{lbl}' at {pct:.1f}% — overrepresented", "Diversify training data")
        elif pct < 5:
            flag = " <-- SEVERELY UNDERREPRESENTED"
            _add_issue("MEDIUM", f"Focus '{lbl}' at {pct:.1f}% — underrepresented", "Collect more examples")
        _warn(f"  {lbl:25s} {count:>4} ({pct:.1f}%){flag}") if flag else print(f"      {lbl:25s} {count:>4} ({pct:.1f}%)")

    # Depth distribution
    print(f"\n    Depth levels:")
    for depth, count in depth_counts.most_common():
        pct = count / total * 100
        flag = ""
        if pct < 5:
            flag = " <-- SEVERELY UNDERREPRESENTED"
            _add_issue("HIGH", f"Depth '{depth}' at {pct:.1f}% — severely underrepresented", "Generate more surface-depth examples")
        elif pct > 90:
            flag = " <-- SEVERELY OVERREPRESENTED"
        _warn(f"  {depth:25s} {count:>4} ({pct:.1f}%){flag}") if flag else print(f"      {depth:25s} {count:>4} ({pct:.1f}%)")

    # Style distribution
    print(f"\n    Style distribution:")
    for style, count in style_counts.most_common():
        pct = count / total * 100
        flag = ""
        if pct > 70:
            flag = " <-- IMBALANCED"
            _add_issue("MEDIUM", f"Style '{style}' at {pct:.1f}% — class imbalance", "Balance style targets in collection_config")
        elif pct < 10:
            flag = " <-- LOW"
        _warn(f"  {style:25s} {count:>4} ({pct:.1f}%){flag}") if flag else print(f"      {style:25s} {count:>4} ({pct:.1f}%)")

    # Importance stats
    if importance_values:
        import statistics
        mean_imp = statistics.mean(importance_values)
        std_imp = statistics.stdev(importance_values) if len(importance_values) > 1 else 0
        print(f"\n    Importance: mean={mean_imp:.3f}, std={std_imp:.3f}, "
              f"min={min(importance_values):.2f}, max={max(importance_values):.2f}")

    # Phase x Focus cross-tabulation
    print(f"\n    Phase x Focus cross-tabulation:")
    from backend.api.schemas.annotation import FOCUS_LABELS
    header = f"      {'Phase':12s}" + "".join(f" {lbl[:8]:>8s}" for lbl in FOCUS_LABELS)
    print(header)
    for phase in ["opening", "midgame", "endgame"]:
        if phase not in phase_focus:
            continue
        row = f"      {phase:12s}"
        for lbl in FOCUS_LABELS:
            count = phase_focus[phase].get(lbl, 0)
            row += f" {count:>8d}"
        print(row)


# ---------------------------------------------------------------------------
# 3. Circular learning check
# ---------------------------------------------------------------------------
def audit_circular_learning() -> None:
    print("\n  [Circular Learning Check]")

    from backend.api.services.importance_predictor import _rule_based_importance

    merged = _ANNOTATED_DIR / "merged_corpus.jsonl"
    if not merged.exists():
        _warn("merged_corpus.jsonl not found — skipping")
        return

    rule_based: List[float] = []
    annotated: List[float] = []

    with open(merged, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                features = obj.get("features", {})
                ann = obj.get("annotation", {})
                imp = ann.get("importance")
                if imp is None or not features:
                    continue
                rule_val = _rule_based_importance(features)
                rule_based.append(rule_val)
                annotated.append(float(imp))
            except Exception:
                continue

    if len(rule_based) < 10:
        _warn("Too few records for circular learning analysis")
        return

    # Calculate correlation
    import numpy as np
    rb = np.array(rule_based)
    an = np.array(annotated)

    if np.std(rb) > 0 and np.std(an) > 0:
        corr = float(np.corrcoef(rb, an)[0, 1])
    else:
        corr = 0.0

    exact_match = sum(1 for a, b in zip(rule_based, annotated) if abs(a - b) < 0.001)
    exact_pct = exact_match / len(rule_based) * 100

    if corr > 0.99:
        _fail(f"Correlation between rule-based importance and annotations: r={corr:.4f}")
        _fail(f"Exact match: {exact_match}/{len(rule_based)} ({exact_pct:.1f}%)")
        _warn("ImportancePredictor R^2=0.992 is circular learning:")
        _warn("  annotation_service._estimate_importance == _rule_based_importance")
        _warn("  Model is learning the rule function, not real patterns")
        _warn("  → Need human/expert importance labels for genuine learning")
        _add_issue(
            "HIGH",
            "ImportancePredictor has circular learning (r={:.4f})".format(corr),
            "Collect human importance labels to break circularity",
        )
    elif corr > 0.9:
        _warn(f"High correlation (r={corr:.4f}) between rule-based and annotated importance")
    else:
        _ok(f"Importance annotations show independent signal (r={corr:.4f})")


# ---------------------------------------------------------------------------
# 4. Model status
# ---------------------------------------------------------------------------
def audit_model_status() -> None:
    print("\n  [Model Status]")

    models = [
        ("focus_predictor.joblib", "FocusPredictor"),
        ("importance_predictor.joblib", "ImportancePredictor"),
        ("style_selector.joblib", "StyleSelector"),
    ]

    for filename, name in models:
        path = _MODELS_DIR / filename
        if path.exists():
            # Try loading
            try:
                from backend.api.services.focus_predictor import FocusPredictor
                from backend.api.services.importance_predictor import ImportancePredictor
                from backend.api.services.ml_trainer import CommentaryStyleSelector

                if name == "FocusPredictor":
                    m = FocusPredictor()
                    ok = m.load(str(path))
                elif name == "ImportancePredictor":
                    m = ImportancePredictor()
                    ok = m.load(str(path))
                elif name == "StyleSelector":
                    m = CommentaryStyleSelector()
                    ok = m.load(str(path))
                else:
                    ok = False

                if ok:
                    _ok(f"{filename}: exists, loadable")
                else:
                    _fail(f"{filename}: exists but FAILED to load")
                    _add_issue("HIGH", f"{filename} failed to load", "Retrain model")
            except Exception as e:
                _fail(f"{filename}: load error: {e}")
        else:
            _fail(f"{filename}: MISSING")
            _add_issue(
                "CRITICAL" if name == "StyleSelector" else "HIGH",
                f"{filename} missing",
                f"Run train_models.py / train_style_model.py",
            )


# ---------------------------------------------------------------------------
# 5. Experiment data integrity
# ---------------------------------------------------------------------------
def audit_experiment_data() -> None:
    print("\n  [Experiment Data]")

    if not _EXPERIMENTS_DIR.is_dir():
        _fail("data/experiments/ directory not found")
        return

    exp_files = sorted([
        f for f in _EXPERIMENTS_DIR.iterdir()
        if f.suffix == ".json" and not f.name.startswith("analysis")
    ])

    if not exp_files:
        _fail("No experiment files found")
        return

    _ok(f"{len(exp_files)} experiment files found")

    latest = exp_files[-1]
    try:
        with open(latest, encoding="utf-8") as f:
            data = json.load(f)

        name = data.get("name", latest.stem)
        # n_samples can be at top level or nested in experiment
        n_samples = data.get("n_samples", 0)
        if n_samples == 0:
            exp_sub = data.get("experiment", {})
            n_samples_nested = exp_sub.get("n_samples", 0)
            if n_samples_nested > 0:
                _warn(f"Latest: {latest.name} — n_samples at top level = 0, "
                      f"but experiment.n_samples = {n_samples_nested}")
                _warn("pipeline_status.py reads exp.get('n_samples', 0) — shows 0")
                _warn("Root cause: baseline_full_*.json nests n_samples under 'experiment' key")
                _add_issue(
                    "MEDIUM",
                    "pipeline_status.py shows 'Samples: 0' for baseline_full experiments",
                    "Fix pipeline_status.py to check experiment.n_samples fallback",
                )
            else:
                _fail(f"Latest: {latest.name} — n_samples = 0 (no training data)")
        else:
            _ok(f"Latest: {latest.name} — n_samples = {n_samples}")

    except Exception as e:
        _fail(f"Error loading {latest.name}: {e}")


# ---------------------------------------------------------------------------
# 6. Test coverage
# ---------------------------------------------------------------------------
def audit_test_coverage() -> None:
    print("\n  [Test Coverage]")

    services = {}
    for f in sorted(_SERVICES_DIR.glob("*.py")):
        if f.name == "__init__.py":
            continue
        line_count = sum(1 for _ in open(f, encoding="utf-8"))
        services[f.stem] = line_count

    tests = {}
    test_counts = {}
    for f in sorted(_TESTS_DIR.glob("test_*.py")):
        line_count = sum(1 for _ in open(f, encoding="utf-8"))
        tests[f.stem] = line_count
        # Count test methods
        n_tests = sum(1 for line in open(f, encoding="utf-8") if line.strip().startswith("def test_"))
        test_counts[f.stem] = n_tests

    # Direct match
    covered = []
    uncovered = []
    for svc, lines in sorted(services.items()):
        test_name = f"test_{svc}"
        if test_name in tests:
            covered.append((svc, lines, test_name, tests[test_name], test_counts.get(test_name, 0)))
        else:
            uncovered.append((svc, lines))

    # Check indirect coverage (service imported in other test files)
    indirect: Dict[str, List[str]] = {}
    for test_file in sorted(_TESTS_DIR.glob("test_*.py")):
        content = test_file.read_text(encoding="utf-8")
        for svc in [s for s, _ in uncovered]:
            if svc in content:
                if svc not in indirect:
                    indirect[svc] = []
                indirect[svc].append(test_file.stem)

    for svc, svc_lines, test, test_lines, n_tests in covered:
        ratio = test_lines / svc_lines if svc_lines > 0 else 0
        _ok(f"{svc}.py ({svc_lines}L) -> {test}.py ({test_lines}L, {n_tests} tests, ratio={ratio:.1f}x)")

    for svc, svc_lines in uncovered:
        if svc in indirect:
            test_files = ", ".join(indirect[svc])
            print(f"    ~ {svc}.py ({svc_lines}L) -> indirect: {test_files}")
        else:
            _fail(f"{svc}.py ({svc_lines}L) -> NO TEST FILE")
            if svc_lines > 50:
                _add_issue("LOW", f"No tests for {svc}.py ({svc_lines} lines)", f"Add tests/test_{svc}.py")

    print(f"\n    Total: {len(covered)} direct, {len(indirect)} indirect, "
          f"{len(uncovered) - len(indirect)} uncovered")


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
def print_summary() -> None:
    print("\n  " + "=" * 54)
    print("  Recommended Actions")
    print("  " + "=" * 54)

    by_severity = {"CRITICAL": [], "HIGH": [], "MEDIUM": [], "LOW": []}
    for issue in _issues:
        sev = issue["severity"]
        by_severity.setdefault(sev, []).append(issue)

    for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        items = by_severity.get(sev, [])
        if not items:
            continue
        print(f"\n  {sev}:")
        for item in items:
            print(f"    - {item['message']}")
            if item["action"]:
                print(f"      -> {item['action']}")

    if not _issues:
        print("\n  No issues found. Pipeline is healthy.")

    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    print()
    print("  " + "=" * 54)
    print("  Pipeline Health Audit")
    print("  " + "=" * 54)

    audit_data_quality()
    audit_label_distribution()
    audit_circular_learning()
    audit_model_status()
    audit_experiment_data()
    audit_test_coverage()
    print_summary()


if __name__ == "__main__":
    main()
