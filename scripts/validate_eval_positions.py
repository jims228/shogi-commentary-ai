"""scripts/validate_eval_positions.py

eval_set / real_positions JSON の局面整合性を検証する.

検証項目:
  1. sfen が python-shogi で読めるか
  2. user_move がその局面で合法か
  3. prev_moves (sfen内 moves 部分) から局面を再構成できるか
  4. ply が一致するか (sfen 末尾の手数 vs record.ply)
  5. candidates の各手がその局面で合法か

使い方:
  python scripts/validate_eval_positions.py data/human_eval/eval_set_*.json
  python scripts/validate_eval_positions.py data/real_positions_*.json --verbose
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import shogi
except ImportError:
    print("ERROR: python-shogi required.  pip install python-shogi")
    sys.exit(1)

STARTPOS_SFEN = "lnsgkgsnl/1r5b1/ppppppppp/9/9/9/PPPPPPPPP/1B5R1/LNSGKGSNL b - 1"


# ---------------------------------------------------------------------------
# SFEN parsing helpers
# ---------------------------------------------------------------------------

def parse_position_cmd(position_cmd: str) -> Tuple[str, List[str]]:
    """USI 'position' コマンド文字列 → (board_sfen, moves_list).

    対応形式:
      "position startpos"
      "position startpos moves 7g7f 3c3d ..."
      "position sfen <sfen> [moves ...]"
      "<bare sfen>"  (position prefix なし)
    """
    s = position_cmd.strip()

    # Strip leading "position" keyword
    if s.startswith("position "):
        s = s[len("position "):]

    if s.startswith("startpos"):
        rest = s[len("startpos"):].strip()
        base_sfen = STARTPOS_SFEN
    elif s.startswith("sfen "):
        rest = s[len("sfen "):]
        # sfen部分と moves部分を分離
        if " moves " in rest:
            sfen_part, moves_part = rest.split(" moves ", 1)
            base_sfen = sfen_part.strip()
            return base_sfen, moves_part.strip().split()
        else:
            base_sfen = rest.strip()
            return base_sfen, []
    else:
        # bare sfen (position prefix なし)
        if " moves " in s:
            sfen_part, moves_part = s.split(" moves ", 1)
            base_sfen = sfen_part.strip()
            return base_sfen, moves_part.strip().split()
        return s.strip(), []

    # startpos case: check for moves
    if rest.startswith("moves "):
        moves = rest[len("moves "):].strip().split()
        return base_sfen, moves
    return base_sfen, []


def board_from_sfen(sfen: str) -> Optional[shogi.Board]:
    """SFEN文字列からBoardを生成. 失敗時 None."""
    try:
        return shogi.Board(sfen)
    except Exception:
        return None


def replay_moves(base_sfen: str, moves: List[str]) -> Tuple[Optional[shogi.Board], Optional[str]]:
    """base_sfen から moves を順に適用. 途中で不正手があれば (None, エラー内容) を返す."""
    board = board_from_sfen(base_sfen)
    if board is None:
        return None, f"base sfen parse failed: {base_sfen}"
    for i, mv_str in enumerate(moves):
        try:
            mv = shogi.Move.from_usi(mv_str)
        except Exception:
            return None, f"move #{i+1} parse failed: {mv_str}"
        if mv not in board.legal_moves:
            return None, f"move #{i+1} illegal: {mv_str} (legal: {len(list(board.legal_moves))} moves)"
        board.push(mv)
    return board, None


def count_ply_from_sfen(base_sfen: str, num_moves: int) -> int:
    """base_sfen の手数番号 + 適用した手数 = 局面の手数."""
    parts = base_sfen.split()
    # SFEN format: board turn hand move_number
    if len(parts) >= 4:
        try:
            start_move_num = int(parts[3])
        except ValueError:
            start_move_num = 1
    else:
        start_move_num = 1
    return start_move_num + num_moves - 1  # move_number is 1-based ply


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class ValidationResult:
    def __init__(self, record_id: str):
        self.record_id = record_id
        self.errors: List[str] = []
        self.warnings: List[str] = []

    @property
    def valid(self) -> bool:
        return len(self.errors) == 0

    def add_error(self, msg: str):
        self.errors.append(msg)

    def add_warning(self, msg: str):
        self.warnings.append(msg)

    def summary(self) -> str:
        status = "VALID" if self.valid else "INVALID"
        parts = [f"[{status}] {self.record_id}"]
        for e in self.errors:
            parts.append(f"  ERROR: {e}")
        for w in self.warnings:
            parts.append(f"  WARN:  {w}")
        return "\n".join(parts)


def validate_record(rec: Dict[str, Any]) -> ValidationResult:
    """1レコードを検証."""
    rid = rec.get("id", rec.get("name", "unknown"))
    result = ValidationResult(rid)

    sfen_cmd = rec.get("sfen", "")
    if not sfen_cmd:
        result.add_error("sfen is empty")
        return result

    # --- 1) SFEN parse ---
    base_sfen, moves_in_sfen = parse_position_cmd(sfen_cmd)

    board = board_from_sfen(base_sfen)
    if board is None:
        result.add_error(f"base sfen unparseable: {base_sfen}")
        return result

    # --- 2) Replay moves in SFEN ---
    if moves_in_sfen:
        final_board, err = replay_moves(base_sfen, moves_in_sfen)
        if err:
            result.add_error(f"sfen replay failed: {err}")
            return result
    else:
        final_board = board

    # --- 3) ply check ---
    record_ply = rec.get("ply", 0)
    if moves_in_sfen:
        # sfen末尾の手数 = base_sfenのmove_number. 実際のplyはmove_number + len(moves) - 1
        expected_ply = count_ply_from_sfen(base_sfen, len(moves_in_sfen))
    else:
        # moves なし → sfen の move_number がそのままply
        parts = base_sfen.split()
        expected_ply = int(parts[3]) if len(parts) >= 4 else 1

    if record_ply != expected_ply:
        # Allow off-by-one since conventions vary
        diff = abs(record_ply - expected_ply)
        if diff == 1:
            result.add_warning(f"ply off-by-one: record={record_ply}, sfen_derived={expected_ply}")
        else:
            result.add_error(f"ply mismatch: record={record_ply}, sfen_derived={expected_ply}")

    # --- 4) user_move legality ---
    user_move_str = rec.get("user_move")
    if user_move_str:
        try:
            um = shogi.Move.from_usi(user_move_str)
            if um not in final_board.legal_moves:
                legal_strs = sorted(str(m) for m in final_board.legal_moves)
                result.add_error(
                    f"user_move '{user_move_str}' is illegal at this position "
                    f"(turn={'b' if final_board.turn == shogi.BLACK else 'w'}, "
                    f"{len(legal_strs)} legal moves)"
                )
            # Also check: does the sfen already include this move in its moves list?
            if moves_in_sfen and user_move_str == moves_in_sfen[-1]:
                result.add_warning("user_move is the last move in sfen (already applied)")
        except Exception as e:
            result.add_error(f"user_move parse error: {user_move_str} ({e})")
    else:
        result.add_warning("user_move is null")

    # --- 5) candidates legality ---
    candidates = rec.get("candidates", [])
    if candidates:
        for i, cand in enumerate(candidates):
            mv_str = cand.get("move", "")
            if not mv_str:
                result.add_warning(f"candidate #{i+1} has no move")
                continue
            try:
                cm = shogi.Move.from_usi(mv_str)
                if cm not in final_board.legal_moves:
                    result.add_error(f"candidate #{i+1} '{mv_str}' is illegal")
            except Exception as e:
                result.add_error(f"candidate #{i+1} parse error: {mv_str} ({e})")

    # --- 6) prev_moves field (if present) ---
    prev_moves = rec.get("prev_moves", [])
    if prev_moves and moves_in_sfen:
        # prev_moves should be the tail of moves_in_sfen
        tail = moves_in_sfen[-len(prev_moves):]
        if prev_moves != tail:
            result.add_warning(
                f"prev_moves doesn't match sfen tail: "
                f"prev_moves={prev_moves}, sfen_tail={tail}"
            )

    return result


# ---------------------------------------------------------------------------
# File loading
# ---------------------------------------------------------------------------

def load_records(path: str) -> List[Dict[str, Any]]:
    """JSONファイルからレコード一覧を読み込む."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # eval_set format: {"records": [...]}
    if isinstance(data, dict) and "records" in data:
        return data["records"]
    # real_positions / comparison format: [...]
    if isinstance(data, list):
        return data
    # comparison format: {"positions": [...]}
    if isinstance(data, dict) and "positions" in data:
        return data["positions"]
    return []


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Validate eval/benchmark position integrity")
    parser.add_argument("files", nargs="+", help="JSON files to validate")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show all results (not just invalid)")
    parser.add_argument("--json-out", "-o", help="Output validation results as JSON")
    args = parser.parse_args()

    all_results: List[Dict[str, Any]] = []
    total = 0
    valid_count = 0
    invalid_count = 0
    error_types: Dict[str, int] = {}

    for fpath in args.files:
        print(f"\n{'='*60}")
        print(f"File: {fpath}")
        print(f"{'='*60}")

        records = load_records(fpath)
        print(f"  Records: {len(records)}")

        for rec in records:
            total += 1
            vr = validate_record(rec)

            if vr.valid:
                valid_count += 1
            else:
                invalid_count += 1

            for e in vr.errors:
                # Categorize
                if "unparseable" in e:
                    cat = "sfen_parse"
                elif "replay failed" in e:
                    cat = "sfen_replay"
                elif "ply mismatch" in e:
                    cat = "ply_mismatch"
                elif "user_move" in e and "illegal" in e:
                    cat = "user_move_illegal"
                elif "user_move" in e and "parse" in e:
                    cat = "user_move_parse"
                elif "candidate" in e and "illegal" in e:
                    cat = "candidate_illegal"
                else:
                    cat = "other"
                error_types[cat] = error_types.get(cat, 0) + 1

            if args.verbose or not vr.valid:
                print(vr.summary())

            all_results.append({
                "id": vr.record_id,
                "valid": vr.valid,
                "errors": vr.errors,
                "warnings": vr.warnings,
            })

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"  Total:   {total}")
    print(f"  Valid:   {valid_count}")
    print(f"  Invalid: {invalid_count}")
    if error_types:
        print("  Error breakdown:")
        for cat, cnt in sorted(error_types.items(), key=lambda x: -x[1]):
            print(f"    {cat}: {cnt}")

    if args.json_out:
        out = {
            "total": total,
            "valid": valid_count,
            "invalid": invalid_count,
            "error_types": error_types,
            "results": all_results,
        }
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"\nJSON output: {args.json_out}")


if __name__ == "__main__":
    main()
