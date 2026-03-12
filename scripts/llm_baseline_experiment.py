#!/usr/bin/env python3
"""LLM-only baseline experiment.

game_01.kif から奇数手目の局面 (1, 3, 5, ..., 19) を抽出し、
Gemini 2.5-flash-lite に直接プロンプトを投げて解説を生成する。
ML パイプラインや特徴量抽出は一切使わない。

Usage:
    python3 scripts/llm_baseline_experiment.py
    python3 scripts/llm_baseline_experiment.py --dry-run   # API呼び出しなし
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.kif_parser import parse_kif_file, moves_to_usi


# ---------------------------------------------------------------------------
# Shogi board helpers (standalone — no ML pipeline imports)
# ---------------------------------------------------------------------------

# Standard SFEN for shogi startpos
_STARTPOS_SFEN = "lnsgkgsnl/1r5b1/ppppppppp/9/9/9/PPPPPPPPP/1B5R1/LNSGKGSNL b - 1"

# Piece order for SFEN hand notation
_HAND_ORDER = ["R", "B", "G", "S", "N", "L", "P"]

# Demoted piece: promoted → base kind
_DEMOTE = {"+P": "P", "+L": "L", "+N": "N", "+S": "S", "+B": "B", "+R": "R"}


def _parse_sfen_board(board_str: str) -> List[List[Optional[str]]]:
    """Parse SFEN board string into 9x9 grid. board[y][x], y=0 top, x=0 file-9."""
    board: List[List[Optional[str]]] = [[None] * 9 for _ in range(9)]
    for y, row in enumerate(board_str.split("/")):
        x = 0
        i = 0
        while i < len(row):
            ch = row[i]
            if ch.isdigit():
                x += int(ch)
                i += 1
            elif ch == "+":
                board[y][x] = "+" + row[i + 1]
                x += 1
                i += 2
            else:
                board[y][x] = ch
                x += 1
                i += 1
    return board


def _board_to_sfen_str(board: List[List[Optional[str]]]) -> str:
    """Convert 9x9 board grid to SFEN board string."""
    rows = []
    for y in range(9):
        row = ""
        empty = 0
        for x in range(9):
            p = board[y][x]
            if p is None:
                empty += 1
            else:
                if empty:
                    row += str(empty)
                    empty = 0
                row += p
        if empty:
            row += str(empty)
        rows.append(row)
    return "/".join(rows)


def _hands_to_sfen_str(hands: Dict[str, Dict[str, int]]) -> str:
    """Convert hands dict to SFEN hand string."""
    parts = []
    for piece in _HAND_ORDER:
        cnt = hands["b"].get(piece, 0)
        if cnt == 1:
            parts.append(piece)
        elif cnt > 1:
            parts.append(str(cnt) + piece)
    for piece in _HAND_ORDER:
        cnt = hands["w"].get(piece, 0)
        lp = piece.lower()
        if cnt == 1:
            parts.append(lp)
        elif cnt > 1:
            parts.append(str(cnt) + lp)
    return "".join(parts) if parts else "-"


def _sq_to_xy(sq: str) -> Tuple[int, int]:
    """USI square "7f" → (x, y). file 1-9 → x=8..0, rank a-i → y=0..8."""
    x = 9 - int(sq[0])
    y = ord(sq[1]) - ord("a")
    return x, y


def _piece_side(piece: str) -> str:
    ch = piece[-1] if piece.startswith("+") else piece[0]
    return "b" if ch.isupper() else "w"


def _base_kind(piece: str) -> str:
    """Demote promoted piece to base uppercase kind."""
    if piece.startswith("+"):
        return piece[1].upper()
    return piece.upper()


def apply_move_with_hands(
    board: List[List[Optional[str]]],
    hands: Dict[str, Dict[str, int]],
    move: str,
    turn: str,
) -> Tuple[List[List[Optional[str]]], Dict[str, Dict[str, int]]]:
    """Apply a USI move and update hands. Returns (new_board, new_hands)."""
    board = [row[:] for row in board]
    hands = {"b": dict(hands["b"]), "w": dict(hands["w"])}

    if "*" in move:
        # Drop
        piece_letter, dst = move.split("*")
        dx, dy = _sq_to_xy(dst)
        placed = piece_letter.upper() if turn == "b" else piece_letter.lower()
        board[dy][dx] = placed
        kind = piece_letter.upper()
        hands[turn][kind] = hands[turn].get(kind, 0) - 1
        return board, hands

    src = move[:2]
    dst = move[2:4]
    promote = move.endswith("+")
    sx, sy = _sq_to_xy(src)
    dx, dy = _sq_to_xy(dst)

    piece = board[sy][sx]
    board[sy][sx] = None

    captured = board[dy][dx]
    if captured is not None:
        kind = _base_kind(captured)
        hands[turn][kind] = hands[turn].get(kind, 0) + 1

    if piece is not None and promote:
        piece = "+" + piece if not piece.startswith("+") else piece

    board[dy][dx] = piece
    return board, hands


def build_sfen_sequence(usi_moves: List[str]) -> List[Dict[str, Any]]:
    """Apply moves one by one from startpos and return SFEN + last_move for each ply."""
    sfen_parts = _STARTPOS_SFEN.split()
    board = _parse_sfen_board(sfen_parts[0])
    # Parse starting hands from SFEN (startpos has no pieces in hand)
    hands: Dict[str, Dict[str, int]] = {"b": {}, "w": {}}

    results = []
    turn = "b"
    move_number = 1

    # ply 0 = starting position (before any moves)
    results.append({
        "ply": 0,
        "sfen": f"{_board_to_sfen_str(board)} {turn} {_hands_to_sfen_str(hands)} {move_number}",
        "last_move": None,
        "turn": turn,
    })

    for i, mv in enumerate(usi_moves):
        board, hands = apply_move_with_hands(board, hands, mv, turn)
        next_turn = "w" if turn == "b" else "b"
        if turn == "w":
            move_number += 1
        ply = i + 1
        results.append({
            "ply": ply,
            "last_move": mv,
            "sfen": f"{_board_to_sfen_str(board)} {next_turn} {_hands_to_sfen_str(hands)} {move_number}",
            "turn": next_turn,
        })
        turn = next_turn

    return results


# ---------------------------------------------------------------------------
# Gemini prompt + call
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """あなたは将棋の解説者です。指定された局面について、以下の3点を80文字以内で簡潔に解説してください。
1. 局面の状況（駒の配置、形勢）
2. 直前の手の意図
3. 相手の有力な対応策"""


def _build_prompt(sfen: str, last_move: Optional[str], ply: int) -> str:
    turn_str = "先手（▲）" if (ply % 2 == 1) else "後手（△）"
    move_str = f"直前の手: {last_move}" if last_move else "開始局面"
    return (
        f"局面 (SFEN): {sfen}\n"
        f"手数: {ply}手目 {turn_str}番\n"
        f"{move_str}\n\n"
        "この局面を80文字以内で解説してください（状況・意図・対応策の3点）:"
    )


def call_gemini(prompt: str) -> str:
    """Call Gemini 2.5-flash-lite with thinking_budget=0."""
    try:
        import google.generativeai as genai
        from backend.api.utils.gemini_client import ensure_configured
    except ImportError as e:
        return f"[import error: {e}]"

    api_key = ensure_configured()
    if not api_key:
        return "[GEMINI_API_KEY not set]"

    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash-lite",
        system_instruction=_SYSTEM_PROMPT,
    )

    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=200,
                temperature=0.7,
            ),
        )
        return response.text.strip()
    except Exception as e:
        return f"[API error: {e}]"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="LLM baseline experiment on game_01.kif")
    parser.add_argument("--dry-run", action="store_true", help="Skip API calls, use placeholder commentary")
    parser.add_argument(
        "--kif",
        default=str(_PROJECT_ROOT / "data" / "games" / "real_kif" / "game_01.kif"),
        help="Path to KIF file",
    )
    parser.add_argument(
        "--output",
        default=str(_PROJECT_ROOT / "data" / "human_eval" / "llm_baseline_game01.json"),
        help="Output JSON path",
    )
    args = parser.parse_args()

    # 1. Parse KIF
    print(f"[1/4] Parsing KIF: {args.kif}")
    parsed = parse_kif_file(args.kif)
    usi_moves = moves_to_usi(parsed)
    valid_moves = [m for m in usi_moves if m is not None]
    print(f"      {len(parsed['moves'])} moves parsed, {len(valid_moves)} valid USI moves")

    # 2. Build SFEN sequence
    print("[2/4] Building SFEN positions...")
    sfen_seq = build_sfen_sequence(valid_moves)

    # Select odd-numbered plies: 1, 3, 5, 7, 9, 11, 13, 15, 17, 19
    target_plies = list(range(1, 20, 2))  # [1, 3, 5, 7, 9, 11, 13, 15, 17, 19]
    positions = [s for s in sfen_seq if s["ply"] in target_plies]
    print(f"      Extracted {len(positions)} positions at plies: {target_plies}")

    # 3. Generate commentary
    print(f"[3/4] Generating commentary {'(DRY RUN)' if args.dry_run else 'via Gemini API'}...")
    results = []
    for pos in positions:
        ply = pos["ply"]
        sfen = pos["sfen"]
        last_move = pos["last_move"]
        prompt = _build_prompt(sfen, last_move, ply)

        if args.dry_run:
            commentary = f"[dry-run] 手数{ply}: {last_move} の後の局面。解説省略。"
        else:
            commentary = call_gemini(prompt)

        move_number = (ply + 1) // 2
        entry = {
            "move_number": move_number,
            "ply": ply,
            "sfen": sfen,
            "last_move": last_move,
            "commentary": commentary,
            "model": "dry-run" if args.dry_run else "gemini-2.5-flash-lite",
        }
        results.append(entry)

        print(f"\n  --- 手数 {ply} (move {move_number}) last_move={last_move} ---")
        print(f"  SFEN: {sfen}")
        print(f"  解説: {commentary}")

    # 4. Save
    print(f"\n[4/4] Saving to {args.output}")
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    output_data = {
        "game_file": args.kif,
        "model": "dry-run" if args.dry_run else "gemini-2.5-flash-lite",
        "system_prompt": _SYSTEM_PROMPT,
        "positions": results,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    print(f"      Saved {len(results)} records.")


if __name__ == "__main__":
    main()
