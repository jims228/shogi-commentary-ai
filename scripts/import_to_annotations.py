#!/usr/bin/env python3
"""sync結果を annotate_game.py のテンプレート形式に変換するスクリプト.

sync_commentary.py の出力をベースに、アノテーションテンプレート構造を生成し、
synced_comments から human_annotation を自動的に埋める。

Usage:
    python3 scripts/import_to_annotations.py \
      data/synced/game01_synced.json \
      --kifu data/parsed/game01_moves.json \
      --output data/annotations/game01_auto.json \
      --with-engine
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from backend.api.services.position_features import extract_position_features

# エンジンの利用可否を判定
_ENGINE_AVAILABLE = True
try:
    from backend.api.services.engine_analysis import EngineAnalysisService
except ImportError:
    _ENGINE_AVAILABLE = False

# ---------------------------------------------------------------------------
# Focus 推定マッピング
# ---------------------------------------------------------------------------
_TYPE_TO_FOCUS = {
    "move_evaluation": "piece_activity",
    "position_analysis": "positional",
    "tactical": "attack_pressure",
    "strategic": "positional",
    "opening_theory": "positional",
    "general": "piece_activity",
}

_DEPTH_KEYWORDS = {
    "deep": ["読み筋", "変化", "分岐", "検討", "研究", "難解"],
    "strategic": ["狙い", "方針", "構想", "理由", "意味", "目的"],
}


def _estimate_focus(comments: List[Dict[str, Any]]) -> Dict[str, Any]:
    """コメントタイプからフォーカスを推定."""
    type_counts: Dict[str, int] = defaultdict(int)
    for c in comments:
        ctype = c.get("commentary_type", "general")
        type_counts[ctype] += 1

    if not type_counts:
        return {"primary": "", "secondary": [], "ignored": []}

    sorted_types = sorted(type_counts.items(), key=lambda x: -x[1])
    primary_type = sorted_types[0][0]
    primary_focus = _TYPE_TO_FOCUS.get(primary_type, "piece_activity")

    secondary = []
    for ctype, _ in sorted_types[1:]:
        focus = _TYPE_TO_FOCUS.get(ctype, "")
        if focus and focus != primary_focus and focus not in secondary:
            secondary.append(focus)

    return {
        "primary": primary_focus,
        "secondary": secondary,
        "ignored": [],
    }


def _estimate_depth(comments: List[Dict[str, Any]]) -> str:
    """コメントテキストから解説の深さを推定."""
    all_text = " ".join(c.get("text", "") for c in comments)

    for kw in _DEPTH_KEYWORDS["deep"]:
        if kw in all_text:
            return "deep"
    for kw in _DEPTH_KEYWORDS["strategic"]:
        if kw in all_text:
            return "strategic"

    total_len = sum(len(c.get("text", "")) for c in comments)
    if total_len > 100:
        return "strategic"
    return "surface"


def _estimate_style(comments: List[Dict[str, Any]]) -> str:
    """コメントテキストからスタイルを推定."""
    all_text = " ".join(c.get("text", "") for c in comments)
    if any(kw in all_text for kw in ["厳しい", "正確", "精密", "読み切り"]):
        return "technical"
    if any(kw in all_text for kw in ["面白い", "楽しい", "素晴らしい"]):
        return "encouraging"
    return "neutral"


def import_to_annotation(
    synced: Dict[str, Any],
    parsed_kifu: Optional[Dict[str, Any]] = None,
    engine_svc: Any = None,
) -> Dict[str, Any]:
    """sync結果をアノテーションテンプレートに変換.

    Parameters
    ----------
    synced : dict
        sync_commentary.py の出力
    parsed_kifu : dict | None
        棋譜パース結果 (kif_parser.py の出力)
    engine_svc : EngineAnalysisService | None
        エンジンサービス (None ならエンジンなし)

    Returns
    -------
    dict
        annotate_game.py 互換のテンプレートJSON
    """
    comments = synced.get("synced_comments", [])

    # ply別にコメントをグルーピング
    ply_comments: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for c in comments:
        ply = c.get("ply")
        if ply is not None:
            ply_comments[ply].append(c)

    # 棋譜情報 (USI手順リスト)
    kifu_moves: List[Dict[str, Any]] = []
    if parsed_kifu:
        kifu_moves = parsed_kifu.get("moves", [])

    ply_set = sorted(ply_comments.keys())
    positions: List[Dict[str, Any]] = []
    prev_features: Optional[Dict[str, Any]] = None

    for ply in ply_set:
        ply_coms = ply_comments[ply]

        # move_ja
        move_ja = ply_coms[0].get("move_ja", "") if ply_coms else ""

        # 解説テキストを結合
        combined_text = "。".join(c.get("text", "") for c in ply_coms)

        # フォーカス推定
        focus = _estimate_focus(ply_coms)
        depth = _estimate_depth(ply_coms)
        style = _estimate_style(ply_coms)

        # SFEN (棋譜から生成 - USI手順があれば)
        sfen = "position startpos"

        # 8次元特徴量
        try:
            features = extract_position_features(
                sfen, move=None, ply=ply, prev_features=prev_features,
            )
        except Exception:
            features = {
                "king_safety": 0, "piece_activity": 0, "attack_pressure": 0,
                "phase": "unknown", "move_intent": None,
            }

        features_dict = {
            "king_safety": features.get("king_safety", 0),
            "piece_activity": features.get("piece_activity", 0),
            "attack_pressure": features.get("attack_pressure", 0),
            "phase": features.get("phase", "unknown"),
            "move_intent": features.get("move_intent") or "",
        }

        # エンジン評価
        engine_eval: Dict[str, Any] = {
            "score_cp": None,
            "score_mate": None,
            "best_move": None,
            "pv": None,
            "delta_cp": None,
        }
        if engine_svc is not None:
            try:
                res = engine_svc.analyze_position(sfen)
                if res.ok:
                    engine_eval["score_cp"] = res.score_cp
                    engine_eval["score_mate"] = res.score_mate
                    engine_eval["best_move"] = res.bestmove
                    engine_eval["pv"] = res.pv
            except Exception:
                pass

        # ハイライト判定
        highlight = False
        avg_conf = sum(c.get("confidence", 0) for c in ply_coms) / len(ply_coms) if ply_coms else 0

        # human_annotation を自動埋め
        human_annotation = {
            "commentator_focus": focus,
            "move_intent_human": "",
            "key_insight_ja": combined_text[:200] if combined_text else "",
            "commentary_style": style,
            "commentary_depth": depth,
            "notes": f"auto-imported from commentary sync (confidence: {avg_conf:.2f})",
        }

        # タイムスタンプ情報を追加
        timestamps = [
            {"start": c["timestamp_start"], "end": c["timestamp_end"], "text": c["text"]}
            for c in ply_coms
            if "timestamp_start" in c
        ]

        pos_entry: Dict[str, Any] = {
            "ply": ply,
            "sfen": sfen,
            "move": move_ja,
            "highlight": highlight,
            "engine_eval": engine_eval,
            "features": features_dict,
            "human_annotation": human_annotation,
            "commentary_timestamps": timestamps,
        }
        positions.append(pos_entry)
        prev_features = features

    # ヘッダー情報
    header_info = {}
    if parsed_kifu:
        header_info = parsed_kifu.get("header", {})

    meta: Dict[str, Any] = {
        "game_id": synced.get("source_video", "unknown"),
        "annotator": "commentary-sync-auto",
        "date": date.today().isoformat(),
        "source_type": "commentary_video",
        "source_note": f"kifu: {synced.get('source_kifu', '')}",
        "sente": header_info.get("sente", ""),
        "gote": header_info.get("gote", ""),
    }

    stats = synced.get("stats", {})
    summary: Dict[str, Any] = {
        "total_positions": len(positions),
        "highlighted_positions": sum(1 for p in positions if p["highlight"]),
        "sync_stats": stats,
    }

    return {
        "meta": meta,
        "positions": positions,
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="sync結果をアノテーションテンプレートに変換"
    )
    parser.add_argument(
        "synced", help="sync結果JSON (sync_commentary.py 出力)"
    )
    parser.add_argument(
        "--kifu",
        help="棋譜パース結果JSON (kif_parser.py 出力)",
    )
    parser.add_argument(
        "--output", "-o",
        help="出力JSONファイル (デフォルト: data/annotations/<synced名>_auto.json)",
    )
    parser.add_argument(
        "--with-engine", action="store_true",
        help="エンジン評価値を追加する",
    )
    parser.add_argument(
        "--engine-nodes", type=int, default=150000,
        help="エンジン探索ノード数 (default: 150000)",
    )
    args = parser.parse_args()

    synced_path = Path(args.synced)
    if not synced_path.exists():
        print(f"Error: file not found: {args.synced}", file=sys.stderr)
        sys.exit(1)

    with open(synced_path, encoding="utf-8") as f:
        synced = json.load(f)

    parsed_kifu = None
    if args.kifu:
        kifu_path = Path(args.kifu)
        if not kifu_path.exists():
            print(f"Error: file not found: {args.kifu}", file=sys.stderr)
            sys.exit(1)
        with open(kifu_path, encoding="utf-8") as f:
            parsed_kifu = json.load(f)

    # エンジン起動
    engine_svc = None
    if args.with_engine and _ENGINE_AVAILABLE:
        try:
            engine_svc = EngineAnalysisService(nodes=args.engine_nodes)
            engine_svc.start()
            print(f"Engine started (nodes={args.engine_nodes})")
        except Exception as e:
            print(f"Warning: Engine start failed: {e}", file=sys.stderr)
            engine_svc = None

    try:
        result = import_to_annotation(
            synced,
            parsed_kifu=parsed_kifu,
            engine_svc=engine_svc,
        )

        # 出力先決定
        if args.output:
            output_path = Path(args.output)
        else:
            output_path = (
                _PROJECT_ROOT / "data" / "annotations"
                / f"{synced_path.stem}_auto.json"
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        summary = result.get("summary", {})
        print(f"Positions: {summary.get('total_positions', 0)}")
        print(f"Output: {output_path}")

    finally:
        if engine_svc is not None:
            engine_svc.stop()


if __name__ == "__main__":
    main()
