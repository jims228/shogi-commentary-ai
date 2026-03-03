#!/usr/bin/env python3
"""アノテーション支援スクリプト.

NHK杯の動画を見ながらプロ解説者の着目点をラベル付けするための
前処理ツール。棋譜を読み込んで、エンジン分析 + 盤面構造化データ +
8次元特徴量を自動的に埋めたJSONテンプレートを生成する。

人間が埋めるべきフィールド (human_annotation) は空欄のまま出力する。

Usage:
    python3 scripts/annotate_game.py data/sample_games.txt \
      --output data/annotations/game01_template.json \
      --game-index 0

    # エンジンなしで実行 (テスト・デバッグ用)
    python3 scripts/annotate_game.py data/sample_games.txt --no-engine

    # 5手ごとにサンプリング
    python3 scripts/annotate_game.py data/sample_games.txt --interval 5
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.batch_extract_features import _parse_game_line
from backend.api.services.position_features import extract_position_features
from backend.api.services.board_analyzer import BoardAnalyzer

# エンジンの利用可否を判定
_ENGINE_AVAILABLE = True
try:
    from backend.api.services.engine_analysis import EngineAnalysisService
except ImportError:
    _ENGINE_AVAILABLE = False

# ---------------------------------------------------------------------------
# ハイライト判定の閾値
# ---------------------------------------------------------------------------
_DELTA_HIGHLIGHT_THRESHOLD = 150  # |delta_cp| > 150 で highlight


# ---------------------------------------------------------------------------
# テンプレート生成
# ---------------------------------------------------------------------------

def _empty_human_annotation() -> Dict[str, Any]:
    """人間が埋めるアノテーション欄 (すべて空)."""
    return {
        "commentator_focus": {
            "primary": "",
            "secondary": [],
            "ignored": [],
        },
        "move_intent_human": "",
        "key_insight_ja": "",
        "commentary_style": "",
        "commentary_depth": "",
        "notes": "",
    }


def _board_analysis_to_dict(ba: Any) -> Dict[str, Any]:
    """BoardAnalysis をテンプレート用辞書に変換."""
    ks = ba.king_safety_detail
    sente_ks = ks.get("sente", {})
    gote_ks = ks.get("gote", {})
    return {
        "king_safety_sente": {
            "king_pos": sente_ks.get("king_pos"),
            "castle_type": sente_ks.get("castle_type", "不明"),
            "adjacent_defenders": sente_ks.get("adjacent_defenders", 0),
            "escape_squares": sente_ks.get("escape_squares", 0),
        },
        "king_safety_gote": {
            "king_pos": gote_ks.get("king_pos"),
            "castle_type": gote_ks.get("castle_type", "不明"),
            "adjacent_defenders": gote_ks.get("adjacent_defenders", 0),
            "escape_squares": gote_ks.get("escape_squares", 0),
        },
        "contested_squares": ba.contested_squares,
        "hanging_pieces": [
            {"square": h["square"], "piece": h["piece"], "side": h["side"]}
            for h in ba.hanging_pieces
        ],
        "commentary_hints": ba.commentary_hints,
    }


def _features_to_dict(features: Dict[str, Any]) -> Dict[str, Any]:
    """position_features の出力からテンプレート用辞書を生成."""
    return {
        "king_safety": features.get("king_safety", 0),
        "piece_activity": features.get("piece_activity", 0),
        "attack_pressure": features.get("attack_pressure", 0),
        "phase": features.get("phase", "unknown"),
        "move_intent": features.get("move_intent") or "",
    }


def generate_annotation_template(
    game_line: str,
    game_id: str = "unknown",
    interval: int = 1,
    engine_svc: Any = None,
) -> Dict[str, Any]:
    """棋譜1局分のアノテーションテンプレートを生成する.

    Parameters
    ----------
    game_line : str
        USI形式の棋譜行
    game_id : str
        ゲームID
    interval : int
        サンプリング間隔 (1=全手)
    engine_svc : EngineAnalysisService | None
        エンジンサービス (None ならエンジンなし)

    Returns
    -------
    dict
        アノテーションテンプレートJSON
    """
    base_position, moves = _parse_game_line(game_line)
    if not base_position:
        return {"error": "棋譜のパースに失敗しました"}

    analyzer = BoardAnalyzer()
    positions: List[Dict[str, Any]] = []
    prev_score_cp: Optional[int] = None
    prev_features: Optional[Dict[str, Any]] = None

    # フェーズ分布カウント
    phase_counts: Dict[str, int] = {"opening": 0, "midgame": 0, "endgame": 0}
    blunder_positions: List[int] = []
    mate_positions: List[int] = []
    highlighted_count = 0

    total_plys = len(moves) + 1  # ply 0 (初期局面) から

    for ply in range(0, total_plys, interval):
        applied_moves = moves[:ply]
        if applied_moves:
            sfen = base_position + " moves " + " ".join(applied_moves)
        else:
            sfen = base_position

        current_move = moves[ply] if ply < len(moves) else None

        # --- エンジン評価 ---
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
                    # 先手視点に統一
                    score_cp_sente: Optional[int] = None
                    if res.score_cp is not None:
                        score_cp_sente = (
                            res.score_cp if ply % 2 == 0 else -res.score_cp
                        )
                    delta_cp: Optional[int] = None
                    if score_cp_sente is not None and prev_score_cp is not None:
                        sente_diff = score_cp_sente - prev_score_cp
                        is_sente_move = ply % 2 == 0
                        delta_cp = sente_diff if is_sente_move else -sente_diff

                    engine_eval = {
                        "score_cp": score_cp_sente,
                        "score_mate": res.score_mate,
                        "best_move": res.bestmove,
                        "pv": res.pv,
                        "delta_cp": delta_cp,
                    }
                    if score_cp_sente is not None:
                        prev_score_cp = score_cp_sente
            except Exception:
                pass

        # --- 盤面構造化データ ---
        ba = analyzer.analyze(sfen, move=current_move, ply=ply)
        board_analysis = _board_analysis_to_dict(ba)

        # --- 8次元特徴量 ---
        eval_info = None
        if engine_eval["score_cp"] is not None or engine_eval["score_mate"] is not None:
            eval_info = {
                "score_cp": engine_eval["score_cp"],
                "score_mate": engine_eval["score_mate"],
            }

        try:
            features = extract_position_features(
                sfen,
                move=current_move,
                ply=ply,
                eval_info=eval_info,
                prev_features=prev_features,
            )
        except Exception:
            features = {
                "king_safety": 0, "piece_activity": 0, "attack_pressure": 0,
                "phase": "unknown", "move_intent": None,
            }

        features_dict = _features_to_dict(features)

        # --- ハイライト判定 ---
        highlight = False
        if engine_eval["delta_cp"] is not None:
            if abs(engine_eval["delta_cp"]) > _DELTA_HIGHLIGHT_THRESHOLD:
                highlight = True
                blunder_positions.append(ply)
        if engine_eval["score_mate"] is not None:
            highlight = True
            mate_positions.append(ply)

        if highlight:
            highlighted_count += 1

        # --- フェーズカウント ---
        phase = features_dict.get("phase", "unknown")
        if phase in phase_counts:
            phase_counts[phase] += 1

        # --- ポジション辞書 ---
        pos_entry: Dict[str, Any] = {
            "ply": ply,
            "sfen": sfen,
            "move": current_move,
            "highlight": highlight,
            "engine_eval": engine_eval,
            "board_analysis": board_analysis,
            "features": features_dict,
            "human_annotation": _empty_human_annotation(),
        }
        positions.append(pos_entry)
        prev_features = features

    # --- サマリー ---
    summary: Dict[str, Any] = {
        "total_positions": len(positions),
        "highlighted_positions": highlighted_count,
        "blunder_positions": blunder_positions,
        "mate_positions": mate_positions,
        "phase_distribution": phase_counts,
    }

    # --- メタ ---
    meta: Dict[str, Any] = {
        "game_id": game_id,
        "annotator": "",
        "date": date.today().isoformat(),
        "source_type": "sample_corpus",
        "source_note": "",
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
        description="棋譜からアノテーションテンプレートを生成"
    )
    parser.add_argument("input", help="入力ファイル (1行1棋譜のUSIリスト)")
    parser.add_argument(
        "--output", "-o",
        help="出力JSONファイル (デフォルト: data/annotations/game{index}_template.json)",
    )
    parser.add_argument(
        "--game-index", type=int, default=0,
        help="対象棋譜のインデックス (0始まり, default: 0)",
    )
    parser.add_argument(
        "--interval", type=int, default=1,
        help="サンプリング間隔 (1=全手, default: 1)",
    )
    parser.add_argument(
        "--no-engine", action="store_true",
        help="エンジンを使用しない (テスト・デバッグ用)",
    )
    parser.add_argument(
        "--engine-nodes", type=int, default=150000,
        help="エンジン探索ノード数 (default: 150000)",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    lines = [
        l.strip()
        for l in input_path.read_text(encoding="utf-8").splitlines()
        if l.strip() and not l.strip().startswith("#")
    ]

    if args.game_index >= len(lines):
        print(
            f"Error: game-index {args.game_index} is out of range "
            f"(0-{len(lines)-1})",
            file=sys.stderr,
        )
        sys.exit(1)

    game_line = lines[args.game_index]
    game_id = f"sample_game_{args.game_index}"

    # エンジン起動
    engine_svc = None
    if not args.no_engine and _ENGINE_AVAILABLE:
        try:
            engine_svc = EngineAnalysisService(nodes=args.engine_nodes)
            engine_svc.start()
            print(f"Engine started (nodes={args.engine_nodes})")
        except Exception as e:
            print(f"Warning: Engine start failed: {e}", file=sys.stderr)
            print("Continuing without engine.", file=sys.stderr)
            engine_svc = None

    try:
        t0 = time.time()
        template = generate_annotation_template(
            game_line,
            game_id=game_id,
            interval=args.interval,
            engine_svc=engine_svc,
        )
        elapsed = time.time() - t0

        # 出力先決定
        if args.output:
            output_path = Path(args.output)
        else:
            output_path = (
                _PROJECT_ROOT / "data" / "annotations"
                / f"game{args.game_index:02d}_template.json"
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(template, f, ensure_ascii=False, indent=2)

        summary = template.get("summary", {})
        print(f"\nDone in {elapsed:.1f}s")
        print(f"  Positions: {summary.get('total_positions', 0)}")
        print(f"  Highlighted: {summary.get('highlighted_positions', 0)}")
        print(f"  Output: {output_path}")

    finally:
        if engine_svc is not None:
            engine_svc.stop()


if __name__ == "__main__":
    main()
