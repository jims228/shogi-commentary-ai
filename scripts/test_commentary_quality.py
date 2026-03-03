#!/usr/bin/env python3
"""LLM解説品質比較スクリプト.

旧方式（8次元特徴量のみ）と新方式（エンジン + 盤面構造化データ）の
プロンプトで Gemini API に解説を生成させ、explanation_evaluator.py で
採点して比較する。

Usage:
    # 通常実行 (5局面 × 2プロンプト = 10 API リクエスト)
    python3 scripts/test_commentary_quality.py --positions 5

    # ドライラン (API を呼ばずプロンプトだけ表示)
    python3 scripts/test_commentary_quality.py --dry-run

    # 局面数を指定
    python3 scripts/test_commentary_quality.py --positions 3
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from backend.api.services.position_features import extract_position_features
from backend.api.services.board_analyzer import BoardAnalyzer
from backend.api.services.explanation_evaluator import evaluate_explanation
from backend.api.services.ai_service import build_features_block

# エンジンの利用可否を判定
_ENGINE_AVAILABLE = True
try:
    from backend.api.services.engine_analysis import EngineAnalysisService
except ImportError:
    _ENGINE_AVAILABLE = False


# ---------------------------------------------------------------------------
# 局面選択
# ---------------------------------------------------------------------------

def _select_positions(n: int = 5) -> List[Dict[str, Any]]:
    """sample_games.txt から多様な局面を選ぶ.

    序盤1, 中盤前半1, 中盤後半1, 終盤1, 悪手/重要局面1 (可能なら)
    """
    games_path = _PROJECT_ROOT / "data" / "sample_games.txt"
    lines = [
        l.strip()
        for l in games_path.read_text(encoding="utf-8").splitlines()
        if l.strip() and not l.strip().startswith("#")
    ]
    if not lines:
        print("Error: sample_games.txt が空です", file=sys.stderr)
        return []

    game_line = lines[0]
    parts = game_line.split("moves")
    base = parts[0].strip()
    if not base.startswith("position"):
        base = "position " + base
    moves = parts[1].strip().split() if len(parts) > 1 else []

    total_moves = len(moves)

    # 手数を分割して局面を選ぶ
    targets = []

    # 序盤
    ply = min(4, total_moves)
    targets.append({"label": f"序盤 (ply={ply})", "ply": ply, "category": "opening"})

    # 中盤前半
    if n >= 2 and total_moves >= 16:
        ply = 16
        targets.append({"label": f"中盤前半 (ply={ply})", "ply": ply, "category": "midgame_early"})

    # 中盤後半
    if n >= 3 and total_moves >= 28:
        ply = 28
        targets.append({"label": f"中盤後半 (ply={ply})", "ply": ply, "category": "midgame_late"})

    # 終盤
    if n >= 4 and total_moves >= 40:
        ply = min(40, total_moves)
        targets.append({"label": f"終盤 (ply={ply})", "ply": ply, "category": "endgame"})

    # 追加: 途中の局面
    if n >= 5 and total_moves >= 20:
        ply = 20
        targets.append({"label": f"重要局面 (ply={ply})", "ply": ply, "category": "critical"})

    # 指定数に合わせる
    targets = targets[:n]

    positions = []
    for t in targets:
        ply = t["ply"]
        applied = moves[:ply]
        if applied:
            sfen = base + " moves " + " ".join(applied)
        else:
            sfen = base
        current_move = moves[ply] if ply < total_moves else None
        positions.append({
            "label": t["label"],
            "sfen": sfen,
            "move": current_move,
            "ply": ply,
            "category": t["category"],
        })

    return positions


# ---------------------------------------------------------------------------
# プロンプト構築
# ---------------------------------------------------------------------------

def _build_old_prompt(features: Dict[str, Any], ply: int) -> str:
    """旧方式: 8次元特徴量のみのプロンプト (ai_service.py のスタイル)."""
    features_block = build_features_block(features)
    return f"""あなたは将棋の局面解説AIです。
以下の局面について、100〜200文字で解説してください。

手数: {ply}手目
{features_block}
ルール:
- 地の文のみ。箇条書き・見出し・記号禁止
- です/ます調
- 文章を途中で切らないこと"""


def _build_new_prompt(
    features: Dict[str, Any],
    board_analysis: Any,
    engine_data: Optional[Dict[str, Any]],
    ply: int,
) -> str:
    """新方式: エンジン + 盤面構造化データを含むプロンプト."""
    ba = board_analysis
    sections = []

    # 基本情報
    phase_jp = {"opening": "序盤", "midgame": "中盤", "endgame": "終盤"}.get(
        features.get("phase", ""), "不明"
    )
    sections.append(f"""【局面情報】
- 手数: {ply}
- フェーズ: {phase_jp}
- 手番: {'先手' if features.get('turn') == 'b' else '後手'}""")

    # エンジン評価
    if engine_data and engine_data.get("score_cp") is not None:
        sections.append(f"""
【エンジン評価】
- 評価値: {engine_data['score_cp']}cp (先手視点)
- 最善手: {engine_data.get('bestmove', '不明')}
- 読み筋: {engine_data.get('pv', '不明')}""")
        if engine_data.get("delta_cp") is not None:
            sections.append(f"- 前局面との差: {engine_data['delta_cp']:+d}cp")

    # 数値特徴量
    sections.append(f"""
【数値特徴量】
- 玉の安全度: {features.get('king_safety', 0)}/100
- 駒の活用度: {features.get('piece_activity', 0)}/100
- 攻撃圧力: {features.get('attack_pressure', 0)}/100""")

    # 玉の安全度詳細
    kd = ba.king_safety_detail
    for side_key, side_jp in [("sente", "先手"), ("gote", "後手")]:
        sd = kd.get(side_key, {})
        sections.append(f"""
【{side_jp}の玉】
- 位置: {sd.get('king_pos', '?')}
- 囲い: {sd.get('castle_type', '不明')}
- 守り駒(隣接): {sd.get('adjacent_defenders', 0)}
- 逃げ道: {sd.get('escape_squares', 0)}マス""")

    # 争点マス
    if ba.contested_squares:
        sections.append(f"""
【争点マス】
{', '.join(ba.contested_squares[:10])}""")

    # 解説ヒント
    if ba.commentary_hints:
        sections.append(f"""
【局面の特徴】
{chr(10).join('- ' + h for h in ba.commentary_hints)}""")

    prompt_body = "\n".join(sections)

    return f"""あなたは将棋の局面解説AIです。以下の詳細な局面情報をもとに、
具体的で正確な解説を100〜200文字で生成してください。
数値だけでなく、駒の配置や利き関係に基づいた具体的な説明をしてください。
{prompt_body}

ルール:
- 地の文のみ。箇条書き・見出し・記号禁止
- です/ます調
- 具体的な駒名とマス目を挙げて解説
- 文章を途中で切らないこと"""


# ---------------------------------------------------------------------------
# Gemini API 呼び出し
# ---------------------------------------------------------------------------

def _call_gemini(prompt: str) -> Optional[str]:
    """Gemini API を呼び出して解説テキストを返す."""
    try:
        from backend.api.utils.gemini_client import ensure_configured
        import google.generativeai as genai

        if not ensure_configured():
            return None

        model = genai.GenerativeModel(
            "gemini-2.5-flash",
            generation_config=genai.types.GenerationConfig(max_output_tokens=500),
        )
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"  Gemini API error: {e}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# メイン処理
# ---------------------------------------------------------------------------

def run_comparison(
    n_positions: int = 5,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """旧方式 vs 新方式の品質比較を実行する.

    Returns
    -------
    dict
        比較結果 (results, summary)
    """
    positions = _select_positions(n_positions)
    if not positions:
        print("Error: 局面が見つかりません")
        return {}

    analyzer = BoardAnalyzer()

    # エンジン起動
    engine_svc = None
    if _ENGINE_AVAILABLE and not dry_run:
        try:
            engine_svc = EngineAnalysisService(nodes=50000)
            engine_svc.start()
            print("Engine started for analysis.\n")
        except Exception as e:
            print(f"Warning: Engine start failed: {e}")
            print("Continuing without engine.\n")
            engine_svc = None

    results: List[Dict[str, Any]] = []

    try:
        for i, pos in enumerate(positions):
            print("=" * 70)
            print(f"  局面 {i + 1}: {pos['label']}")
            print("=" * 70)

            # --- データ収集 ---
            features = extract_position_features(
                pos["sfen"], move=pos["move"], ply=pos["ply"],
            )
            ba = analyzer.analyze(pos["sfen"], move=pos["move"], ply=pos["ply"])

            engine_data: Optional[Dict[str, Any]] = None
            if engine_svc:
                try:
                    res = engine_svc.analyze_position(pos["sfen"])
                    if res.ok:
                        engine_data = {
                            "score_cp": res.score_cp,
                            "score_mate": res.score_mate,
                            "bestmove": res.bestmove,
                            "pv": res.pv,
                            "delta_cp": None,
                        }
                except Exception:
                    pass

            # --- プロンプト構築 ---
            old_prompt = _build_old_prompt(features, pos["ply"])
            new_prompt = _build_new_prompt(features, ba, engine_data, pos["ply"])

            if dry_run:
                print("\n--- OLD PROMPT ---")
                print(old_prompt)
                print(f"\n[{len(old_prompt)}文字]")
                print("\n--- NEW PROMPT ---")
                print(new_prompt)
                print(f"\n[{len(new_prompt)}文字]")
                print()
                results.append({
                    "position": pos["label"],
                    "ply": pos["ply"],
                    "old_prompt_len": len(old_prompt),
                    "new_prompt_len": len(new_prompt),
                    "dry_run": True,
                })
                continue

            # --- Gemini API 呼び出し ---
            print("\n  Generating OLD commentary...", end="", flush=True)
            old_text = _call_gemini(old_prompt)
            if old_text is None:
                print(" FAILED (API unavailable)")
                print("  Skipping remaining positions.")
                break
            print(f" done ({len(old_text)}文字)")
            time.sleep(1)  # レート制限対策

            print("  Generating NEW commentary...", end="", flush=True)
            new_text = _call_gemini(new_prompt)
            if new_text is None:
                print(" FAILED")
                continue
            print(f" done ({len(new_text)}文字)")
            time.sleep(1)

            # --- 表示 ---
            print(f"\n  [旧方式の解説]")
            print(f"  {old_text}")
            print(f"\n  [新方式の解説]")
            print(f"  {new_text}")

            # --- 評価 ---
            old_eval = evaluate_explanation(old_text, features)
            new_eval = evaluate_explanation(new_text, features)

            print(f"\n  [評価]")
            print(f"  {'':20s} {'旧方式':>8s} {'新方式':>8s} {'差':>8s}")
            for axis in ("context_relevance", "naturalness", "informativeness", "readability"):
                old_s = old_eval["scores"][axis]
                new_s = new_eval["scores"][axis]
                diff = new_s - old_s
                marker = " ←" if abs(diff) >= 15 else ""
                print(f"  {axis:20s} {old_s:>8d} {new_s:>8d} {diff:>+8d}{marker}")
            print(f"  {'total':20s} {old_eval['total']:>8.1f} {new_eval['total']:>8.1f} "
                  f"{new_eval['total'] - old_eval['total']:>+8.1f}")
            print()

            results.append({
                "position": pos["label"],
                "ply": pos["ply"],
                "category": pos["category"],
                "old_text": old_text,
                "new_text": new_text,
                "old_eval": old_eval,
                "new_eval": new_eval,
            })

    finally:
        if engine_svc:
            engine_svc.stop()

    # --- 総合結果 ---
    evaluated = [r for r in results if "old_eval" in r]
    summary: Dict[str, Any] = {}

    if evaluated:
        print("=" * 70)
        print("  総合結果")
        print("=" * 70)

        axes = ("context_relevance", "naturalness", "informativeness", "readability")
        print(f"\n  {'':20s} {'旧方式平均':>10s} {'新方式平均':>10s} {'改善幅':>8s}")

        for axis in axes:
            old_avg = sum(r["old_eval"]["scores"][axis] for r in evaluated) / len(evaluated)
            new_avg = sum(r["new_eval"]["scores"][axis] for r in evaluated) / len(evaluated)
            diff = new_avg - old_avg
            marker = " ←" if abs(diff) >= 10 else ""
            print(f"  {axis:20s} {old_avg:>10.1f} {new_avg:>10.1f} {diff:>+8.1f}{marker}")

        old_total_avg = sum(r["old_eval"]["total"] for r in evaluated) / len(evaluated)
        new_total_avg = sum(r["new_eval"]["total"] for r in evaluated) / len(evaluated)
        print(f"  {'total':20s} {old_total_avg:>10.1f} {new_total_avg:>10.1f} "
              f"{new_total_avg - old_total_avg:>+8.1f}")
        print()

        summary = {
            "n_positions": len(evaluated),
            "old_avg_total": round(old_total_avg, 1),
            "new_avg_total": round(new_total_avg, 1),
            "improvement": round(new_total_avg - old_total_avg, 1),
            "per_axis": {
                axis: {
                    "old_avg": round(sum(r["old_eval"]["scores"][axis] for r in evaluated) / len(evaluated), 1),
                    "new_avg": round(sum(r["new_eval"]["scores"][axis] for r in evaluated) / len(evaluated), 1),
                }
                for axis in axes
            },
        }

    return {"results": results, "summary": summary}


def _save_results(data: Dict[str, Any]) -> Optional[Path]:
    """結果をJSONファイルに保存."""
    if not data.get("results"):
        return None

    # dry_run の場合は保存しない
    if any(r.get("dry_run") for r in data["results"]):
        return None

    experiments_dir = _PROJECT_ROOT / "data" / "experiments"
    experiments_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = experiments_dir / f"enriched_vs_baseline_{timestamp}.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return output_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="旧方式 vs 新方式の LLM 解説品質比較"
    )
    parser.add_argument(
        "--positions", type=int, default=5,
        help="比較する局面数 (default: 5)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Gemini API を呼ばずプロンプトだけ表示",
    )
    args = parser.parse_args()

    data = run_comparison(
        n_positions=args.positions,
        dry_run=args.dry_run,
    )

    if not args.dry_run and data.get("results"):
        output_path = _save_results(data)
        if output_path:
            print(f"Results saved to: {output_path}")


if __name__ == "__main__":
    main()
