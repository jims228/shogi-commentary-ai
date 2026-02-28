# backend/api/utils/shogi_explain_core.py
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Set, Any
import copy
import json
import os
import re

import google.generativeai as genai
from backend.api.utils.gemini_client import ensure_configured, get_model_name

_LEVEL_ORDER = {"beginner": 0, "intermediate": 1, "advanced": 2}


def _level_ge(level: str, threshold: str) -> bool:
    return _LEVEL_ORDER.get(level, 0) >= _LEVEL_ORDER.get(threshold, 0)

STARTPOS_SFEN = "lnsgkgsnl/1r5b1/p1ppppppp/9/9/9/P1PPPPPPP/1B5R1/LNSGKGSNL b - 1"

KANJI_NUM = ["", "一", "二", "三", "四", "五", "六", "七", "八", "九"]

PIECE_JP = {
    "P": "歩", "L": "香", "N": "桂", "S": "銀", "G": "金", "B": "角", "R": "飛", "K": "玉",
    "+P": "と", "+L": "成香", "+N": "成桂", "+S": "成銀", "+B": "馬", "+R": "龍",
}

PIECE_VALUE = {
    "P": 1, "L": 3, "N": 3, "S": 5, "G": 6, "B": 8, "R": 10,
    "+P": 5, "+L": 5, "+N": 5, "+S": 6, "+B": 10, "+R": 12,
}

# --- 用語DB（初心者向け補足） ---
_GLOSSARY_CACHE: Optional[Dict[str, str]] = None

_GLOSSARY_PRIORITY = [
    "王手", "詰み", "詰み筋", "成り", "持ち駒", "打",
    "評価値", "PV", "候補手",
    "大駒", "利き", "駒得", "玉の安全",
    "居飛車", "振り飛車", "中飛車", "四間飛車", "三間飛車", "向かい飛車",
]


def _default_glossary() -> Dict[str, str]:
    # JSONが無い環境でも落ちないように最小セットを内蔵
    return {
        "王手": "相手の玉に次の手で取れる状態。相手は基本的に受ける必要があります。",
        "成り": "駒を強くすること。動きが変わります。",
        "持ち駒": "取った駒。盤上へ打てます。",
        "PV": "エンジンが読んでいる最善の手順。",
        "評価値": "局面の有利不利の目安（cp）。",
        "候補手": "有力とみなした手の一覧。",
    }


def load_glossary() -> Dict[str, str]:
    global _GLOSSARY_CACHE
    if _GLOSSARY_CACHE is not None:
        return _GLOSSARY_CACHE

    # 既定パス: backend/api/data/shogi_glossary.json
    default_path = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "data", "shogi_glossary.json")
    )
    path = os.getenv("SHOGI_GLOSSARY_PATH") or default_path

    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        if isinstance(obj, dict) and obj:
            _GLOSSARY_CACHE = {str(k): str(v) for k, v in obj.items()}
            return _GLOSSARY_CACHE
    except Exception:
        pass

    _GLOSSARY_CACHE = _default_glossary()
    return _GLOSSARY_CACHE


def extract_glossary_terms(text: str, glossary: Dict[str, str], max_terms: int = 6) -> List[str]:
    found: List[str] = []
    for term in _GLOSSARY_PRIORITY:
        if term in text and term in glossary:
            found.append(term)
            if len(found) >= max_terms:
                break
    return found

def _rank_to_y(ch: str) -> int:
    # 'a'..'i' => 0..8 (aが上段)
    return ord(ch) - ord("a")

def _file_to_x(ch: str) -> int:
    # file '1'..'9' => x 8..0 （SFENは左から9筋）
    f = int(ch)
    return 9 - f

def sq_to_xy(sq: str) -> Tuple[int, int]:
    # "7g"
    return _file_to_x(sq[0]), _rank_to_y(sq[1])

def xy_to_file_rank(x: int, y: int) -> Tuple[int, int]:
    file_ = 9 - x
    rank_ = y + 1
    return file_, rank_

def piece_side(piece: str) -> str:
    # 'b' or 'w'
    if piece.startswith("+"):
        return "b" if piece[1].isupper() else "w"
    return "b" if piece.isupper() else "w"

def piece_kind_upper(piece: str) -> str:
    # promoted => "+P" 形式にして返す（大文字基準）
    if piece.startswith("+"):
        return "+" + piece[1].upper()
    return piece.upper()


def unpromote_kind(kind: str) -> str:
    # "+P" -> "P"
    return kind[1:] if kind and kind.startswith("+") else kind

def is_promoted(piece: str) -> bool:
    return piece.startswith("+")

def promote_piece(piece: str) -> str:
    if piece.startswith("+"):
        return piece
    # 例: 'p' -> '+p', 'P' -> '+P'
    return "+" + piece

def board_clone(board: List[List[Optional[str]]]) -> List[List[Optional[str]]]:
    return [row[:] for row in board]

def parse_sfen_board(board_part: str) -> List[List[Optional[str]]]:
    rows = board_part.split("/")
    board: List[List[Optional[str]]] = [[None for _ in range(9)] for _ in range(9)]
    for y, row in enumerate(rows):
        x = 0
        i = 0
        while i < len(row):
            ch = row[i]
            if ch.isdigit():
                x += int(ch)
                i += 1
                continue
            if ch == "+":
                # promoted piece
                nxt = row[i + 1]
                board[y][x] = "+" + nxt
                x += 1
                i += 2
                continue
            board[y][x] = ch
            x += 1
            i += 1
    return board

@dataclass
class PositionState:
    board: List[List[Optional[str]]]
    turn: str              # 'b' or 'w'
    moves: List[str]       # usi moves applied from base position

def parse_position_cmd(position_cmd: str) -> PositionState:
    s = position_cmd.strip()
    if s.startswith("position"):
        s = s[len("position"):].strip()

    if s.startswith("startpos"):
        base_board = parse_sfen_board(STARTPOS_SFEN.split()[0])
        turn = "b"
        moves: List[str] = []
        rest = s[len("startpos"):].strip()
        if rest.startswith("moves"):
            moves = rest[len("moves"):].strip().split()
        board = base_board
        t = turn
        for mv in moves:
            board, _ = apply_usi_move(board, mv, t)
            t = "w" if t == "b" else "b"
        return PositionState(board=board, turn=t, moves=moves)

    if s.startswith("sfen"):
        # "sfen <board> <turn> <hand> <moveNumber> [moves ...]"
        parts = s.split()
        if len(parts) < 5:
            # fallback
            base_board = parse_sfen_board(STARTPOS_SFEN.split()[0])
            return PositionState(board=base_board, turn="b", moves=[])

        board_part = parts[1]
        turn = parts[2]
        # parts[3] hand, parts[4] moveNumber
        moves: List[str] = []
        if "moves" in parts:
            mi = parts.index("moves")
            moves = parts[mi + 1:]
        board = parse_sfen_board(board_part)
        t = turn
        for mv in moves:
            board, _ = apply_usi_move(board, mv, t)
            t = "w" if t == "b" else "b"
        return PositionState(board=board, turn=t, moves=moves)

    # unknown => startpos
    base_board = parse_sfen_board(STARTPOS_SFEN.split()[0])
    return PositionState(board=base_board, turn="b", moves=[])

def apply_usi_move(board_in: List[List[Optional[str]]], move: str, turn: str) -> Tuple[List[List[Optional[str]]], Optional[str]]:
    board = board_clone(board_in)
    captured: Optional[str] = None

    if "*" in move:
        p, dst = move.split("*")
        dx, dy = sq_to_xy(dst)
        placed = p.upper() if turn == "b" else p.lower()
        board[dy][dx] = placed
        return board, None

    src = move[:2]
    dst = move[2:4]
    promote = move.endswith("+")
    sx, sy = sq_to_xy(src)
    dx, dy = sq_to_xy(dst)

    piece = board[sy][sx]
    board[sy][sx] = None
    captured = board[dy][dx]

    if piece is None:
        # 盤面不整合でも落ちないように
        return board, captured

    if promote:
        piece = promote_piece(piece)

    board[dy][dx] = piece
    return board, captured

def find_king(board: List[List[Optional[str]]], side: str) -> Optional[Tuple[int, int]]:
    target = "K" if side == "b" else "k"
    for y in range(9):
        for x in range(9):
            if board[y][x] == target:
                return x, y
            if board[y][x] == ("+" + target):  # 念のため
                return x, y
    return None

def _in_bounds(x: int, y: int) -> bool:
    return 0 <= x < 9 and 0 <= y < 9

def _add_step(att: Set[Tuple[int, int]], x: int, y: int, dx: int, dy: int):
    nx, ny = x + dx, y + dy
    if _in_bounds(nx, ny):
        att.add((nx, ny))

def _add_slider(att: Set[Tuple[int, int]], board: List[List[Optional[str]]], x: int, y: int, dx: int, dy: int):
    nx, ny = x + dx, y + dy
    while _in_bounds(nx, ny):
        att.add((nx, ny))
        if board[ny][nx] is not None:
            break
        nx += dx
        ny += dy

def attacks_from_piece(board: List[List[Optional[str]]], x: int, y: int, piece: str) -> Set[Tuple[int, int]]:
    side = piece_side(piece)
    k = piece_kind_upper(piece)  # e.g. 'P', '+B'
    att: Set[Tuple[int, int]] = set()

    fwd = -1 if side == "b" else 1

    # helper: gold-like moves
    def gold():
        _add_step(att, x, y, 0, fwd)
        _add_step(att, x, y, -1, fwd)
        _add_step(att, x, y, 1, fwd)
        _add_step(att, x, y, -1, 0)
        _add_step(att, x, y, 1, 0)
        _add_step(att, x, y, 0, -fwd)

    if k == "K":
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                _add_step(att, x, y, dx, dy)
        return att

    if k == "P":
        _add_step(att, x, y, 0, fwd)
        return att

    if k == "L":
        _add_slider(att, board, x, y, 0, fwd)
        return att

    if k == "N":
        _add_step(att, x, y, -1, 2 * fwd)
        _add_step(att, x, y, 1, 2 * fwd)
        return att

    if k == "S":
        _add_step(att, x, y, 0, fwd)
        _add_step(att, x, y, -1, fwd)
        _add_step(att, x, y, 1, fwd)
        _add_step(att, x, y, -1, -fwd)
        _add_step(att, x, y, 1, -fwd)
        return att

    if k == "G":
        gold()
        return att

    if k == "B":
        _add_slider(att, board, x, y, 1, 1)
        _add_slider(att, board, x, y, 1, -1)
        _add_slider(att, board, x, y, -1, 1)
        _add_slider(att, board, x, y, -1, -1)
        return att

    if k == "R":
        _add_slider(att, board, x, y, 1, 0)
        _add_slider(att, board, x, y, -1, 0)
        _add_slider(att, board, x, y, 0, 1)
        _add_slider(att, board, x, y, 0, -1)
        return att

    if k in ("+P", "+L", "+N", "+S"):
        gold()
        return att

    if k == "+B":  # horse
        # bishop slider + orth step
        _add_slider(att, board, x, y, 1, 1)
        _add_slider(att, board, x, y, 1, -1)
        _add_slider(att, board, x, y, -1, 1)
        _add_slider(att, board, x, y, -1, -1)
        _add_step(att, x, y, 1, 0)
        _add_step(att, x, y, -1, 0)
        _add_step(att, x, y, 0, 1)
        _add_step(att, x, y, 0, -1)
        return att

    if k == "+R":  # dragon
        # rook slider + diag step
        _add_slider(att, board, x, y, 1, 0)
        _add_slider(att, board, x, y, -1, 0)
        _add_slider(att, board, x, y, 0, 1)
        _add_slider(att, board, x, y, 0, -1)
        _add_step(att, x, y, 1, 1)
        _add_step(att, x, y, 1, -1)
        _add_step(att, x, y, -1, 1)
        _add_step(att, x, y, -1, -1)
        return att

    return att

def attacked_squares(board: List[List[Optional[str]]], side: str, only_big: bool = False) -> Set[Tuple[int, int]]:
    res: Set[Tuple[int, int]] = set()
    for y in range(9):
        for x in range(9):
            p = board[y][x]
            if not p:
                continue
            if piece_side(p) != side:
                continue
            if only_big:
                ku = piece_kind_upper(p)
                if ku not in ("B", "R", "+B", "+R"):
                    continue
            res |= attacks_from_piece(board, x, y, p)
    return res

def move_to_japanese(move: str, board_before: List[List[Optional[str]]], turn: str) -> str:
    prefix = "▲" if turn == "b" else "△"

    if "*" in move:
        p, dst = move.split("*")
        dx, dy = sq_to_xy(dst)
        file_, rank_ = xy_to_file_rank(dx, dy)
        piece_name = PIECE_JP.get(p.upper(), p.upper())
        return f"{prefix}{file_}{KANJI_NUM[rank_]}{piece_name}打"

    src = move[:2]
    dst = move[2:4]
    promote = move.endswith("+")
    sx, sy = sq_to_xy(src)
    dx, dy = sq_to_xy(dst)

    piece = board_before[sy][sx]
    file_, rank_ = xy_to_file_rank(dx, dy)

    if not piece:
        return f"{prefix}{file_}{KANJI_NUM[rank_]}"

    base = piece_kind_upper(piece).replace("+", "")
    base_name = PIECE_JP.get(base, base)

    if promote:
        # 初心者向けに「角成」等を明示
        return f"{prefix}{file_}{KANJI_NUM[rank_]}{base_name}成"

    # すでに成っている駒は「と/馬/龍」などで出す
    full_name = PIECE_JP.get(piece_kind_upper(piece), base_name)
    return f"{prefix}{file_}{KANJI_NUM[rank_]}{full_name}"

def _score_to_words(cp_for_turn: Optional[int], mate_for_turn: Optional[int]) -> str:
    if mate_for_turn is not None and mate_for_turn != 0:
        if mate_for_turn > 0:
            return f"詰み筋（{mate_for_turn}手以内）"
        return f"詰みを防ぐ局面（相手に{-mate_for_turn}手詰）"
    if cp_for_turn is None:
        return "形勢不明"
    a = abs(cp_for_turn)
    if a < 200:
        return "互角"
    if a < 600:
        return "少し良い" if cp_for_turn > 0 else "少し苦しい"
    if a < 1200:
        return "優勢" if cp_for_turn > 0 else "劣勢"
    return "勝勢" if cp_for_turn > 0 else "敗勢"

def _cp_for_turn(turn: str, score_cp_sente: Optional[int]) -> Optional[int]:
    if score_cp_sente is None:
        return None
    return score_cp_sente if turn == "b" else -score_cp_sente

def _mate_for_turn(turn: str, score_mate_sente: Optional[int]) -> Optional[int]:
    if score_mate_sente is None:
        return None
    return score_mate_sente if turn == "b" else -score_mate_sente

def pv_to_jp(board_before: List[List[Optional[str]]], turn: str, pv: str, max_moves: int = 5) -> List[str]:
    moves = pv.strip().split()
    moves = moves[:max_moves]
    out: List[str] = []
    b = board_clone(board_before)
    t = turn
    for mv in moves:
        out.append(move_to_japanese(mv, b, t))
        b, _ = apply_usi_move(b, mv, t)
        t = "w" if t == "b" else "b"
    return out

def detect_simple_strategy(board: List[List[Optional[str]]]) -> str:
    # 超軽量：飛車位置で居飛車/振り飛車を推定（後で拡張しやすい）
    # 先手飛車を探す
    rook_pos = None
    for y in range(9):
        for x in range(9):
            p = board[y][x]
            if p and piece_side(p) == "b" and piece_kind_upper(p) in ("R", "+R"):
                rook_pos = (x, y)
                break
        if rook_pos:
            break
    if not rook_pos:
        return "不明"

    file_, _ = xy_to_file_rank(rook_pos[0], rook_pos[1])
    # 先手の基本：2筋が居飛車。7/6/5/8あたりは振り飛車系
    if file_ == 2:
        return "居飛車（目安）"
    if file_ == 5:
        return "中飛車（目安）"
    if file_ == 6:
        return "四間飛車（目安）"
    if file_ == 7:
        return "三間飛車（目安）"
    if file_ == 8:
        return "向かい飛車（目安）"
    return "力戦（目安）"

def build_explain_facts(req: Dict[str, Any]) -> Dict[str, Any]:
    position_cmd = req.get("sfen") or ""
    level = req.get("explain_level") or "beginner"
    ply = int(req.get("ply", 0) or 0)
    turn = req.get("turn") or "b"
    user_move = req.get("user_move")

    # candidates優先（あると精度が上がる）
    candidates = req.get("candidates") or []
    bestmove = req.get("bestmove") or ""
    score_cp = req.get("score_cp")
    score_mate = req.get("score_mate")
    pv = req.get("pv") or ""
    delta_cp = req.get("delta_cp")

    # 盤面復元
    pos = parse_position_cmd(position_cmd)
    board_before = pos.board
    pos_moves = pos.moves or []

    # --- 戦型/戦法/囲い（ルールベース） ---
    try:
        from backend.ai.opening_detector import detect_opening_bundle
        from backend.ai.castle_detector import detect_castle_bundle

        # IMPORTANT: use request 'turn' (API contract) as the POV for detection.
        opening_facts = detect_opening_bundle(board_before, pos_moves, turn)
        castle_facts = detect_castle_bundle(board_before, turn)
    except Exception:
        opening_facts = {"style": {"id": "unknown", "nameJa": "不明（戦型）", "confidence": 0.0, "reasons": []},
                         "opening": {"id": "unknown", "nameJa": "不明（戦法）", "confidence": 0.0, "reasons": []}}
        castle_facts = {"castle": {"id": "unknown", "nameJa": "不明（囲い）", "confidence": 0.0, "reasons": []}}

    # スコアは「先手視点cp」が来る前提なので、turn視点に直す
    cp_turn = _cp_for_turn(turn, score_cp if isinstance(score_cp, int) else None)
    mate_turn = _mate_for_turn(turn, score_mate if isinstance(score_mate, int) else None)

    # 候補手整形
    cand_out = []
    if candidates:
        for c in candidates[:3]:
            mv = (c.get("move") or "").strip()
            pv_line = (c.get("pv") or "").strip()
            ccp = c.get("score_cp")
            cmate = c.get("score_mate")
            ccp_turn = _cp_for_turn(turn, ccp if isinstance(ccp, int) else None)
            cmate_turn = _mate_for_turn(turn, cmate if isinstance(cmate, int) else None)
            cand_out.append({
                "move": mv,
                "move_jp": move_to_japanese(mv, board_before, turn) if mv else "",
                "score_turn": {"cp": ccp_turn, "mate": cmate_turn},
                "score_words": _score_to_words(ccp_turn, cmate_turn),
                "pv": pv_line,
                "pv_jp": pv_to_jp(board_before, turn, pv_line, max_moves=5) if pv_line else [],
            })

        # bestmove/pvを候補から上書き
        if cand_out and not bestmove:
            bestmove = cand_out[0]["move"]
        if cand_out and not pv:
            pv = candidates[0].get("pv") or pv

        # スコアも候補1を採用
        if cand_out and cp_turn is None and mate_turn is None:
            cp_turn = cand_out[0]["score_turn"]["cp"]
            mate_turn = cand_out[0]["score_turn"]["mate"]

    # --- 解説対象手をここで確定（空なら安全に抜ける） ---
    target_move = (user_move or bestmove or "").strip()

    # pv_movesは“確定したpv”から作る
    pv_moves = [m for m in (pv or "").split() if m.strip()][:6]

    # “指した手”の評価差（候補に入っていれば）
    user_gap_note = None
    if user_move and cand_out:
        best_cp = cand_out[0]["score_turn"]["cp"]
        user_cp = None
        for c in cand_out:
            if c["move"] == user_move:
                user_cp = c["score_turn"]["cp"]
                break
        if best_cp is not None and user_cp is not None:
            gap = best_cp - user_cp
            user_gap_note = {"gap_cp": gap}

    # 手が無い場合は盤面特徴の計算をスキップして返す
    if not target_move:
        return {
            "level": level,
            "ply": ply,
            "turn": turn,
            "target_move": "",
            "target_move_jp": "",
            "bestmove": bestmove,
            "bestmove_jp": move_to_japanese(bestmove, board_before, turn) if bestmove else "",
            "phase": "序盤" if ply < 24 else "終盤" if ply > 100 else "中盤",
            "strategy_hint": detect_simple_strategy(board_before),
            "opening_facts": opening_facts,
            "castle_facts": castle_facts,
            "score_turn": {"cp": cp_turn, "mate": mate_turn},
            "score": {"cp": cp_turn, "mate": mate_turn},
            "score_words": _score_to_words(cp_turn, mate_turn),
            "delta_cp": delta_cp,
            "flags": {
                "is_drop": False,
                "is_capture": False,
                "is_promotion": False,
                "is_check": False,
                "line_opened": False,
                "captured_kind": None,
                "captured_kind_hand": None,
                "captured_value": 0,
            },
            "pv": pv,
            "pv_moves": pv_moves,
            "pv_jp": pv_to_jp(board_before, turn, pv, max_moves=5) if pv else [],
            "candidates": cand_out,
            "user_move": user_move,
            "user_gap": user_gap_note,
            "history_tail": (req.get("history") or [])[-5:],
        }

    # --- ここから先は通常処理 ---
    # 手の適用前後で特徴を取る
    mobility_before = len(attacked_squares(board_before, turn, only_big=True))
    board_after, captured = apply_usi_move(board_before, target_move, turn)
    mobility_after = len(attacked_squares(board_after, turn, only_big=True))

    opp = "w" if turn == "b" else "b"
    king_sq = find_king(board_after, opp)
    is_check = False
    if king_sq:
        is_check = king_sq in attacked_squares(board_after, turn, only_big=False)

    is_drop = ("*" in target_move)
    is_promo = target_move.endswith("+")
    is_capture = captured is not None
    line_opened = (mobility_after - mobility_before) >= 2
    captured_kind = piece_kind_upper(captured) if captured else None
    captured_kind_hand = unpromote_kind(captured_kind) if captured_kind else None
    captured_value = PIECE_VALUE.get(captured_kind, 0) if captured_kind else 0

    facts = {
        "level": level,
        "ply": ply,
        "turn": turn,
        "target_move": target_move,
        "target_move_jp": move_to_japanese(target_move, board_before, turn) if target_move else "",
        "bestmove": bestmove,
        "bestmove_jp": move_to_japanese(bestmove, board_before, turn) if bestmove else "",
        "phase": "序盤" if ply < 24 else "終盤" if ply > 100 else "中盤",
        "strategy_hint": detect_simple_strategy(board_before),
        "opening_facts": opening_facts,
        "castle_facts": castle_facts,
        "score_turn": {"cp": cp_turn, "mate": mate_turn},
        "score": {"cp": cp_turn, "mate": mate_turn},
        "score_words": _score_to_words(cp_turn, mate_turn),
        "delta_cp": delta_cp,
        "flags": {
            "is_drop": is_drop,
            "is_capture": is_capture,
            "is_promotion": is_promo,
            "is_check": is_check,
            "line_opened": line_opened,
            "captured_kind": captured_kind,
            "captured_kind_hand": captured_kind_hand,
            "captured_value": captured_value,
        },
        "pv": pv,
        "pv_moves": pv_moves,
        "pv_jp": pv_to_jp(board_before, turn, pv, max_moves=5) if pv else [],
        "candidates": cand_out,
        "user_move": user_move,
        "user_gap": user_gap_note,
        "history_tail": (req.get("history") or [])[-5:],
    }
    return facts

def render_rule_based_explanation(f: Dict[str, Any]) -> str:
    level = f.get("level") or "beginner"
    lines: List[str] = []
    move_jp = f.get("target_move_jp") or f.get("bestmove_jp") or f.get("target_move") or ""
    phase = f.get("phase", "")
    strat = f.get("strategy_hint", "不明")
    score_words = f.get("score_words", "")
    flags = f.get("flags", {})

    score_turn = f.get("score_turn") or {}
    mate = score_turn.get("mate")
    cp = score_turn.get("cp")

    lines.append(f"【この一手】{move_jp}")
    lines.append(f"【状況】{phase} / 戦型: {strat} / 形勢: {score_words}")

    # ねらい（確実に言える事実だけ）
    aims: List[str] = []
    if flags.get("is_check"):
        aims.append("王手で相手玉の選択肢を減らします。")
    if flags.get("is_capture"):
        ck = flags.get("captured_kind_hand") or flags.get("captured_kind")
        if ck:
            aims.append(f"{PIECE_JP.get(ck, ck)}を取って駒得を狙います。")
        else:
            aims.append("駒取りで形勢を良くします。")
    if flags.get("is_promotion"):
        aims.append("成りで駒の力を一気に上げます。")
    if flags.get("is_drop"):
        aims.append("持ち駒を使って一気に局面を動かします。")
    if flags.get("line_opened"):
        aims.append("大駒の利きが通り、攻めやすくなります。")
    if not aims:
        aims.append("局面の形を整え、次の攻防に備える手です。")

    if _level_ge(level, "beginner"):
        lines.append("【ねらい】" + " ".join(aims[:2]))

    pv_jp = f.get("pv_jp") or []
    if pv_jp and _level_ge(level, "beginner"):
        lines.append("【読み筋】" + " → ".join(pv_jp[:5]))

    cands = f.get("candidates") or []
    if cands and _level_ge(level, "intermediate"):
        lines.append("【候補手（上位）】")
        for i, c in enumerate(cands[:3], start=1):
            lines.append(f"  {i}) {c.get('move_jp','')} / {c.get('score_words','')}")

    # 指した手が最善と違う場合のヒント（候補にある時だけ）
    if f.get("user_move") and f.get("bestmove") and f["user_move"] != f["bestmove"]:
        ug = f.get("user_gap")
        if ug and isinstance(ug.get("gap_cp"), int):
            gap = ug["gap_cp"]
            if gap >= 200:
                lines.append("【改善】この手より、AI最善手の方がはっきり良いです（差が大きめ）。")
            elif gap >= 80:
                lines.append("【改善】AI最善手の方が少し良いです。まずは“次の一手”を比べてみましょう。")
        else:
            lines.append("【改善】他の候補手も見比べると学びが増えます。")

    if _level_ge(level, "advanced"):
        def _score_text_turn(cp_val: Any, mate_val: Any) -> str:
            if isinstance(mate_val, int) and mate_val != 0:
                return f"Mate {mate_val}"
            if isinstance(cp_val, int):
                return f"{cp_val:+d}cp"
            return "不明"

        lines.append("")
        lines.append("【根拠（上級者向け）】")
        lines.append(f"- 評価値（手番視点）: {_score_text_turn(cp, mate)}")

        dcp = f.get("delta_cp")
        if isinstance(dcp, int) and dcp != 0:
            lines.append(f"- この手のインパクト: {dcp:+d}cp（形勢が動いた度合い）")
        else:
            lines.append("- この手のインパクト: 不明（delta_cp未提供）")

        facts_bits: List[str] = []
        if flags.get("is_check"):
            facts_bits.append("王手")
        if flags.get("is_capture"):
            ck = flags.get("captured_kind")
            facts_bits.append(f"駒取り({PIECE_JP.get(ck, ck) if ck else '不明'})")
        if flags.get("is_promotion"):
            facts_bits.append("成り")
        if flags.get("is_drop"):
            facts_bits.append("打")
        if isinstance(mate, int) and mate != 0:
            facts_bits.append("詰み/詰み筋")
        lines.append(f"- 事実: {', '.join(facts_bits) if facts_bits else '特記事項なし'}")

        pv_moves = f.get("pv_moves") or []
        if pv_moves:
            lines.append(f"- 本線PV: {' '.join(pv_moves[:6])}")
        else:
            pv_raw = (f.get("pv") or "").strip()
            lines.append(f"- 本線PV: {pv_raw[:60] if pv_raw else 'なし'}")

        if cands:
            lines.append("- 候補手（上位・数値根拠）:")
            for i, c in enumerate(cands[:3], start=1):
                sc_turn = c.get("score_turn") or {}
                lines.append(
                    f"  {i}. {c.get('move','')} ({_score_text_turn(sc_turn.get('cp'), sc_turn.get('mate'))})"
                )

        lines.append("- 注: 上はエンジンの評価値とPVに基づく説明です（意図付けはPVからの推論）。")

    # --- 初心者向け：次の確認ポイント（LLM不要） ---
    if _level_ge(level, "beginner") and not _level_ge(level, "intermediate"):
        lines.append("【次の確認】")
        if flags.get("is_check"):
            lines.append("- 王手に対する受け（逃げる/取る/合駒）のどれが成立するか。")
        if flags.get("is_capture"):
            lines.append("- 取り返されないか（直後の反撃・駒取り）を確認。")
        if not flags.get("is_check") and not flags.get("is_capture"):
            lines.append("- 相手の狙い（王手・駒取り）がないかを先にチェック。")

    # --- 用語ミニ辞典（初心者/中級だけ） ---
    if not _level_ge(level, "advanced"):
        glossary = load_glossary()
        full_text = "\n".join(lines)
        terms = extract_glossary_terms(full_text, glossary, max_terms=6)
        if terms:
            lines.append("")
            lines.append("【用語】")
            for t in terms:
                lines.append(f"- {t}: {glossary.get(t, '')}")

    return "\n".join(lines)


async def rewrite_with_gemini(base_text: str, facts: Dict[str, Any]) -> Optional[str]:
    """LLMは“言い換え”に限定。新しい事実を捏造しないように強く縛る。"""
    # 外部APIは単一トグルで明示許可（デフォルト/テストではOFF）
    if os.getenv("USE_LLM", "0") != "1":
        return None

    # 用途別トグル（rewrite）。推論(reasoning)とは独立にON/OFFできる。
    if os.getenv("USE_LLM_REWRITE", "0") != "1":
        return None

    provider = (os.getenv("LLM_PROVIDER", "gemini") or "gemini").lower()
    if provider != "gemini":
        return None

    if not ensure_configured():
        return None

    level = facts.get("level", "beginner")

    prompt = f"""
あなたは将棋解説者です。次の文章を、読みやすい日本語に整えてください。

【重要ルール】
- 新しい戦術事実（王手/駒取り/詰み/手筋名など）を“追加しない”。
- 断定しすぎない。根拠は「PV/評価値/候補比較/インパクト」だけに基づける。
- レベル: {level}
  - beginner: 短く、用語に補足
  - intermediate: 見出しごとに整理
  - advanced: 根拠（PV/評価差）を残す

【事実(JSON)】
{json.dumps(facts, ensure_ascii=False)}

【素材テキスト】
{base_text}
"""
    try:
        model_name = get_model_name()
        model = genai.GenerativeModel(model_name)
        res = await model.generate_content_async(prompt)
        return (getattr(res, "text", None) or "").strip() or None
    except Exception:
        return None
