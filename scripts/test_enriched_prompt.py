#!/usr/bin/env python3
"""Step 4: 旧方式 vs 新方式のプロンプト比較スクリプト.

sample_games.txt から3局面を選んで:
1. position_features.py で8次元特徴量を取得
2. engine_analysis.py で評価値・最善手を取得（エンジン使用）
3. board_analyzer.py で構造化データを取得

旧方式（8次元のみ）と新方式（全データ統合）のプロンプトを並べて表示し、
情報量の違いを確認する。Gemini API は呼ばない。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from backend.api.services.position_features import extract_position_features
from backend.api.services.board_analyzer import BoardAnalyzer

# エンジンの利用可否を判定
_USE_ENGINE = True
try:
    from backend.api.services.engine_analysis import EngineAnalysisService
except ImportError:
    _USE_ENGINE = False


def _select_positions() -> list[dict]:
    """sample_games.txt から序盤・中盤・終盤の3局面を選ぶ."""
    games_path = _PROJECT_ROOT / "data" / "sample_games.txt"
    lines = [
        l.strip()
        for l in games_path.read_text(encoding="utf-8").splitlines()
        if l.strip() and not l.strip().startswith("#")
    ]
    if not lines:
        print("Error: sample_games.txt に棋譜が見つかりません", file=sys.stderr)
        sys.exit(1)

    game_line = lines[0]  # 矢倉模範手順
    # "position startpos moves ..." から moves を抽出
    parts = game_line.split("moves")
    base = parts[0].strip()
    moves = parts[1].strip().split() if len(parts) > 1 else []

    positions = []
    # 序盤: ply=4
    if len(moves) >= 5:
        sfen = base + " moves " + " ".join(moves[:4])
        positions.append({
            "label": "序盤 (4手目)",
            "sfen": sfen,
            "move": moves[4] if len(moves) > 4 else None,
            "ply": 4,
            "moves": moves[:4],
        })

    # 中盤: ply=16
    if len(moves) >= 17:
        sfen = base + " moves " + " ".join(moves[:16])
        positions.append({
            "label": "中盤 (16手目)",
            "sfen": sfen,
            "move": moves[16] if len(moves) > 16 else None,
            "ply": 16,
            "moves": moves[:16],
        })

    # 終盤相当: ply=28
    if len(moves) >= 29:
        sfen = base + " moves " + " ".join(moves[:28])
        positions.append({
            "label": "終盤寄り (28手目)",
            "sfen": sfen,
            "move": moves[28] if len(moves) > 28 else None,
            "ply": 28,
            "moves": moves[:28],
        })

    return positions


def _build_old_prompt(features: dict, ply: int) -> str:
    """旧方式: 8次元特徴量のみのプロンプト."""
    return f"""あなたは将棋解説者です。以下の局面を解説してください。

【局面情報】
- 手数: {ply}
- フェーズ: {features.get('phase', '不明')}
- 手番: {'先手' if features.get('turn') == 'b' else '後手'}
- 玉の安全度: {features.get('king_safety', 0)}/100
- 駒の活用度: {features.get('piece_activity', 0)}/100
- 攻撃圧力: {features.get('attack_pressure', 0)}/100
- 手の意図: {features.get('move_intent', '不明')}
- 変化量:
  - 玉の安全度変化: {features.get('tension_delta', {}).get('d_king_safety', 0):.1f}
  - 駒の活用度変化: {features.get('tension_delta', {}).get('d_piece_activity', 0):.1f}
  - 攻撃圧力変化: {features.get('tension_delta', {}).get('d_attack_pressure', 0):.1f}

この局面の特徴と次の一手の狙いを解説してください。"""


def _build_new_prompt(
    features: dict,
    board_analysis: object,
    engine_data: dict | None,
    ply: int,
) -> str:
    """新方式: 全データ統合プロンプト."""
    ba = board_analysis

    sections = []

    # 基本情報
    sections.append(f"""【局面情報】
- 手数: {ply}
- フェーズ: {features.get('phase', '不明')}
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
- 攻撃圧力: {features.get('attack_pressure', 0)}/100
- 手の意図: {features.get('move_intent', '不明')}""")

    # 玉の安全度詳細
    kd = ba.king_safety_detail
    for side_key, side_jp in [("sente", "先手"), ("gote", "後手")]:
        sd = kd.get(side_key, {})
        sections.append(f"""
【{side_jp}の玉】
- 位置: {sd.get('king_pos', '?')}
- 囲い: {sd.get('castle_type', '不明')}
- 守り駒(隣接): {sd.get('adjacent_defenders', 0)}
- 敵の利き(隣接): {sd.get('adjacent_attackers', 0)}
- 逃げ道: {sd.get('escape_squares', 0)}マス""")

    # 浮き駒
    if ba.hanging_pieces:
        hanging_strs = [
            f"{h['square']}の{h['piece']}({h['side']})"
            for h in ba.hanging_pieces[:5]
        ]
        sections.append(f"""
【浮き駒（守りの利きがない駒）】
{chr(10).join('- ' + s for s in hanging_strs)}""")

    # 脅威
    if ba.threats:
        threat_strs = []
        for t in ba.threats[:5]:
            if t["type"] == "check":
                threat_strs.append(f"王手: {t['by']}({t['from']})→{t['to']}")
            elif t["type"] == "hanging":
                threat_strs.append(f"駒取り: {t['attacker']}が{t['at']}の{t['target']}を狙う")
            elif t["type"] == "fork_potential":
                threat_strs.append(f"両取り: {t['piece']}({t['at']})→{','.join(t['targets'])}")
        if threat_strs:
            sections.append(f"""
【脅威】
{chr(10).join('- ' + s for s in threat_strs)}""")

    # 争点
    if ba.contested_squares:
        sections.append(f"""
【争点マス（両者の利きが重なる）】
{', '.join(ba.contested_squares[:10])}""")

    # 手の影響
    if ba.move_impact:
        mi = ba.move_impact
        impact_parts = [f"- 動かした駒: {mi.get('moved_piece', '?')}"]
        if mi.get("from_sq"):
            impact_parts.append(f"- 移動: {mi['from_sq']}→{mi['to_sq']}")
        if mi.get("captured"):
            impact_parts.append(f"- 取った駒: {mi['captured']}")
        if mi.get("opened_lines"):
            impact_parts.append("- 大駒の筋が通った")
        if mi.get("new_attacks"):
            impact_parts.append(f"- 新たな利き: {', '.join(mi['new_attacks'][:5])}")
        sections.append(f"""
【この手の影響】
{chr(10).join(impact_parts)}""")

    # 解説ヒント
    if ba.commentary_hints:
        sections.append(f"""
【局面の特徴（解説ヒント）】
{chr(10).join('- ' + h for h in ba.commentary_hints)}""")

    prompt_body = "\n".join(sections)

    return f"""あなたは将棋解説者です。以下の詳細な局面情報をもとに、具体的で正確な解説を生成してください。
数値だけでなく、駒の配置や利き関係に基づいた具体的な説明をしてください。
{prompt_body}

この局面の特徴と次の一手の狙いを、具体的な駒名とマス目を挙げて解説してください。"""


def main() -> None:
    positions = _select_positions()
    if not positions:
        print("Error: 解析する局面が見つかりません")
        return

    analyzer = BoardAnalyzer()

    # エンジン起動（可能であれば）
    engine_svc = None
    if _USE_ENGINE:
        try:
            engine_svc = EngineAnalysisService(nodes=50000)
            engine_svc.start()
            print("Engine started for analysis.\n")
        except Exception as e:
            print(f"Warning: Engine start failed: {e}")
            print("Continuing without engine evaluation.\n")
            engine_svc = None

    try:
        for pos in positions:
            print("=" * 70)
            print(f"  {pos['label']}")
            print(f"  SFEN: {pos['sfen'][:80]}...")
            if pos["move"]:
                print(f"  次の手: {pos['move']}")
            print("=" * 70)

            # 1. 8次元特徴量
            features = extract_position_features(
                pos["sfen"],
                move=pos["move"],
                ply=pos["ply"],
            )

            # 2. エンジン評価
            engine_data: dict | None = None
            if engine_svc:
                res = engine_svc.analyze_position(pos["sfen"])
                if res.ok:
                    engine_data = {
                        "score_cp": res.score_cp,
                        "score_mate": res.score_mate,
                        "bestmove": res.bestmove,
                        "pv": res.pv,
                        "delta_cp": None,  # 単一局面なので delta なし
                    }

            # 3. 構造化データ
            ba = analyzer.analyze(pos["sfen"], move=pos["move"], ply=pos["ply"])

            # --- 旧方式プロンプト ---
            old_prompt = _build_old_prompt(features, pos["ply"])
            # --- 新方式プロンプト ---
            new_prompt = _build_new_prompt(features, ba, engine_data, pos["ply"])

            print()
            print("-" * 35 + " OLD " + "-" * 30)
            print(old_prompt)
            print()
            print("-" * 35 + " NEW " + "-" * 30)
            print(new_prompt)
            print()

            # 文字数比較
            old_chars = len(old_prompt)
            new_chars = len(new_prompt)
            print(f"[文字数] OLD: {old_chars}文字  →  NEW: {new_chars}文字  "
                  f"(+{new_chars - old_chars}文字, {new_chars / old_chars:.1f}x)")
            print()

    finally:
        if engine_svc:
            engine_svc.stop()


if __name__ == "__main__":
    main()
