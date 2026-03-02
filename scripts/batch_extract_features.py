#!/usr/bin/env python3
"""USI形式の棋譜リストから全手の特徴量を一括抽出し、
JSONL形式で保存する。Gemini APIは使わない。

Usage:
    python scripts/batch_extract_features.py input.txt output.jsonl
    python scripts/batch_extract_features.py input.txt output.jsonl --interval 10
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# プロジェクトルートをパスに追加
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from backend.api.services.position_features import extract_position_features


def _parse_game_line(line: str) -> tuple[str, List[str]]:
    """1行のUSI棋譜を (base_position, moves) にパースする.

    対応フォーマット:
      - "position startpos moves 7g7f 3c3d ..."
      - "startpos moves 7g7f 3c3d ..."
      - "7g7f 3c3d ..."  (startpos + moves のみ)
    """
    line = line.strip()
    if not line:
        return "", []

    if line.startswith("position "):
        line = line[len("position "):].strip()

    if line.startswith("startpos"):
        rest = line[len("startpos"):].strip()
        if rest.startswith("moves"):
            moves = rest[len("moves"):].strip().split()
        else:
            moves = []
        return "position startpos", moves

    if line.startswith("sfen "):
        parts = line.split()
        if "moves" in parts:
            mi = parts.index("moves")
            base = "position " + " ".join(parts[:mi])
            moves = parts[mi + 1:]
        else:
            base = "position " + line
            moves = []
        return base, moves

    # moves のみ (startpos と仮定)
    moves = line.split()
    return "position startpos", moves


def batch_extract(
    input_file: str,
    output_file: str,
    sample_interval: int = 5,
) -> Dict[str, Any]:
    """棋譜ファイルからバッチで特徴量を抽出する.

    Parameters
    ----------
    input_file : str
        1行1棋譜のUSIリスト (.txt)
    output_file : str
        出力JSONL
    sample_interval : int
        N手ごとにサンプリング (default: 5)

    Returns
    -------
    dict
        統計情報 (games, positions, elapsed_sec)
    """
    input_path = Path(input_file)
    if not input_path.exists():
        print(f"Error: input file not found: {input_file}", file=sys.stderr)
        return {"games": 0, "positions": 0, "elapsed_sec": 0.0}

    lines = [
        l.strip()
        for l in input_path.read_text(encoding="utf-8").splitlines()
        if l.strip() and not l.strip().startswith("#")
    ]

    total_games = len(lines)
    total_positions = 0
    start_time = time.time()

    with open(output_file, "w", encoding="utf-8") as out:
        for game_idx, line in enumerate(lines):
            base_position, moves = _parse_game_line(line)
            if not base_position:
                continue

            prev_features: Optional[Dict[str, Any]] = None

            for ply in range(0, len(moves) + 1, sample_interval):
                # 初手から ply 手目までの指し手で局面を構成
                applied_moves = moves[:ply]
                if applied_moves:
                    sfen = base_position + " moves " + " ".join(applied_moves)
                else:
                    sfen = base_position

                # この局面での指し手 (次の手)
                current_move = moves[ply] if ply < len(moves) else None

                try:
                    features = extract_position_features(
                        sfen,
                        move=current_move,
                        ply=ply,
                        prev_features=prev_features,
                    )
                except Exception as e:
                    print(
                        f"  Warning: game {game_idx + 1}, ply {ply}: {e}",
                        file=sys.stderr,
                    )
                    continue

                record = {
                    "game_index": game_idx,
                    "ply": ply,
                    "sfen": sfen,
                    "move": current_move,
                    **features,
                }
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
                total_positions += 1
                prev_features = features

            # 進捗表示
            if (game_idx + 1) % 10 == 0 or game_idx + 1 == total_games:
                elapsed = time.time() - start_time
                print(
                    f"\r  [{game_idx + 1}/{total_games}] "
                    f"{total_positions} positions extracted "
                    f"({elapsed:.1f}s)",
                    end="",
                    flush=True,
                )

    elapsed = time.time() - start_time
    print()  # 改行

    stats = {
        "games": total_games,
        "positions": total_positions,
        "elapsed_sec": round(elapsed, 2),
    }
    print(
        f"Done: {stats['games']} games, "
        f"{stats['positions']} positions, "
        f"{stats['elapsed_sec']}s"
    )
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(
        description="USI棋譜から特徴量をバッチ抽出してJSONLに保存"
    )
    parser.add_argument("input", help="入力ファイル (1行1棋譜のUSIリスト)")
    parser.add_argument("output", help="出力ファイル (JSONL)")
    parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="サンプリング間隔 (手数, default: 5)",
    )
    args = parser.parse_args()
    batch_extract(args.input, args.output, sample_interval=args.interval)


if __name__ == "__main__":
    main()
