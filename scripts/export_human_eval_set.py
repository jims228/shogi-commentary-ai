"""scripts/export_human_eval_set.py

validated real_positions JSON または comparison JSON から
人手評価用のデータセットを書き出す.

全レコードは出力前に validate_eval_positions で整合性検証を行い、
不正な局面は除外する.

使い方:
  # validated real_positions から出力 (推奨)
  python scripts/export_human_eval_set.py -i data/real_positions_validated.json

  # comparison json から出力 (レガシー)
  python scripts/export_human_eval_set.py -i data/experiments/legacy_vs_planner_*.json

  # 上限数を指定
  python scripts/export_human_eval_set.py -i data/real_positions_validated.json --max 15

出力: data/human_eval/eval_set_<timestamp>.json
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.validate_eval_positions import validate_record


def _load_input(path: str) -> List[Dict[str, Any]]:
    """入力JSONからレコード一覧を取得."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    # comparison json: {"positions": [...]}
    if isinstance(data, dict) and "positions" in data:
        return data["positions"]
    # eval_set json: {"records": [...]}
    if isinstance(data, dict) and "records" in data:
        return data["records"]
    # real_positions / benchmark json: [...]
    if isinstance(data, list):
        return data
    return []


def build_eval_records(positions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """局面リストを人手評価用レコードに変換."""
    records: List[Dict[str, Any]] = []
    for i, pos in enumerate(positions):
        plan = pos.get("planner_plan") or {}
        record = {
            "id": f"eval_{i+1:03d}",
            # 局面情報 (そのまま保持)
            "sfen": pos.get("sfen", ""),
            "ply": pos.get("ply", 0),
            "user_move": pos.get("user_move"),
            "name": pos.get("name", ""),
            "candidates": pos.get("candidates", []),
            "prev_moves": pos.get("prev_moves", []),
            # 解説テキスト
            "legacy_explanation": pos.get("legacy_explanation", ""),
            "planner_explanation": pos.get("planner_explanation", ""),
            # プラン構造
            "planner_plan_flow": plan.get("flow", ""),
            "planner_plan_topic_keyword": plan.get("topic_keyword", ""),
            "planner_plan_surface_reason": plan.get("surface_reason", ""),
            "planner_plan_deep_reason": plan.get("deep_reason", ""),
            # 自動評価 (参考値)
            "auto_legacy_score": pos.get("legacy_eval", {}).get("total")
                if isinstance(pos.get("legacy_eval"), dict) else None,
            "auto_planner_score": pos.get("planner_eval", {}).get("total")
                if isinstance(pos.get("planner_eval"), dict) else None,
            "is_fallback": pos.get("is_fallback", False),
            # 人手評価フィールド (記入用)
            "flow_score": None,
            "keyword_score": None,
            "depth_score": None,
            "readability_score": None,
            "preference": None,
            "notes": "",
        }
        records.append(record)
    return records


def validate_and_filter(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """整合性チェックに通らないレコードを除外."""
    valid = []
    for rec in records:
        vr = validate_record(rec)
        if vr.valid:
            valid.append(rec)
        else:
            print(f"  [filter] DROPPED {rec.get('id', '?')}: {'; '.join(vr.errors)}")
    return valid


def export_json(records: List[Dict[str, Any]], out_path: Path) -> None:
    payload = {
        "version": "1.1",
        "created": datetime.now(timezone.utc).isoformat(),
        "total": len(records),
        "scoring_guide": {
            "flow_score": "1=不自然 2=やや不自然 3=普通 4=自然 5=非常に自然",
            "keyword_score": "1=不適切 2=やや不適切 3=普通 4=適切 5=非常に適切",
            "depth_score": "1=浅い/無関係 2=やや浅い 3=普通 4=深い 5=非常に深い・洞察的",
            "readability_score": "1=読みにくい 2=やや読みにくい 3=普通 4=読みやすい 5=非常に読みやすい",
            "preference": "legacy=旧方式が良い / planner=プランナーが良い / tie=同等",
        },
        "records": records,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def export_csv(records: List[Dict[str, Any]], out_path: Path) -> None:
    if not records:
        return
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(records[0].keys())
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for rec in records:
            row = {}
            for k, v in rec.items():
                row[k] = json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v
            writer.writerow(row)


def main():
    parser = argparse.ArgumentParser(description="Export human evaluation dataset")
    parser.add_argument("--input", "-i", required=True, nargs="+",
                        help="入力ファイル (real_positions / comparison json). glob可")
    parser.add_argument("--format", "-f", default="json", choices=["json", "csv", "both"],
                        help="出力形式 (default: json)")
    parser.add_argument("--output", "-o", default=None,
                        help="出力パス (省略時: data/human_eval/eval_set_<timestamp>)")
    parser.add_argument("--max", "-m", type=int, default=None,
                        help="最大レコード数")
    args = parser.parse_args()

    # glob展開
    input_files: List[str] = []
    for pattern in args.input:
        expanded = glob.glob(pattern)
        if expanded:
            input_files.extend(sorted(expanded))
        else:
            input_files.append(pattern)

    # 全ファイルから局面を集約
    all_positions: List[Dict[str, Any]] = []
    for fpath in input_files:
        positions = _load_input(fpath)
        all_positions.extend(positions)
        print(f"[export] {len(positions)} positions from {fpath}")

    if not all_positions:
        print("[export] ERROR: No positions found")
        return

    if args.max:
        all_positions = all_positions[:args.max]

    records = build_eval_records(all_positions)
    print(f"[export] {len(records)} eval records created")

    # Validation gate
    print("[export] Running validation...")
    valid_records = validate_and_filter(records)
    print(f"[export] {len(valid_records)}/{len(records)} passed validation")

    if not valid_records:
        print("[export] ERROR: No valid records after validation")
        return

    # Re-number IDs after filtering
    for i, rec in enumerate(valid_records):
        rec["id"] = f"eval_{i+1:03d}"

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_dir = _PROJECT_ROOT / "data" / "human_eval"

    if args.output:
        base = Path(args.output)
    else:
        base = out_dir / f"eval_set_{ts}"

    if args.format in ("json", "both"):
        json_path = base.with_suffix(".json")
        export_json(valid_records, json_path)
        print(f"[export] JSON: {json_path}")

    if args.format in ("csv", "both"):
        csv_path = base.with_suffix(".csv")
        export_csv(valid_records, csv_path)
        print(f"[export] CSV: {csv_path}")


if __name__ == "__main__":
    main()
