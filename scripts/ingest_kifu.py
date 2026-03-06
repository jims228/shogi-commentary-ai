"""scripts/ingest_kifu.py

KIF 棋譜ファイルから整合性保証付きの評価用局面セットを生成する.

パイプライン:
  1. KIF → parse_kif() → USI moves
  2. python-shogi で全手リプレイ検証
  3. 各 ply で sfen_before / user_move / prev_moves を一貫生成
  4. (optional) エンジン解析で candidates / bestmove / score_cp を取得
  5. validate_eval_positions で最終検証
  6. eval_set JSON として出力

使い方:
  # KIF から局面抽出のみ (エンジンなし)
  python scripts/ingest_kifu.py data/games/game01.kif

  # エンジン解析付き
  python scripts/ingest_kifu.py data/games/game01.kif --engine

  # 複数ファイル + サンプリング
  python scripts/ingest_kifu.py data/games/*.kif --sample 20

  # eval_set として直接出力
  python scripts/ingest_kifu.py data/games/*.kif --eval-set --sample 15

出力: data/ingested/positions_<timestamp>.json
       or data/human_eval/eval_set_<timestamp>.json (--eval-set)
"""
from __future__ import annotations

import argparse
import copy
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import shogi
except ImportError:
    print("ERROR: python-shogi required.  pip install python-shogi")
    sys.exit(1)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.kif_parser import parse_kif, parse_kif_file, moves_to_usi
from scripts.validate_eval_positions import validate_record

STARTPOS_SFEN = "lnsgkgsnl/1r5b1/ppppppppp/9/9/9/PPPPPPPPP/1B5R1/LNSGKGSNL b - 1"


# ---------------------------------------------------------------------------
# Step 1-2: KIF → USI moves → python-shogi replay
# ---------------------------------------------------------------------------

def replay_game(usi_moves: List[str]) -> Optional[List[Dict[str, Any]]]:
    """USI手順を python-shogi でリプレイし、各 ply の局面情報を返す.

    Returns None if any move is illegal.
    Returns list of dicts, one per applied move:
      {
        "ply": int,              # 1-based
        "sfen_before": str,      # position sfen ... (user_move 適用前)
        "user_move": str,        # USI move
        "sfen_after": str,       # position sfen ... (user_move 適用後)
        "board_sfen": str,       # bare sfen at sfen_before
        "turn": str,             # "b" or "w"
        "legal_moves": [str],    # all legal moves at sfen_before
      }
    """
    board = shogi.Board()
    positions = []

    for i, mv_str in enumerate(usi_moves):
        # Validate move
        try:
            mv = shogi.Move.from_usi(mv_str)
        except Exception:
            print(f"  [replay] move #{i+1} parse error: {mv_str}")
            return None

        if mv not in board.legal_moves:
            print(f"  [replay] move #{i+1} illegal: {mv_str}")
            return None

        # Record position BEFORE this move
        board_sfen_before = board.sfen()
        legal_moves_before = [str(m) for m in board.legal_moves]

        # Build the full position command (startpos + moves up to here)
        if i == 0:
            sfen_before_cmd = "position startpos"
        else:
            sfen_before_cmd = "position startpos moves " + " ".join(usi_moves[:i])

        # Apply move
        board.push(mv)

        board_sfen_after = board.sfen()
        sfen_after_cmd = "position startpos moves " + " ".join(usi_moves[:i+1])

        positions.append({
            "ply": i,  # number of moves applied = position ply (matches sfen-derived ply)
            "sfen_before": sfen_before_cmd,
            "user_move": mv_str,
            "sfen_after": sfen_after_cmd,
            "board_sfen": board_sfen_before,
            "turn": "b" if (i % 2 == 0) else "w",
            "legal_moves": legal_moves_before,
        })

    return positions


# ---------------------------------------------------------------------------
# Step 3: Build position records with prev_moves & candidates
# ---------------------------------------------------------------------------

def build_position_records(
    positions: List[Dict[str, Any]],
    usi_moves: List[str],
    game_meta: Dict[str, str],
    rng: random.Random,
    n_candidates: int = 3,
) -> List[Dict[str, Any]]:
    """replay結果から eval 用レコードを組み立てる."""
    records = []

    for pos in positions:
        ply = pos["ply"]
        idx = ply  # ply == index into usi_moves (0-based)

        # prev_moves: up to 5 moves before this one
        start = max(0, idx - 5)
        prev_moves = usi_moves[start:idx]

        # candidates: sample from legal moves, always including user_move
        user_move = pos["user_move"]
        legal = pos["legal_moves"]

        candidates = _pick_candidates(legal, user_move, rng, n_candidates)

        # Game phase estimate
        if ply <= 30:
            phase = "opening"
        elif ply <= 80:
            phase = "midgame"
        else:
            phase = "endgame"

        sente = game_meta.get("sente", "")
        gote = game_meta.get("gote", "")
        event = game_meta.get("event", "")
        name_parts = []
        if event:
            name_parts.append(event)
        if sente and gote:
            name_parts.append(f"{sente} vs {gote}")
        name_parts.append(f"{ply}手目")
        name = " ".join(name_parts)

        record = {
            "name": name,
            "sfen": pos["sfen_before"],
            "ply": ply,
            "user_move": user_move,
            "prev_moves": prev_moves,
            "candidates": candidates,
            "phase": phase,
            "turn": pos["turn"],
            "source": game_meta.get("source_file", "unknown"),
        }
        records.append(record)

    return records


def _pick_candidates(
    legal_moves: List[str],
    user_move: str,
    rng: random.Random,
    n: int = 3,
) -> List[Dict[str, str]]:
    """legal_moves から n 手をサンプリング. user_move は必ず含む."""
    candidates = [user_move] if user_move in legal_moves else []
    remaining = [m for m in legal_moves if m != user_move]
    rng.shuffle(remaining)
    for m in remaining:
        if len(candidates) >= n:
            break
        candidates.append(m)
    rng.shuffle(candidates)
    return [{"move": m} for m in candidates]


# ---------------------------------------------------------------------------
# Step 4 (optional): Engine analysis
# ---------------------------------------------------------------------------

def enrich_with_engine(
    records: List[Dict[str, Any]],
    multipv: int = 3,
    nodes: int = 150000,
) -> List[Dict[str, Any]]:
    """エンジン解析で candidates にスコアを付与し、bestmove/pv を追加."""
    try:
        from backend.api.services.engine_analysis import EngineAnalysisService
    except ImportError:
        print("  [engine] engine_analysis import failed, skipping")
        return records

    enriched = []
    try:
        with EngineAnalysisService(nodes=nodes, multipv=multipv) as svc:
            for i, rec in enumerate(records):
                pos_cmd = rec["sfen"]
                if not pos_cmd.startswith("position"):
                    pos_cmd = f"position {pos_cmd}"

                result = svc.analyze_position(pos_cmd)

                if result.ok:
                    # Build candidates from engine multipv
                    engine_candidates = []
                    for mpv in result.multipv:
                        pv_str = mpv.get("pv", "")
                        first_move = pv_str.split()[0] if pv_str else ""
                        score = mpv.get("score", {})
                        score_cp = score.get("cp") if score.get("type") == "cp" else None
                        score_mate = score.get("mate") if score.get("type") == "mate" else None
                        if first_move:
                            engine_candidates.append({
                                "move": first_move,
                                "score_cp": score_cp,
                                "score_mate": score_mate,
                            })

                    # Ensure user_move is in candidates
                    user_in = any(c["move"] == rec["user_move"] for c in engine_candidates)
                    if not user_in:
                        engine_candidates.append({"move": rec["user_move"], "score_cp": None})

                    rec["candidates"] = engine_candidates
                    rec["bestmove"] = result.bestmove
                    rec["score_cp"] = result.score_cp
                    rec["score_mate"] = result.score_mate
                    rec["pv"] = result.pv

                    # delta_cp: difference between user_move and bestmove
                    if result.score_cp is not None and engine_candidates:
                        user_score = None
                        best_score = engine_candidates[0].get("score_cp")
                        for c in engine_candidates:
                            if c["move"] == rec["user_move"]:
                                user_score = c.get("score_cp")
                                break
                        if user_score is not None and best_score is not None:
                            rec["delta_cp"] = user_score - best_score
                        else:
                            rec["delta_cp"] = None
                    else:
                        rec["delta_cp"] = None

                enriched.append(rec)

                if (i + 1) % 10 == 0:
                    print(f"  [engine] {i+1}/{len(records)} analyzed")

        print(f"  [engine] {len(enriched)}/{len(records)} enriched")
    except Exception as e:
        print(f"  [engine] Error: {e}")
        print("  [engine] Returning records without engine analysis")
        return records

    return enriched


# ---------------------------------------------------------------------------
# Step 5: Validation gate
# ---------------------------------------------------------------------------

def validate_all(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """validate_eval_positions で全件検証し、valid のみ返す."""
    valid = []
    for rec in records:
        vr = validate_record(rec)
        if vr.valid:
            valid.append(rec)
        else:
            print(f"  [validate] DROPPED ply={rec.get('ply')}: {'; '.join(vr.errors)}")
    return valid


# ---------------------------------------------------------------------------
# Step 6: Output
# ---------------------------------------------------------------------------

def save_positions(records: List[Dict[str, Any]], out_path: Path) -> None:
    """positions JSON として保存."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"[output] {len(records)} records → {out_path}")


def save_eval_set(records: List[Dict[str, Any]], out_path: Path) -> None:
    """human eval 用 eval_set JSON として保存."""
    eval_records = []
    for i, rec in enumerate(records):
        er = {
            "id": f"eval_{i+1:03d}",
            "sfen": rec["sfen"],
            "ply": rec["ply"],
            "user_move": rec["user_move"],
            "name": rec.get("name", ""),
            "candidates": rec.get("candidates", []),
            "prev_moves": rec.get("prev_moves", []),
            "bestmove": rec.get("bestmove"),
            "score_cp": rec.get("score_cp"),
            "delta_cp": rec.get("delta_cp"),
            "phase": rec.get("phase", ""),
            "turn": rec.get("turn", ""),
            "source": rec.get("source", ""),
            # Human eval fields (blank)
            "legacy_explanation": "",
            "planner_explanation": "",
            "planner_plan_flow": "",
            "planner_plan_topic_keyword": "",
            "planner_plan_surface_reason": "",
            "planner_plan_deep_reason": "",
            "auto_legacy_score": None,
            "auto_planner_score": None,
            "is_fallback": False,
            "flow_score": None,
            "keyword_score": None,
            "depth_score": None,
            "readability_score": None,
            "preference": None,
            "notes": "",
        }
        eval_records.append(er)

    payload = {
        "version": "2.0",
        "created": datetime.now(timezone.utc).isoformat(),
        "total": len(eval_records),
        "scoring_guide": {
            "flow_score": "1=不自然 2=やや不自然 3=普通 4=自然 5=非常に自然",
            "keyword_score": "1=不適切 2=やや不適切 3=普通 4=適切 5=非常に適切",
            "depth_score": "1=浅い/無関係 2=やや浅い 3=普通 4=深い 5=非常に深い・洞察的",
            "readability_score": "1=読みにくい 2=やや読みにくい 3=普通 4=読みやすい 5=非常に読みやすい",
            "preference": "legacy=旧方式が良い / planner=プランナーが良い / tie=同等",
        },
        "records": eval_records,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"[output] eval_set ({len(eval_records)} records) → {out_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def process_kif_file(
    kif_path: Path,
    rng: random.Random,
    min_ply: int = 5,
    max_ply: int = 200,
) -> List[Dict[str, Any]]:
    """1つの KIF ファイルを処理して validated records を返す."""
    print(f"\n[ingest] {kif_path.name}")

    # Parse KIF
    try:
        parsed = parse_kif_file(kif_path)
    except Exception as e:
        print(f"  [parse] FAILED: {e}")
        return []

    usi_moves_raw = moves_to_usi(parsed)
    # Filter out None (unparseable moves)
    usi_moves: List[str] = []
    for m in usi_moves_raw:
        if m is None:
            print(f"  [parse] USI conversion failed at move #{len(usi_moves)+1}, truncating")
            break
        usi_moves.append(m)

    if len(usi_moves) < min_ply:
        print(f"  [parse] Too few moves ({len(usi_moves)}), skipping")
        return []

    print(f"  [parse] {len(usi_moves)} moves, header: {parsed['header'].get('sente', '?')} vs {parsed['header'].get('gote', '?')}")

    game_meta = {
        "sente": parsed["header"].get("sente", ""),
        "gote": parsed["header"].get("gote", ""),
        "event": parsed["header"].get("event", ""),
        "source_file": kif_path.name,
    }

    return _process_usi_moves(usi_moves, game_meta, rng, min_ply, max_ply)


def process_usi_file(
    usi_path: Path,
    rng: random.Random,
    min_ply: int = 5,
    max_ply: int = 200,
) -> List[Dict[str, Any]]:
    """USI moves ファイル (1行1棋譜, スペース区切り) を処理."""
    print(f"\n[ingest] {usi_path.name} (USI format)")
    all_records: List[Dict[str, Any]] = []

    with open(usi_path, "r") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Support "position startpos moves ..." format
            if line.startswith("position"):
                parts = line.split()
                if "moves" in parts:
                    idx = parts.index("moves")
                    usi_moves = parts[idx + 1:]
                else:
                    continue
            else:
                usi_moves = line.split()

            game_meta = {
                "sente": "",
                "gote": "",
                "event": "",
                "source_file": f"{usi_path.name}:{line_no}",
            }
            records = _process_usi_moves(usi_moves, game_meta, rng, min_ply, max_ply)
            all_records.extend(records)

    return all_records


def _process_usi_moves(
    usi_moves: List[str],
    game_meta: Dict[str, str],
    rng: random.Random,
    min_ply: int,
    max_ply: int,
) -> List[Dict[str, Any]]:
    """USI手順 → replay → build → validate の共通処理."""
    if len(usi_moves) < min_ply:
        print(f"  [parse] Too few moves ({len(usi_moves)}), skipping")
        return []

    # Replay with python-shogi validation
    positions = replay_game(usi_moves)
    if positions is None:
        print(f"  [replay] FAILED - illegal moves detected")
        return []

    print(f"  [replay] {len(positions)} positions validated")

    # Filter by ply range
    filtered = [p for p in positions if min_ply <= p["ply"] <= max_ply]

    # Build records
    records = build_position_records(filtered, usi_moves, game_meta, rng)
    print(f"  [build] {len(records)} records (ply {min_ply}-{max_ply})")

    # Validate
    valid = validate_all(records)
    print(f"  [validate] {len(valid)}/{len(records)} valid")

    return valid


def main():
    parser = argparse.ArgumentParser(
        description="KIF棋譜から整合性保証付き評価用局面セットを生成"
    )
    parser.add_argument("inputs", nargs="+", help="KIF ファイル (glob可)")
    parser.add_argument("--engine", action="store_true",
                        help="エンジン解析を実行")
    parser.add_argument("--multipv", type=int, default=3,
                        help="エンジン multipv (default: 3)")
    parser.add_argument("--nodes", type=int, default=150000,
                        help="エンジン nodes (default: 150000)")
    parser.add_argument("--sample", "-n", type=int, default=None,
                        help="出力レコード数 (ランダムサンプリング)")
    parser.add_argument("--min-ply", type=int, default=5,
                        help="最小手数 (default: 5)")
    parser.add_argument("--max-ply", type=int, default=200,
                        help="最大手数 (default: 200)")
    parser.add_argument("--interval", type=int, default=5,
                        help="サンプリング間隔 (N手ごと, default: 5)")
    parser.add_argument("--eval-set", action="store_true",
                        help="eval_set 形式で出力")
    parser.add_argument("--output", "-o", default=None,
                        help="出力パス")
    parser.add_argument("--seed", type=int, default=42,
                        help="乱数シード (default: 42)")
    args = parser.parse_args()

    rng = random.Random(args.seed)

    # Collect KIF files
    import glob as glob_mod
    kif_files: List[Path] = []
    for pattern in args.inputs:
        expanded = glob_mod.glob(pattern)
        if expanded:
            kif_files.extend(Path(p) for p in sorted(expanded))
        else:
            kif_files.append(Path(pattern))

    if not kif_files:
        print("[ingest] No input files")
        return

    print(f"[ingest] {len(kif_files)} file(s)")

    # Process each file
    all_records: List[Dict[str, Any]] = []
    for kif_path in kif_files:
        if not kif_path.exists():
            print(f"[ingest] File not found: {kif_path}")
            continue

        suffix = kif_path.suffix.lower()
        if suffix in (".usi", ".txt"):
            records = process_usi_file(kif_path, rng, args.min_ply, args.max_ply)
        else:
            records = process_kif_file(kif_path, rng, args.min_ply, args.max_ply)

        # Subsample by interval (every N moves)
        if args.interval > 1:
            records = [r for r in records if r["ply"] % args.interval == 0]

        all_records.extend(records)

    print(f"\n[ingest] Total valid records: {len(all_records)}")

    if not all_records:
        print("[ingest] No valid records to output")
        return

    # Random sample if requested
    if args.sample and args.sample < len(all_records):
        rng.shuffle(all_records)
        all_records = all_records[:args.sample]
        # Sort by source + ply for readability
        all_records.sort(key=lambda r: (r.get("source", ""), r["ply"]))
        print(f"[ingest] Sampled {len(all_records)} records")

    # Engine analysis (optional)
    if args.engine:
        print("\n[ingest] Running engine analysis...")
        all_records = enrich_with_engine(all_records, args.multipv, args.nodes)

    # Final validation
    print("\n[ingest] Final validation...")
    final = validate_all(all_records)
    print(f"[ingest] Final: {len(final)}/{len(all_records)} valid")

    if not final:
        print("[ingest] No valid records after final validation")
        return

    # Output
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    if args.eval_set:
        if args.output:
            out_path = Path(args.output)
        else:
            out_path = _PROJECT_ROOT / "data" / "human_eval" / f"eval_set_{ts}.json"
        save_eval_set(final, out_path)
    else:
        if args.output:
            out_path = Path(args.output)
        else:
            out_path = _PROJECT_ROOT / "data" / "ingested" / f"positions_{ts}.json"
        save_positions(final, out_path)

    # Summary
    phases = {}
    for r in final:
        p = r.get("phase", "?")
        phases[p] = phases.get(p, 0) + 1
    print(f"\n[ingest] Phase distribution: {phases}")
    print("[ingest] Done.")


if __name__ == "__main__":
    main()
