import re

KANJI_NUM = {1: "一", 2: "二", 3: "三", 4: "四", 5: "五", 6: "六", 7: "七", 8: "八", 9: "九"}
PIECE_MAP = {
    "P": "歩", "L": "香", "N": "桂", "S": "銀", "G": "金", "B": "角", "R": "飛",
    "+P": "と", "+L": "成香", "+N": "成桂", "+S": "成銀", "+B": "馬", "+R": "龍",
    "K": "玉",
}


class ShogiUtils:
    KANJI_NUM = KANJI_NUM
    PIECE_NAMES = {
        "P": "歩", "L": "香", "N": "桂", "S": "銀", "G": "金", "B": "角", "R": "飛",
        "+P": "と", "+L": "成香", "+N": "成桂", "+S": "成銀", "+B": "馬", "+R": "龍",
        "K": "玉",
    }

    @staticmethod
    def _rank_to_int(r: str) -> int:
        # USI rank: a..i -> 1..9 （例: f -> 6）
        if not r:
            return 0
        if r.isdigit():
            return int(r)
        o = ord(r.lower()) - ord("a") + 1
        return o if 1 <= o <= 9 else 0

    @staticmethod
    def format_move_label(move: str, turn: str) -> str:
        """
        USI符号（例: 7g7f, P*2c）を日本語表記（例: ▲7六歩）に変換する。
        盤面情報がないため駒名は省略する場合がある。
        """
        if not move:
            return ""

        prefix = "▲" if turn == "b" else "△"

        # 打ち手の場合 (例: P*2c)
        if "*" in move:
            parts = move.split("*", 1)
            piece_char = parts[0].upper()
            dest = parts[1] if len(parts) > 1 else ""
            piece_name = ShogiUtils.PIECE_NAMES.get(piece_char, piece_char)
            if dest and len(dest) >= 2:
                file_idx = dest[0]
                rank_idx = ShogiUtils._rank_to_int(dest[1])
                rank_kanji = ShogiUtils.KANJI_NUM.get(rank_idx, dest[1])
                return f"{prefix}{file_idx}{rank_kanji}{piece_name}打"
            return f"{prefix}{piece_name}打"

        # 通常の指し手 (例: 7g7f, 7g7f+)
        promote = move.endswith("+")
        m = move.rstrip("+")
        if len(m) >= 4:
            src_file = m[0]
            src_rank = ShogiUtils._rank_to_int(m[1])
            dst_file = m[2]
            dst_rank_char = m[3]
            dst_rank = ShogiUtils._rank_to_int(dst_rank_char)
            rank_kanji = ShogiUtils.KANJI_NUM.get(dst_rank, dst_rank_char)
            promote_str = "成" if promote else ""
            return f"{prefix}{dst_file}{rank_kanji}{promote_str}({src_file}{src_rank})"

        return f"{prefix}{move}"


class StrategyAnalyzer:
    def __init__(self, sfen: str):
        self.sfen = sfen
        self.board = self._parse_sfen(sfen)

    @staticmethod
    def analyze_sfen(sfen: str) -> str:
        """局面 SFEN から戦型を簡易判定する（static convenience method）"""
        return StrategyAnalyzer(sfen).analyze()

    def _parse_sfen(self, sfen: str):
        try:
            if not sfen or "startpos" in sfen:
                sfen = "lnsgkgsnl/1r5b1/ppppppppp/9/9/9/PPPPPPPPP/1B5R1/LNSGKGSNL b - 1"

            parts = sfen.split(" ")
            board_str = parts[0]
            rows = board_str.split("/")
            if len(rows) != 9:
                raise ValueError("Invalid board rows")

            board = []
            for row in rows:
                current_row = []
                for char in row:
                    if char.isdigit():
                        current_row.extend([""] * int(char))
                    else:
                        current_row.append(char)
                while len(current_row) < 9:
                    current_row.append("")
                current_row = current_row[:9]
                board.append(current_row)
            return board
        except Exception:
            return [["" for _ in range(9)] for _ in range(9)]

    def analyze(self) -> str:
        try:
            if not self.board or len(self.board) != 9:
                return "不明"

            sente_rook_col = -1
            gote_rook_col = -1
            sente_king_col = -1
            gote_king_col = -1

            for r in range(9):
                for c in range(9):
                    piece = self.board[r][c]
                    if piece in ("R", "+R"):
                        sente_rook_col = 9 - c
                    elif piece in ("r", "+r"):
                        gote_rook_col = 9 - c
                    if piece == "K":
                        sente_king_col = 9 - c
                    elif piece == "k":
                        gote_king_col = 9 - c

            sente_strategy = self._judge_rook_strategy(sente_rook_col)
            gote_strategy = self._judge_rook_strategy(gote_rook_col)
            sente_castle = self._judge_castle(sente_king_col)
            gote_castle = self._judge_castle(gote_king_col)

            return f"先手: {sente_strategy}（{sente_castle}） vs 後手: {gote_strategy}（{gote_castle}）"
        except Exception:
            return "不明"

    def _judge_rook_strategy(self, col: int) -> str:
        if col == -1:
            return "不明"
        if col in [2, 8]:
            return "居飛車"
        if col == 5:
            return "中飛車"
        if col in [3, 4, 6, 7]:
            return "振り飛車"
        return "その他"

    def _judge_castle(self, col: int) -> str:
        if col == -1:
            return "不明"
        if col in [1, 9]:
            return "穴熊模様"
        if col in [2, 8]:
            return "美濃模様"
        if col in [3, 7]:
            return "矢倉模様"
        if col in [4, 6]:
            return "右玉模様"
        if col == 5:
            return "中住まい"
        return "その他"
