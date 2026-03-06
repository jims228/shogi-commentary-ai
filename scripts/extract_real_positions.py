"""scripts/extract_real_positions.py

training_logs / batch_commentary から実戦由来の局面を抽出し、
python-shogi で合法性を検証済みのベンチマークセットを生成する.

ポイント:
  - 全レコードは python-shogi でリプレイ検証済み
  - user_move = SFEN 手順の最終手 (局面はその直前の状態)
  - candidates = その局面での合法手からサンプリング (ダミーではなく実際の合法手)
  - prev_moves = SFEN 手順の末尾 N 手

使い方:
  python scripts/extract_real_positions.py
  python scripts/extract_real_positions.py --count 20 --source training
  python scripts/extract_real_positions.py --count 50 --source all

出力: data/real_positions_<timestamp>.json
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import shogi
except ImportError:
    print("ERROR: python-shogi required.  pip install python-shogi")
    sys.exit(1)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

STARTPOS_SFEN = "lnsgkgsnl/1r5b1/ppppppppp/9/9/9/PPPPPPPPP/1B5R1/LNSGKGSNL b - 1"


# ---------------------------------------------------------------------------
# SFEN replay with validation
# ---------------------------------------------------------------------------

def parse_and_replay(sfen_cmd: str) -> Optional[Dict[str, Any]]:
    """SFEN コマンドをリプレイし、検証済みの局面情報を返す.

    戻り値: {
      "base_sfen": str,        # moves適用前のSFEN
      "moves": [str, ...],     # 全手順
      "board_before": Board,   # 最終手の直前の盤面
      "board_after": Board,    # 全手適用後の盤面
      "user_move": str,        # 最終手 (USI)
      "ply": int,              # 手数
    } or None (検証失敗時)
    """
    s = sfen_cmd.strip()
    if s.startswith("position "):
        s = s[len("position "):]

    if s.startswith("startpos"):
        base_sfen = STARTPOS_SFEN
        rest = s[len("startpos"):].strip()
        moves = rest[len("moves "):].split() if rest.startswith("moves ") else []
    elif s.startswith("sfen "):
        rest = s[len("sfen "):]
        if " moves " in rest:
            sfen_part, moves_part = rest.split(" moves ", 1)
            base_sfen = sfen_part.strip()
            moves = moves_part.strip().split()
        else:
            base_sfen = rest.strip()
            moves = []
    else:
        return None

    if len(moves) < 2:
        return None  # 最低2手ないと user_move + board_before を構成できない

    try:
        board = shogi.Board(base_sfen)
    except Exception:
        return None

    # 最終手の直前までリプレイ
    for mv_str in moves[:-1]:
        try:
            mv = shogi.Move.from_usi(mv_str)
            if mv not in board.legal_moves:
                return None
            board.push(mv)
        except Exception:
            return None

    board_before = copy.deepcopy(board)

    # 最終手を適用
    user_move_str = moves[-1]
    try:
        um = shogi.Move.from_usi(user_move_str)
        if um not in board.legal_moves:
            return None
        board.push(um)
    except Exception:
        return None

    # ply計算: startpos (move_number=1) からの手数 = len(moves)
    # sfen の move_number は開始手数を示すが、moves を全て適用した手数を返す
    parts = base_sfen.split()
    base_move_num = int(parts[3]) if len(parts) >= 4 else 1
    # board_before の手数 (user_move 適用前) = base_move_num + len(moves) - 2
    # ただし sfen が startpos (move_number=1) の場合、moves の数がそのまま手数
    ply = base_move_num + len(moves) - 2

    return {
        "base_sfen": base_sfen,
        "moves": moves,
        "board_before": board_before,
        "board_after": board,
        "user_move": user_move_str,
        "ply": ply,
    }


def pick_candidates(
    board: shogi.Board,
    user_move: str,
    rng: random.Random,
    n: int = 3,
) -> List[Dict[str, str]]:
    """board の合法手から n 手をサンプリング.

    user_move は必ず含める. 残りはランダム.
    """
    all_legal = [str(m) for m in board.legal_moves]
    if not all_legal:
        return []

    candidates = []
    # user_move を最初に入れる
    if user_move in all_legal:
        candidates.append(user_move)
        remaining = [m for m in all_legal if m != user_move]
    else:
        remaining = all_legal

    rng.shuffle(remaining)
    for m in remaining:
        if len(candidates) >= n:
            break
        candidates.append(m)

    # shuffle して順番をランダムにする (A/Bテスト用)
    rng.shuffle(candidates)
    return [{"move": m} for m in candidates]


# ---------------------------------------------------------------------------
# Data source loaders
# ---------------------------------------------------------------------------

def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    records = []
    if not path.exists():
        return records
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return records


def load_training_logs() -> List[Dict[str, Any]]:
    """training_logs/explanations_*.jsonl から sfen+ply を抽出."""
    logs_dir = _PROJECT_ROOT / "data" / "training_logs"
    positions = []
    for p in sorted(logs_dir.glob("explanations_*.jsonl")):
        for rec in _load_jsonl(p):
            inp = rec.get("input", {})
            sfen = inp.get("sfen", "")
            ply = inp.get("ply", 0)
            features = inp.get("features", {})
            if sfen and ply >= 5:
                positions.append({
                    "sfen_cmd": sfen,
                    "ply_hint": ply,
                    "phase": features.get("phase", "unknown"),
                    "source": "training_log",
                })
    return positions


def load_batch_commentary() -> List[Dict[str, Any]]:
    """batch_commentary.jsonl から sfen+move を抽出.

    batch_commentary の場合、sfen は「この手を指す前の局面」で
    move が「次に指された手」. sfen の moves の末尾に move を足すと
    完全な手順になる.
    """
    path = _PROJECT_ROOT / "data" / "batch_commentary" / "batch_commentary.jsonl"
    positions = []
    for rec in _load_jsonl(path):
        sfen = rec.get("sfen", "")
        move = rec.get("move")
        ply = rec.get("ply", 0)
        if sfen and move and ply >= 5:
            # sfen + " " + move で手順を完成させる
            if " moves " in sfen:
                full_sfen = sfen + " " + move
            else:
                full_sfen = sfen + " moves " + move
            positions.append({
                "sfen_cmd": full_sfen,
                "ply_hint": ply + 1,
                "phase": _guess_phase(ply),
                "source": "batch_commentary",
            })
    return positions


def _guess_phase(ply: int) -> str:
    if ply <= 30:
        return "opening"
    elif ply <= 80:
        return "midgame"
    return "endgame"


# ---------------------------------------------------------------------------
# Deduplication and balancing
# ---------------------------------------------------------------------------

def _sfen_hash(sfen: str) -> str:
    return hashlib.md5(sfen.encode()).hexdigest()[:16]


def deduplicate(positions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    result = []
    for pos in positions:
        h = _sfen_hash(pos["sfen_cmd"])
        if h not in seen:
            seen.add(h)
            result.append(pos)
    return result


def balanced_sample(
    positions: List[Dict[str, Any]],
    count: int,
    seed: int = 42,
) -> List[Dict[str, Any]]:
    """序盤/中盤/終盤をなるべく均等にサンプリング."""
    by_phase: Dict[str, List[Dict[str, Any]]] = {
        "opening": [], "midgame": [], "endgame": [],
    }
    for pos in positions:
        phase = pos.get("phase", "unknown")
        if phase not in by_phase:
            phase = _guess_phase(pos.get("ply_hint", 0))
        by_phase[phase].append(pos)

    rng = random.Random(seed)
    per_phase = count // 3
    remainder = count - per_phase * 3

    sampled: List[Dict[str, Any]] = []
    for i, phase in enumerate(["opening", "midgame", "endgame"]):
        n = per_phase + (1 if i < remainder else 0)
        pool = by_phase[phase]
        rng.shuffle(pool)
        sampled.extend(pool[:n])

    return sampled


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def build_validated_positions(
    raw_positions: List[Dict[str, Any]],
    seed: int = 42,
) -> List[Dict[str, Any]]:
    """raw positions → validated benchmark records."""
    rng = random.Random(seed)
    output = []
    skipped = 0

    for pos in raw_positions:
        result = parse_and_replay(pos["sfen_cmd"])
        if result is None:
            skipped += 1
            continue

        prev_moves = result["moves"][-5:] if len(result["moves"]) > 5 else result["moves"]
        candidates = pick_candidates(result["board_before"], result["user_move"], rng)

        # build the sfen_cmd without the last move (board_before state)
        # so that user_move is separate and can be validated against the position
        if len(result["moves"]) > 1:
            moves_before = result["moves"][:-1]
            sfen_before_cmd = f"position sfen {result['base_sfen']} moves {' '.join(moves_before)}"
        else:
            sfen_before_cmd = f"position sfen {result['base_sfen']}"

        phase = pos.get("phase", _guess_phase(result["ply"]))

        record = {
            "name": f"{phase}_{len(output)+1:03d}_{pos['source']}",
            "sfen": sfen_before_cmd,
            "ply": result["ply"],
            "user_move": result["user_move"],
            "prev_moves": prev_moves[:-1],  # moves before user_move
            "candidates": candidates,
            "phase": phase,
            "source": pos["source"],
        }
        output.append(record)

    if skipped:
        print(f"  [build] Skipped {skipped} records (replay failed)")

    return output


def main():
    parser = argparse.ArgumentParser(
        description="Extract validated real-game positions for benchmarking"
    )
    parser.add_argument("--count", "-n", type=int, default=40,
                        help="抽出局面数 (default: 40)")
    parser.add_argument("--source", "-s", default="all",
                        choices=["all", "training", "batch"],
                        help="データソース (default: all)")
    parser.add_argument("--seed", type=int, default=42,
                        help="乱数シード (default: 42)")
    parser.add_argument("--output", "-o", default=None,
                        help="出力パス")
    args = parser.parse_args()

    # Load sources
    all_positions: List[Dict[str, Any]] = []

    if args.source in ("all", "training"):
        training = load_training_logs()
        all_positions.extend(training)
        print(f"[extract] {len(training)} from training_logs")

    if args.source in ("all", "batch"):
        batch = load_batch_commentary()
        all_positions.extend(batch)
        print(f"[extract] {len(batch)} from batch_commentary")

    print(f"[extract] Total raw: {len(all_positions)}")

    deduped = deduplicate(all_positions)
    print(f"[extract] After dedup: {len(deduped)}")

    sampled = balanced_sample(deduped, args.count, seed=args.seed)
    print(f"[extract] Sampled: {len(sampled)}")

    # Phase distribution
    phase_dist: Dict[str, int] = {}
    for p in sampled:
        phase_dist[p["phase"]] = phase_dist.get(p["phase"], 0) + 1
    print(f"[extract] Phase distribution: {phase_dist}")

    # Validate and build
    benchmark = build_validated_positions(sampled, seed=args.seed)
    print(f"[extract] Validated records: {len(benchmark)}")

    # Output
    if args.output:
        out_path = Path(args.output)
    else:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        out_path = _PROJECT_ROOT / "data" / f"real_positions_{ts}.json"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(benchmark, f, ensure_ascii=False, indent=2)

    print(f"[extract] Output: {out_path}")

    # Run validation
    print(f"\n[extract] Running validation on output...")
    from scripts.validate_eval_positions import validate_record, load_records
    records = load_records(str(out_path))
    valid = sum(1 for r in records if validate_record(r).valid)
    print(f"[extract] Validation: {valid}/{len(records)} valid")


if __name__ == "__main__":
    main()
