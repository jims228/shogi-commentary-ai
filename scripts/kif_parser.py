#!/usr/bin/env python3
"""KIF形式の棋譜ファイルをパースするスクリプト.

KIF形式（Shift-JIS / UTF-8）を読み込み、ヘッダー情報・指し手・コメント・
消費時間を抽出してJSONとして出力する。USI形式への変換機能も提供。

Usage:
    python3 scripts/kif_parser.py data/games/game01.kif \
      --output data/parsed/game01_moves.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

# ---------------------------------------------------------------------------
# 漢数字 / 全角数字 → int 変換テーブル
# ---------------------------------------------------------------------------
_KANJI_TO_INT = {
    "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9,
}
_ZEN_TO_HAN = {
    "１": "1", "２": "2", "３": "3", "４": "4", "５": "5",
    "６": "6", "７": "7", "８": "8", "９": "9",
}

# USI rank: 1→a, 2→b, ..., 9→i
_RANK_TO_USI = {i: chr(ord("a") + i - 1) for i in range(1, 10)}

# 駒名 → USI piece letter (大文字)
_PIECE_TO_USI = {
    "歩": "P", "香": "L", "桂": "N", "銀": "S",
    "金": "G", "角": "B", "飛": "R", "玉": "K", "王": "K",
    "と": "+P", "成香": "+L", "成桂": "+N", "成銀": "+S",
    "馬": "+B", "龍": "+R", "竜": "+R",
}

# ヘッダーキーの正規化マップ
_HEADER_KEYS = {
    "開始日時": "date",
    "終了日時": "end_date",
    "棋戦": "event",
    "手合割": "handicap",
    "先手": "sente",
    "後手": "gote",
    "場所": "place",
    "持ち時間": "time_control",
    "表題": "title",
    "戦型": "strategy",
}

# 指し手行の正規表現
# 例: "   1 ７六歩(77)   ( 0:16/00:00:16)"
_MOVE_RE = re.compile(
    r"^\s*(\d+)\s+"          # 手数
    r"(.+?)"                 # 指し手
    r"\s*\(\s*"              # 消費時間開始
    r"(\d+:\d+)"             # 消費時間 (m:ss)
    r"\s*/\s*"
    r"(\d+:\d+:\d+)"         # 累計時間 (h:mm:ss)
    r"\s*\)\s*$"
)

# 消費時間がない指し手行
_MOVE_NO_TIME_RE = re.compile(
    r"^\s*(\d+)\s+"
    r"(.+?)"
    r"\s*$"
)

# 指し手テキストの解析
# 例: "７六歩(77)", "同　金(48)", "４一銀打", "３三角成(88)"
_MOVE_TEXT_RE = re.compile(
    r"(?:同\s*|([１-９1-9])([一-九]))"   # 移動先: 同 or 筋段
    r"(歩|香|桂|銀|金|角|飛|玉|王|と|成香|成桂|成銀|馬|龍|竜)"  # 駒名
    r"(成)?"                              # 成り
    r"(打)?"                              # 打ち
    r"(?:\((\d{2})\))?"                   # 移動元 (NN)
)

# 終局条件
_RESULT_KEYWORDS = ("投了", "中断", "千日手", "持将棋", "切れ負け", "反則",
                    "詰み", "入玉勝ち", "時間切れ")


# ---------------------------------------------------------------------------
# パース関数
# ---------------------------------------------------------------------------

def _normalize_digit(ch: str) -> str:
    """全角数字→半角、漢数字はそのまま."""
    return _ZEN_TO_HAN.get(ch, ch)


def _parse_file_rank(file_ch: str, rank_ch: str) -> Tuple[int, int]:
    """筋(file)と段(rank)をintに変換.

    Returns (file: 1-9, rank: 1-9)
    """
    f = int(_normalize_digit(file_ch))
    r = _KANJI_TO_INT.get(rank_ch, 0)
    if r == 0:
        r = int(_normalize_digit(rank_ch))
    return f, r


def _detect_encoding(file_path: Path) -> str:
    """ファイルのエンコーディングを判定."""
    raw = file_path.read_bytes()
    # UTF-8 BOM
    if raw[:3] == b"\xef\xbb\xbf":
        return "utf-8-sig"
    # UTF-8 で decode できるか試す
    try:
        raw.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        pass
    # Shift-JIS (CP932)
    try:
        raw.decode("cp932")
        return "cp932"
    except UnicodeDecodeError:
        pass
    return "utf-8"  # fallback


def parse_kif(text: str) -> Dict[str, Any]:
    """KIF形式テキストをパースして辞書を返す.

    Parameters
    ----------
    text : str
        KIF形式の棋譜テキスト (デコード済み)

    Returns
    -------
    dict
        {"header": {...}, "moves": [...], "result": "..."}
    """
    header: Dict[str, str] = {}
    moves: List[Dict[str, Any]] = []
    result: str = ""
    pending_comments: List[str] = []
    in_moves = False
    prev_dest: Optional[Tuple[int, int]] = None  # 「同」処理用

    for line in text.splitlines():
        line = line.rstrip()

        # 空行スキップ
        if not line:
            continue

        # コメント行 (#)
        if line.startswith("#"):
            continue

        # コメント行 (* で始まる) → 直前の手に紐づける
        if line.startswith("*"):
            comment_text = line[1:].strip()
            if comment_text:
                if moves:
                    moves[-1].setdefault("comments", []).append(comment_text)
                else:
                    pending_comments.append(comment_text)
            continue

        # 手数行ヘッダ (区切り線)
        if "手数" in line and "指手" in line:
            in_moves = True
            continue

        # ヘッダー行
        if not in_moves and "：" in line:
            key, _, val = line.partition("：")
            key = key.strip()
            val = val.strip()
            normalized = _HEADER_KEYS.get(key)
            if normalized:
                header[normalized] = val
            else:
                header[key] = val
            continue

        # 指し手行
        m = _MOVE_RE.match(line)
        if m:
            in_moves = True
            ply = int(m.group(1))
            move_text = m.group(2).strip()
            time_spent = m.group(3)
            cumulative_time = m.group(4)

            # 終局判定
            is_result = False
            for kw in _RESULT_KEYWORDS:
                if kw in move_text:
                    result = move_text
                    is_result = True
                    break

            if not is_result:
                move_entry = _parse_move_text(move_text, ply, prev_dest)
                move_entry["time_spent"] = time_spent
                move_entry["cumulative_time"] = cumulative_time
                move_entry["comments"] = pending_comments
                pending_comments = []
                moves.append(move_entry)
                # prev_dest 更新
                if move_entry.get("dest_file") and move_entry.get("dest_rank"):
                    prev_dest = (move_entry["dest_file"], move_entry["dest_rank"])
            else:
                # 終局行にもコメントを付与
                if pending_comments and moves:
                    moves[-1]["comments"].extend(pending_comments)
                    pending_comments = []
            continue

        # 消費時間なしの指し手行
        m2 = _MOVE_NO_TIME_RE.match(line)
        if m2 and in_moves:
            ply = int(m2.group(1))
            move_text = m2.group(2).strip()

            is_result = False
            for kw in _RESULT_KEYWORDS:
                if kw in move_text:
                    result = move_text
                    is_result = True
                    break

            if not is_result:
                move_entry = _parse_move_text(move_text, ply, prev_dest)
                move_entry["time_spent"] = None
                move_entry["cumulative_time"] = None
                move_entry["comments"] = pending_comments
                pending_comments = []
                moves.append(move_entry)
                if move_entry.get("dest_file") and move_entry.get("dest_rank"):
                    prev_dest = (move_entry["dest_file"], move_entry["dest_rank"])
            else:
                if pending_comments and moves:
                    moves[-1]["comments"].extend(pending_comments)
                    pending_comments = []
            continue

    # 残りコメントを最後の手に付与
    if pending_comments and moves:
        moves[-1]["comments"].extend(pending_comments)

    # 出力用moves整形
    output_moves = []
    for mv in moves:
        entry: Dict[str, Any] = {
            "ply": mv["ply"],
            "move_ja": mv["move_ja"],
        }
        if mv.get("move_from"):
            entry["move_from"] = mv["move_from"]
        if mv.get("is_drop"):
            entry["is_drop"] = True
        if mv.get("is_promote"):
            entry["is_promote"] = True
        if mv.get("is_same"):
            entry["is_same"] = True
        # USI変換に必要な内部フィールドも保持
        entry["dest_file"] = mv.get("dest_file")
        entry["dest_rank"] = mv.get("dest_rank")
        entry["piece_name"] = mv.get("piece_name", "")
        entry["time_spent"] = mv.get("time_spent")
        entry["cumulative_time"] = mv.get("cumulative_time")
        entry["comments"] = mv.get("comments", [])
        output_moves.append(entry)

    return {
        "header": header,
        "moves": output_moves,
        "result": result,
    }


def _parse_move_text(
    text: str,
    ply: int,
    prev_dest: Optional[Tuple[int, int]],
) -> Dict[str, Any]:
    """指し手テキストをパースして情報を抽出."""
    entry: Dict[str, Any] = {"ply": ply, "move_ja": "", "move_from": None}

    is_same = "同" in text
    is_drop = "打" in text
    is_promote = "成" in text and "成香" not in text and "成桂" not in text and "成銀" not in text

    # 移動元 (NN) の抽出
    from_match = re.search(r"\((\d{2})\)", text)
    move_from = from_match.group(1) if from_match else None

    # 駒名の抽出
    piece_match = re.search(
        r"(成香|成桂|成銀|歩|香|桂|銀|金|角|飛|玉|王|と|馬|龍|竜)", text
    )
    piece_name = piece_match.group(1) if piece_match else ""

    # 移動先の抽出
    dest_file: Optional[int] = None
    dest_rank: Optional[int] = None

    if is_same and prev_dest:
        dest_file, dest_rank = prev_dest
        move_ja = f"同{piece_name}"
    else:
        # 筋段を探す
        dest_match = re.search(r"([１-９1-9])([一二三四五六七八九])", text)
        if dest_match:
            dest_file, dest_rank = _parse_file_rank(
                dest_match.group(1), dest_match.group(2)
            )
        move_ja = ""
        if dest_file and dest_rank:
            # 全角筋名 → 使い分け (元テキストをそのまま)
            file_ch = text[0] if re.match(r"[１-９1-9]", text[0:1]) else ""
            rank_ch = ""
            if dest_match:
                file_ch = dest_match.group(1)
                rank_ch = dest_match.group(2)
            move_ja = f"{file_ch}{rank_ch}{piece_name}"

    if is_promote and "成香" not in piece_name and "成桂" not in piece_name and "成銀" not in piece_name:
        move_ja += "成"
    if is_drop:
        move_ja += "打"

    entry["move_ja"] = move_ja
    entry["move_from"] = move_from
    entry["dest_file"] = dest_file
    entry["dest_rank"] = dest_rank
    entry["piece_name"] = piece_name
    entry["is_same"] = is_same
    entry["is_drop"] = is_drop
    entry["is_promote"] = is_promote

    return entry


# ---------------------------------------------------------------------------
# USI変換
# ---------------------------------------------------------------------------

def move_to_usi(move: Dict[str, Any], prev_dest: Optional[Tuple[int, int]] = None) -> Optional[str]:
    """パース済みの手をUSI形式に変換.

    Parameters
    ----------
    move : dict
        parse_kif() の moves 要素
    prev_dest : (file, rank) | None
        「同X」の場合に必要な直前の移動先

    Returns
    -------
    str | None
        USI文字列 (例: "7g7f", "G*5b") or None
    """
    piece_name = move.get("piece_name", "")
    is_drop = move.get("is_drop", False)
    is_promote = move.get("is_promote", False)
    is_same = move.get("is_same", False)
    move_from = move.get("move_from")

    # 移動先座標
    dest_file = move.get("dest_file")
    dest_rank = move.get("dest_rank")

    if is_same and prev_dest:
        dest_file, dest_rank = prev_dest

    if dest_file is None or dest_rank is None:
        return None

    dest_usi = f"{dest_file}{_RANK_TO_USI.get(dest_rank, '')}"

    # 打ち
    if is_drop:
        usi_piece = _PIECE_TO_USI.get(piece_name, "")
        if usi_piece and not usi_piece.startswith("+"):
            return f"{usi_piece[0]}*{dest_usi}"
        return None

    # 通常手
    if move_from and len(move_from) == 2:
        from_file = int(move_from[0])
        from_rank = int(move_from[1])
        from_usi = f"{from_file}{_RANK_TO_USI.get(from_rank, '')}"
        promote_str = "+" if is_promote else ""
        return f"{from_usi}{dest_usi}{promote_str}"

    return None


def moves_to_usi(parsed: Dict[str, Any]) -> List[Optional[str]]:
    """パース結果の全手をUSI形式に変換."""
    result = []
    prev_dest: Optional[Tuple[int, int]] = None
    for mv in parsed["moves"]:
        usi = move_to_usi(mv, prev_dest)
        result.append(usi)
        # dest更新
        d_file = mv.get("dest_file")
        d_rank = mv.get("dest_rank")
        if mv.get("is_same") and prev_dest:
            pass  # prev_dest は変わらない
        elif d_file and d_rank:
            prev_dest = (d_file, d_rank)
    return result


# ---------------------------------------------------------------------------
# ファイル読み込み
# ---------------------------------------------------------------------------

def parse_kif_file(file_path: "str | Path") -> Dict[str, Any]:
    """KIFファイルをエンコーディング自動判定で読み込みパース."""
    if not isinstance(file_path, Path):
        file_path = Path(file_path)
    enc = _detect_encoding(file_path)
    text = file_path.read_text(encoding=enc)
    return parse_kif(text)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="KIF形式の棋譜をパースしてJSONに変換"
    )
    parser.add_argument("input", help="入力KIFファイル")
    parser.add_argument(
        "--output", "-o",
        help="出力JSONファイル (デフォルト: data/parsed/<input名>_moves.json)",
    )
    parser.add_argument(
        "--with-usi", action="store_true",
        help="USI形式の指し手も出力に含める",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    parsed = parse_kif_file(input_path)

    if args.with_usi:
        usi_moves = moves_to_usi(parsed)
        for i, mv in enumerate(parsed["moves"]):
            if i < len(usi_moves):
                mv["usi"] = usi_moves[i]

    # 出力先決定
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = (
            _PROJECT_ROOT / "data" / "parsed"
            / f"{input_path.stem}_moves.json"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(parsed, f, ensure_ascii=False, indent=2)

    print(f"Parsed {len(parsed['moves'])} moves")
    print(f"Header: {json.dumps(parsed['header'], ensure_ascii=False)}")
    print(f"Result: {parsed['result']}")
    print(f"Output: {output_path}")


if __name__ == "__main__":
    main()
