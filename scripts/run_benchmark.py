#!/usr/bin/env python3
"""ベンチマーク局面に対して特徴量抽出+品質評価を実行し、
期待値との乖離をレポートする。Gemini APIは使わない。

Usage:
    python scripts/run_benchmark.py
    python scripts/run_benchmark.py --json   # JSON出力
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

# プロジェクトルートをパスに追加
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from backend.api.services.position_features import extract_position_features

_BENCHMARK_PATH = _PROJECT_ROOT / "data" / "benchmark_positions.json"

# テーブル描画の列幅
_COL_WIDTHS = {
    "position": 20,
    "phase": 12,
    "k_safety": 14,
    "activity": 14,
    "pressure": 14,
}


def _load_benchmark() -> List[Dict[str, Any]]:
    with open(_BENCHMARK_PATH, encoding="utf-8") as f:
        return json.load(f)


def _check_expectation(
    value: Any,
    expected: Dict[str, Any],
    key_prefix: str,
) -> tuple[str, bool]:
    """値と期待値を比較し、表示文字列と合否を返す."""
    vmin = expected.get(f"{key_prefix}_min")
    vmax = expected.get(f"{key_prefix}_max")

    if vmin is not None and vmax is not None:
        ok = vmin <= value <= vmax
        label = f"{value} ({vmin}-{vmax})"
    elif vmin is not None:
        ok = value >= vmin
        label = f"{value} (>={vmin})"
    elif vmax is not None:
        ok = value <= vmax
        label = f"{value} (<={vmax})"
    else:
        ok = True
        label = str(value)

    mark = "\u2713" if ok else "\u2717"
    return f"{mark}{label}", ok


def run_benchmark(json_output: bool = False) -> Dict[str, Any]:
    """ベンチマークを実行して結果を返す."""
    positions = _load_benchmark()
    results: List[Dict[str, Any]] = []
    warnings: List[str] = []
    all_pass = True

    for pos in positions:
        name = pos["name"]
        sfen = pos["sfen"]
        ply = pos.get("ply", 0)
        expected = pos.get("expected", {})

        features = extract_position_features(sfen, ply=ply)

        # phase チェック
        expected_phase = expected.get("phase")
        phase_ok = expected_phase is None or features["phase"] == expected_phase

        # 数値チェック
        ks_label, ks_ok = _check_expectation(
            features["king_safety"], expected, "king_safety"
        )
        pa_label, pa_ok = _check_expectation(
            features["piece_activity"], expected, "piece_activity"
        )
        ap_label, ap_ok = _check_expectation(
            features["attack_pressure"], expected, "attack_pressure"
        )

        row_pass = phase_ok and ks_ok and pa_ok and ap_ok
        if not row_pass:
            all_pass = False

        result = {
            "name": name,
            "phase": features["phase"],
            "phase_expected": expected_phase,
            "phase_ok": phase_ok,
            "king_safety": features["king_safety"],
            "king_safety_label": ks_label,
            "king_safety_ok": ks_ok,
            "piece_activity": features["piece_activity"],
            "piece_activity_label": pa_label,
            "piece_activity_ok": pa_ok,
            "attack_pressure": features["attack_pressure"],
            "attack_pressure_label": ap_label,
            "attack_pressure_ok": ap_ok,
            "pass": row_pass,
        }
        results.append(result)

        if not row_pass:
            fails = []
            if not phase_ok:
                fails.append(
                    f"phase: got {features['phase']}, expected {expected_phase}"
                )
            if not ks_ok:
                fails.append(f"king_safety: {ks_label}")
            if not pa_ok:
                fails.append(f"piece_activity: {pa_label}")
            if not ap_ok:
                fails.append(f"attack_pressure: {ap_label}")
            warnings.append(f"  {name}: {'; '.join(fails)}")

    summary = {
        "total": len(results),
        "passed": sum(1 for r in results if r["pass"]),
        "failed": sum(1 for r in results if not r["pass"]),
        "all_pass": all_pass,
        "results": results,
        "warnings": warnings,
    }

    if json_output:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        _print_table(results, warnings, summary)

    return summary


def _print_table(
    results: List[Dict[str, Any]],
    warnings: List[str],
    summary: Dict[str, Any],
) -> None:
    """結果をテーブル形式で表示."""
    w = _COL_WIDTHS
    header = (
        f"{'Position':<{w['position']}}"
        f"{'Phase':<{w['phase']}}"
        f"{'K.Safety':<{w['k_safety']}}"
        f"{'Activity':<{w['activity']}}"
        f"{'Pressure':<{w['pressure']}}"
    )
    sep = "-" * len(header)

    print()
    print("=== Benchmark Results ===")
    print(sep)
    print(header)
    print(sep)

    for r in results:
        phase_mark = "\u2713" if r["phase_ok"] else "\u2717"
        phase_str = f"{phase_mark}{r['phase']}"
        status = " \u2713" if r["pass"] else " \u2717"

        print(
            f"{r['name']:<{w['position']}}"
            f"{phase_str:<{w['phase']}}"
            f"{r['king_safety_label']:<{w['k_safety']}}"
            f"{r['piece_activity_label']:<{w['activity']}}"
            f"{r['attack_pressure_label']:<{w['pressure']}}"
            f"{status}"
        )

    print(sep)
    print(
        f"Total: {summary['total']}  "
        f"Passed: {summary['passed']}  "
        f"Failed: {summary['failed']}"
    )

    if warnings:
        print()
        print("Warnings:")
        for w in warnings:
            print(w)

    print()


if __name__ == "__main__":
    json_mode = "--json" in sys.argv
    result = run_benchmark(json_output=json_mode)
    sys.exit(0 if result["all_pass"] else 1)
