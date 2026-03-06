"""scripts/compare_legacy_vs_planner.py

Legacy方式 vs Planner方式 の解説品質を同一局面で比較する.

使い方:
  # LLMなし (テンプレート/フォールバック同士の比較)
  python scripts/compare_legacy_vs_planner.py

  # LLMあり (GEMINI_API_KEY が必要)
  USE_LLM=1 python scripts/compare_legacy_vs_planner.py

  # カスタム入力ファイル
  python scripts/compare_legacy_vs_planner.py --input data/my_positions.json

出力: data/experiments/legacy_vs_planner_<timestamp>.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# プロジェクトルートをパスに追加
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from backend.api.services.explanation_evaluator import evaluate_explanation
from backend.api.services.position_features import extract_position_features


def _load_positions(path: str) -> List[Dict[str, Any]]:
    """benchmark_positions.json 形式の局面リストを読み込む."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _build_candidates_from_position(pos: Dict[str, Any]) -> List[Dict[str, Any]]:
    """テスト用の候補手を生成 (実エンジンなしの簡易版)."""
    # benchmark_positions.json にはcandidatesがないので、ダミーを返す
    return pos.get("candidates", [])


def _build_prev_moves(pos: Dict[str, Any]) -> Optional[List[str]]:
    """prev_moves があれば返す."""
    return pos.get("prev_moves")


async def _generate_legacy(
    ply: int,
    sfen: str,
    candidates: List[Dict[str, Any]],
    user_move: Optional[str],
    delta_cp: Optional[int],
    features: Optional[Dict[str, Any]],
    style: str,
    use_llm: bool,
) -> Dict[str, Any]:
    """Legacy方式で解説を生成."""
    if use_llm:
        from backend.api.services.ai_service import AIService
        explanation = await AIService.generate_position_comment(
            ply=ply, sfen=sfen, candidates=candidates,
            user_move=user_move, delta_cp=delta_cp,
            features=features, style=style,
        )
        return {"explanation": explanation, "error": False}

    # LLMなし: フォールバックテンプレート
    from backend.api.services.ai_service import build_features_block
    if features:
        phase_jp = {"opening": "序盤", "midgame": "中盤", "endgame": "終盤"}
        phase = phase_jp.get(features.get("phase", ""), "不明")
        explanation = f"{phase}の局面です。"
    else:
        explanation = "局面の解説を生成できませんでした。"
    return {"explanation": explanation, "error": False}


async def _generate_planner(
    ply: int,
    sfen: str,
    candidates: List[Dict[str, Any]],
    user_move: Optional[str],
    delta_cp: Optional[int],
    style: str,
    prev_moves: Optional[List[str]],
    use_llm: bool,
) -> Dict[str, Any]:
    """Planner方式で解説を生成."""
    from backend.api.services.ai_service import AIService, _build_planned_fallback

    if use_llm:
        result = await AIService.generate_planned_comment(
            ply=ply, sfen=sfen, candidates=candidates,
            user_move=user_move, delta_cp=delta_cp,
            style=style, prev_moves=prev_moves,
        )
        return {
            "explanation": result["explanation"],
            "plan": result.get("plan"),
            "error": False,
        }

    # LLMなし: プラン生成 → フォールバック
    from backend.api.services.explanation_planner import ExplanationPlanner
    planner = ExplanationPlanner()
    plan = planner.build_plan(
        sfen=sfen, move=user_move, ply=ply,
        candidates=candidates, delta_cp=delta_cp,
        user_move=user_move, prev_moves=prev_moves,
    )
    explanation = _build_planned_fallback(plan)
    return {
        "explanation": explanation,
        "plan": plan.to_dict(),
        "error": False,
        "is_fallback": True,
    }


async def compare_single(
    pos: Dict[str, Any],
    use_llm: bool,
    style: str = "neutral",
) -> Dict[str, Any]:
    """1局面について legacy / planner を両方実行し比較結果を返す."""
    sfen = pos["sfen"]
    ply = pos.get("ply", 0)
    user_move = pos.get("user_move")
    delta_cp = pos.get("delta_cp")
    candidates = _build_candidates_from_position(pos)
    prev_moves = _build_prev_moves(pos)

    # 特徴量抽出 (共通)
    features = None
    try:
        features = extract_position_features(sfen=sfen, move=user_move, ply=ply)
    except Exception:
        pass

    # Legacy
    legacy_result: Dict[str, Any] = {"explanation": "", "error": True}
    try:
        legacy_result = await _generate_legacy(
            ply=ply, sfen=sfen, candidates=candidates,
            user_move=user_move, delta_cp=delta_cp,
            features=features, style=style, use_llm=use_llm,
        )
    except Exception as e:
        legacy_result = {"explanation": "", "error": True, "error_msg": str(e)}

    # Planner
    planner_result: Dict[str, Any] = {"explanation": "", "plan": None, "error": True}
    try:
        planner_result = await _generate_planner(
            ply=ply, sfen=sfen, candidates=candidates,
            user_move=user_move, delta_cp=delta_cp,
            style=style, prev_moves=prev_moves, use_llm=use_llm,
        )
    except Exception as e:
        planner_result = {"explanation": "", "plan": None, "error": True, "error_msg": str(e)}

    # 評価
    legacy_eval = evaluate_explanation(legacy_result["explanation"], features)
    planner_eval = evaluate_explanation(planner_result["explanation"], features)

    # フォールバック判定: フラグベース (API側で判定済み)
    is_fallback = planner_result.get("is_fallback", not use_llm)

    return {
        "name": pos.get("name", ""),
        "sfen": sfen,
        "ply": ply,
        "prev_moves": prev_moves,
        "candidates": candidates,
        "user_move": user_move,
        "delta_cp": delta_cp,
        "style": style,
        "legacy_explanation": legacy_result["explanation"],
        "legacy_char_count": len(legacy_result["explanation"]),
        "legacy_error": legacy_result.get("error", False),
        "legacy_eval": legacy_eval,
        "planner_explanation": planner_result["explanation"],
        "planner_char_count": len(planner_result["explanation"]),
        "planner_error": planner_result.get("error", False),
        "planner_plan": planner_result.get("plan"),
        "planner_eval": planner_eval,
        "planner_has_deep_reason": bool(
            planner_result.get("plan", {}).get("deep_reason", "")
            if isinstance(planner_result.get("plan"), dict)
            else False
        ),
        "is_fallback": is_fallback,
    }


async def run_comparison(
    positions: List[Dict[str, Any]],
    use_llm: bool,
    style: str = "neutral",
) -> Dict[str, Any]:
    """全局面を比較し、集計結果を返す."""
    results: List[Dict[str, Any]] = []
    for pos in positions:
        result = await compare_single(pos, use_llm=use_llm, style=style)
        results.append(result)

    # 集計
    legacy_totals = [r["legacy_eval"]["total"] for r in results if not r["legacy_error"]]
    planner_totals = [r["planner_eval"]["total"] for r in results if not r["planner_error"]]
    fallback_count = sum(1 for r in results if r["is_fallback"])
    error_count = sum(1 for r in results if r["legacy_error"] or r["planner_error"])

    summary = {
        "total_positions": len(results),
        "use_llm": use_llm,
        "style": style,
        "legacy_avg_score": round(sum(legacy_totals) / max(1, len(legacy_totals)), 1),
        "planner_avg_score": round(sum(planner_totals) / max(1, len(planner_totals)), 1),
        "fallback_count": fallback_count,
        "error_count": error_count,
        "planner_wins": sum(
            1 for r in results
            if r["planner_eval"]["total"] > r["legacy_eval"]["total"]
        ),
        "legacy_wins": sum(
            1 for r in results
            if r["legacy_eval"]["total"] > r["planner_eval"]["total"]
        ),
        "ties": sum(
            1 for r in results
            if r["planner_eval"]["total"] == r["legacy_eval"]["total"]
        ),
        "deep_reason_count": sum(1 for r in results if r.get("planner_has_deep_reason")),
        "note": "evaluator はルールベース (4軸: context_relevance, naturalness, informativeness, readability)。LLM評価ではないため参考値。",
    }

    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "summary": summary,
        "positions": results,
    }


def main():
    parser = argparse.ArgumentParser(description="Legacy vs Planner comparison")
    parser.add_argument(
        "--input", "-i",
        default=str(_PROJECT_ROOT / "data" / "benchmark_positions.json"),
        help="入力局面JSONファイル (default: data/benchmark_positions.json)",
    )
    parser.add_argument(
        "--style", "-s",
        default="neutral",
        choices=["neutral", "technical", "encouraging"],
        help="解説スタイル (default: neutral)",
    )
    args = parser.parse_args()

    use_llm = os.getenv("USE_LLM", "0") == "1"

    positions = _load_positions(args.input)
    print(f"[compare] {len(positions)} positions loaded from {args.input}")
    print(f"[compare] use_llm={use_llm}, style={args.style}")

    report = asyncio.run(run_comparison(positions, use_llm=use_llm, style=args.style))

    # 出力
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_dir = _PROJECT_ROOT / "data" / "experiments"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"legacy_vs_planner_{ts}.json"

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # サマリー表示
    s = report["summary"]
    print(f"\n=== Comparison Summary ===")
    print(f"Positions: {s['total_positions']}")
    print(f"Legacy avg score:  {s['legacy_avg_score']}")
    print(f"Planner avg score: {s['planner_avg_score']}")
    print(f"Planner wins: {s['planner_wins']}, Legacy wins: {s['legacy_wins']}, Ties: {s['ties']}")
    print(f"Fallbacks: {s['fallback_count']}, Errors: {s['error_count']}")
    print(f"Deep reasons: {s['deep_reason_count']}/{s['total_positions']}")
    print(f"\nOutput: {out_path}")


if __name__ == "__main__":
    main()
