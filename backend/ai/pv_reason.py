from typing import Dict, Any, List, Optional, Tuple

try:
    import shogi  # type: ignore
    HAS_SHOGI = True
except Exception:
    HAS_SHOGI = False


def build_pv_reason_fallback(position_cmd: str, pv_str: str, options: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Fallback PV reasoning without python-shogi.
    Uses the lightweight USI/SFEN parser already used for rule-based explanations.
    """
    from backend.api.utils.shogi_explain_core import parse_position_cmd, apply_usi_move  # local import

    pv_tokens: List[str] = [t for t in (pv_str or "").split() if t]
    if not pv_tokens:
        return None

    max_h = _get_max_horizon(options or {})
    used_h = 0

    try:
        pos = parse_position_cmd(position_cmd or "position startpos")
        board = pos.board
        turn = pos.turn
    except Exception:
        return None

    events: List[Dict[str, Any]] = []
    threat_event: Optional[Dict[str, Any]] = None
    initial_side = "black" if turn == "b" else "white"

    def _append(ev: Dict[str, Any]):
        nonlocal threat_event
        events.append(ev)
        if threat_event is None and ev.get("side") != initial_side:
            threat_event = ev

    for token in pv_tokens:
        if used_h >= max_h:
            break

        side = "black" if turn == "b" else "white"
        early_stop = False

        if "*" in token:
            _append({"type": "drop", "move": token, "side": side})

        # capture detection (non-strict legality; based on dst occupancy)
        try:
            next_board, captured = apply_usi_move(board, token, turn)
            if captured is not None:
                _append({"type": "capture", "move": token, "side": side})
                early_stop = True
            board = next_board
        except Exception:
            break

        used_h += 1
        if token.endswith("+"):
            _append({"type": "promotion", "move": token, "side": side})
            early_stop = True

        # simple check marker: "+" in token (best-effort)
        if "+" in token:
            _append({"type": "check", "move": token, "side": side})
            early_stop = True

        turn = "w" if turn == "b" else "b"
        if early_stop:
            break

    level = (options or {}).get("explain_level") or "beginner"
    threat_line = pv_tokens[:used_h] if used_h > 0 else []

    if level == "beginner":
        summary = "次の狙い（王手・駒取り）に注意しましょう。"
    elif level == "intermediate":
        summary = "相手の狙いと大駒の利きを確認しましょう。"
    else:
        summary = f"読み筋: {' '.join(threat_line)}。"

    return {
        "level": level,
        "used_horizon": used_h,
        "threat_line": threat_line,
        "threat_event": threat_event,
        "events": events,
        "bishop_activity_delta": None,
        "rook_activity_delta": None,
        "hanging": [],
        "summary": summary,
    }


LEVEL_DEFAULTS = {
    "beginner": 5,
    "intermediate": 10,
    "advanced": 16,
}


def _clamp_horizon(h: int) -> int:
    if h < 1:
        return 1
    if h > 20:
        return 20
    return h


def _get_max_horizon(options: Dict[str, Any]) -> int:
    h = options.get("explain_horizon")
    if isinstance(h, int):
        return _clamp_horizon(h)
    lvl = options.get("explain_level") or "beginner"
    base = LEVEL_DEFAULTS.get(lvl, LEVEL_DEFAULTS["beginner"])
    return _clamp_horizon(base)


def _side_name(color: int) -> str:
    return "black" if color == getattr(shogi, "BLACK", 0) else "white"


def _square_name(board: "shogi.Board", sq: int) -> str:
    # python-shogi uses 0..80 squares, names via SQUARE_NAMES
    return shogi.SQUARE_NAMES[sq]


def _bishop_attacks_count(board: "shogi.Board", color: int) -> int:
    """Count potential attack squares for bishops (including horses) of given color.

    Simplified: scans diagonals until blocked; for horses (+B), also includes orthogonal one-step.
    """
    BISHOP = getattr(shogi, "BISHOP", 6)
    PROM_BISHOP = getattr(shogi, "PROM_BISHOP", 13)

    def _attacks_from(sq: int, is_horse: bool) -> int:
        # Convert sq to file/rank (1..9, a..i)
        name = shogi.SQUARE_NAMES[sq]
        fx = int(name[0]) - 1  # 0..8
        fy = ord(name[1]) - ord("a")  # 0..8 (a=0 is top for white side)

        count = 0
        for dx, dy in ((1,1),(1,-1),(-1,1),(-1,-1)):
            x, y = fx + dx, fy + dy
            while 0 <= x < 9 and 0 <= y < 9:
                # add this square, then stop if occupied
                count += 1
                idx = y * 9 + x
                if board.piece_at(idx) is not None:
                    break
                x += dx
                y += dy
        if is_horse:
            for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
                x, y = fx + dx, fy + dy
                if 0 <= x < 9 and 0 <= y < 9:
                    count += 1
        return count

    total = 0
    for sq in range(81):
        piece = board.piece_at(sq)
        if piece is None:
            continue
        if getattr(piece, "color", None) != color:
            continue
        pt = getattr(piece, "piece_type", None)
        if pt == BISHOP:
            total += _attacks_from(sq, False)
        elif pt == PROM_BISHOP:
            total += _attacks_from(sq, True)
    return total


def _is_capture(board: "shogi.Board", mv: "shogi.Move") -> bool:
    to_sq = getattr(mv, "to_square", None)
    if to_sq is None:
        return False
    return board.piece_at(to_sq) is not None


def build_pv_reason(board_before: "shogi.Board", move_str: str, pv_str: str, options: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract reasoning from PV for annotate notes.

    Returns a dict with events and a short summary suitable for note["explain"].
    If python-shogi is unavailable or pv_str empty, returns None.
    """
    if not HAS_SHOGI or board_before is None:
        return None

    pv_tokens: List[str] = [t for t in (pv_str or "").split() if t]
    if not pv_tokens:
        return None

    max_h = _get_max_horizon(options or {})
    used_h = 0

    # Baseline bishop activity for side to move at start
    color_start = getattr(board_before, "turn", getattr(shogi, "BLACK", 0))
    bishop_before = _bishop_attacks_count(board_before, color_start)

    # Work on a clone via SFEN
    board = shogi.Board(sfen=board_before.sfen())

    events: List[Dict[str, Any]] = []
    threat_event: Optional[Dict[str, Any]] = None
    initial_side = _side_name(color_start)

    def _append_event(ev: Dict[str, Any]):
        nonlocal threat_event
        events.append(ev)
        if threat_event is None and ev.get("side") != initial_side:
            # First opponent event becomes threat_event
            threat_event = ev

    early_stop = False

    for idx, token in enumerate(pv_tokens):
        if used_h >= max_h:
            break
        try:
            mv = shogi.Move.from_usi(token)
        except Exception:
            break

        side = _side_name(getattr(board, "turn", getattr(shogi, "BLACK", 0)))

        # event: drop
        if "*" in token:
            _append_event({"type": "drop", "move": token, "side": side})

        # event: capture (before push)
        if _is_capture(board, mv):
            # capture target info (square)
            to_sq = getattr(mv, "to_square", None)
            sq_name = _square_name(board, to_sq) if to_sq is not None else ""
            _append_event({"type": "capture", "move": token, "side": side, "sq": sq_name})
            early_stop = True

        # push
        try:
            board.push(mv)
        except Exception:
            break

        used_h += 1

        # event: promotion (USI suffix '+')
        if token.endswith("+"):
            _append_event({"type": "promotion", "move": token, "side": side})
            early_stop = True

        # event: check (after push)
        try:
            if hasattr(board, "is_check") and board.is_check():
                _append_event({"type": "check", "move": token, "side": side})
                early_stop = True
        except Exception:
            pass

        if early_stop:
            break

    # Bishop activity delta (side to move at start)
    bishop_after = _bishop_attacks_count(board, color_start)
    bishop_delta = bishop_after - bishop_before

    # Minimal hanging detection (after PV): any own piece attacked by opponent but not defended by own big-piece squares?
    # Simplified: we only check bishop/rook attacks sets.
    hanging: List[Dict[str, Any]] = []

    def _big_piece_attacks(board: "shogi.Board", color: int) -> set:
        ROOK = getattr(shogi, "ROOK", 7)
        PROM_ROOK = getattr(shogi, "PROM_ROOK", 14)
        BISHOP = getattr(shogi, "BISHOP", 6)
        PROM_BISHOP = getattr(shogi, "PROM_BISHOP", 13)

        def _rook_attacks_from(sq: int, is_dragon: bool) -> set:
            name = shogi.SQUARE_NAMES[sq]
            fx = int(name[0]) - 1
            fy = ord(name[1]) - ord("a")
            att = set()
            for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
                x, y = fx + dx, fy + dy
                while 0 <= x < 9 and 0 <= y < 9:
                    att.add((x, y))
                    idx = y * 9 + x
                    if board.piece_at(idx) is not None:
                        break
                    x += dx
                    y += dy
            if is_dragon:
                for dx, dy in ((1,1),(1,-1),(-1,1),(-1,-1)):
                    x, y = fx + dx, fy + dy
                    if 0 <= x < 9 and 0 <= y < 9:
                        att.add((x, y))
            return att

        def _bishop_attacks_from(sq: int, is_horse: bool) -> set:
            name = shogi.SQUARE_NAMES[sq]
            fx = int(name[0]) - 1
            fy = ord(name[1]) - ord("a")
            att = set()
            for dx, dy in ((1,1),(1,-1),(-1,1),(-1,-1)):
                x, y = fx + dx, fy + dy
                while 0 <= x < 9 and 0 <= y < 9:
                    att.add((x, y))
                    idx = y * 9 + x
                    if board.piece_at(idx) is not None:
                        break
                    x += dx
                    y += dy
            if is_horse:
                for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
                    x, y = fx + dx, fy + dy
                    if 0 <= x < 9 and 0 <= y < 9:
                        att.add((x, y))
            return att

        squares = set()
        for sq in range(81):
            p = board.piece_at(sq)
            if p is None:
                continue
            if getattr(p, "color", None) != color:
                continue
            pt = getattr(p, "piece_type", None)
            if pt == ROOK:
                squares |= _rook_attacks_from(sq, False)
            elif pt == PROM_ROOK:
                squares |= _rook_attacks_from(sq, True)
            elif pt == BISHOP:
                squares |= _bishop_attacks_from(sq, False)
            elif pt == PROM_BISHOP:
                squares |= _bishop_attacks_from(sq, True)
        return squares

    opp_color = getattr(shogi, "WHITE", 1) if color_start == getattr(shogi, "BLACK", 0) else getattr(shogi, "BLACK", 0)
    opp_att = _big_piece_attacks(board, opp_color)
    own_att = _big_piece_attacks(board, color_start)

    # find one hanging piece
    for sq in range(81):
        p = board.piece_at(sq)
        if p is None:
            continue
        if getattr(p, "color", None) != color_start:
            continue
        name = shogi.SQUARE_NAMES[sq]
        fx = int(name[0]) - 1
        fy = ord(name[1]) - ord("a")
        if (fx, fy) in opp_att and (fx, fy) not in own_att:
            hanging.append({"piece": "駒", "sq": name, "side": initial_side})
            break

    # threat line (up to used_h moves)
    threat_line = pv_tokens[:used_h] if used_h > 0 else []

    # summary
    level = (options or {}).get("explain_level") or "beginner"
    if level == "beginner":
        bits: List[str] = []
        if threat_event and threat_event.get("type") == "capture":
            bits.append("次に駒を取られやすいです。")
        if bishop_delta < 0:
            bits.append("角の利きが通りにくくなります。")
        summary = " ".join(bits) or "次の狙い（駒取りや王手）に注意しましょう。"
    elif level == "intermediate":
        parts = []
        if threat_event:
            t = threat_event.get("type")
            parts.append(f"相手の狙いは{t}です。")
        if bishop_delta:
            parts.append(f"角の利き変化: {bishop_delta:+d}。")
        summary = " ".join(parts) or "相手の狙いと大駒の利きを確認しましょう。"
    else:  # advanced
        parts = []
        if threat_line:
            parts.append(f"読み筋: {' '.join(threat_line)}。")
        if threat_event:
            t = threat_event.get("type")
            parts.append(f"最初の狙い: {t}。")
        parts.append(f"角の利きΔ: {bishop_delta:+d}。")
        summary = " ".join(parts)

    return {
        "level": level,
        "used_horizon": used_h,
        "threat_line": threat_line,
        "threat_event": threat_event,
        "events": events,
        "bishop_activity_delta": bishop_delta,
        "rook_activity_delta": None,
        "hanging": hanging,
        "summary": summary,
    }
