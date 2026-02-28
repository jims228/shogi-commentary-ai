// src/lib/sfen.ts
export type Side = "black" | "white";
export type PieceBase = "P"|"L"|"N"|"S"|"G"|"B"|"R"|"K";
export type PieceCode = PieceBase | `+${PieceBase}` | Lowercase<PieceBase> | `+${Lowercase<PieceBase>}`;

export type Placed = { piece: PieceCode; x: number; y: number };

export const STARTPOS_SFEN = "lnsgkgsnl/1r5b1/ppppppppp/9/9/9/PPPPPPPPP/1B5R1/LNSGKGSNL";

// SFENの1段を配列に（左→右＝9筋→1筋の順）
function expandRow(row: string): (PieceCode|null)[] {
  const out: (PieceCode|null)[] = [];
  for (let i=0;i<row.length;i++){
    const ch = row[i];
    if (/\d/.test(ch)) {
      const n = Number(ch);
      for (let k=0;k<n;k++) out.push(null);
    } else if (ch === '+') {
      // プロモーションは +X の2文字
      const next = row[++i];
      out.push( ("+" + next) as PieceCode );
    } else {
      out.push(ch as PieceCode);
    }
  }
  return out;
}

/** 盤面部分のSFEN（例: "lnsg.../..."）→ Placed[] */
export function parseBoardSFEN(board: string): Placed[] {
  const ranks = board.split('/');
  if (ranks.length !== 9) throw new Error("Invalid SFEN board part");
  // SFENは上段(1段目=a)から順。y=0が上
  const pieces: Placed[] = [];
  ranks.forEach((row, y) => {
    const cells = expandRow(row);
    if (cells.length !== 9) throw new Error("Invalid SFEN row width");
    cells.forEach((pc, x) => {
      if (pc) pieces.push({ piece: pc, x, y });
    });
  });
  return pieces;
}

/** "startpos" または "sfen <board> ..." を受け取って盤面Placed[]を返す */
export function sfenToPlaced(input: string): Placed[] {
  if (input.trim() === "startpos") {
    return parseBoardSFEN(STARTPOS_SFEN);
  }
  // 例: "sfen <board> b - 1" or "sfen <board> w - 1 moves ..."
  const m = input.trim().match(/^sfen\s+([^ ]+)\s/i);
  if (!m) throw new Error("Unsupported SFEN input");
  return parseBoardSFEN(m[1]);
}

/** SFEN文字列（盤面のみまたはフルフォーマット）をパースしてPlaced[]を返す */
export function parseSfen(sfen: string): Placed[] {
  // "startpos" または "sfen <board> ..." 形式に対応
  if (!sfen.includes("sfen") && !sfen.includes("startpos")) {
    // 盤面部分のみの場合（例: "lnsgkgsnl/1r5b1/ppppppppp/9/9/9/PPPPPPPPP/1B5R1/LNSGKGSNL"）
    return parseBoardSFEN(sfen);
  }
  return sfenToPlaced(sfen);
}

/** SFEN文字列から持ち駒情報をパース */
export function parseHandFromSfen(sfen: string, side: "b" | "w"): Record<string, number> {
  // SFEN形式: "board turn hand movecount"
  // 例: "9/9/9/9/9/9/9/1Pk6/2G6 b 2G 1"
  //     hand部分は "2G" (金2枚)、"-" (持ち駒なし)
  const parts = sfen.trim().split(/\s+/);
  if (parts.length < 3) return {};

  const handPart = parts[2];
  if (handPart === "-") return {};

  const hand: Record<string, number> = {};
  let i = 0;
  while (i < handPart.length) {
    let count = 1;
    // 数字があればその枚数
    if (/\d/.test(handPart[i])) {
      count = parseInt(handPart[i], 10);
      i++;
    }
    const piece = handPart[i];
    if (!piece) break;

    // 先手の駒は大文字、後手の駒は小文字
    const isBlack = piece === piece.toUpperCase();
    if ((side === "b" && isBlack) || (side === "w" && !isBlack)) {
      const key = piece.toUpperCase();
      hand[key] = (hand[key] || 0) + count;
    }
    i++;
  }

  return hand;
}

/** USI座標 "7g7f" → {from:{x,y}, to:{x,y}}（x:0..8 左→右, y:0..8 上→下） */
export function usiMoveToCoords(usi: string): { from: {x:number;y:number}, to:{x:number;y:number} } | null {
  // drop（例 "P*7f"）は今回は未対応→null返却
  if (usi.includes("*") || usi.length < 4) return null;
  const file = (d:string) => 9 - Number(d); // "9..1" → 0..8
  const rank = (c:string) => c.charCodeAt(0) - "a".charCodeAt(0); // 'a'..'i' → 0..8 (上→下)

  const fx = file(usi[0]), fy = rank(usi[1]);
  const tx = file(usi[2]), ty = rank(usi[3]);
  if ([fx,fy,tx,ty].some(v => Number.isNaN(v) || v<0 || v>8)) return null;
  return { from:{x:fx,y:fy}, to:{x:tx,y:ty} };
}

const KANJI_NUM = ["", "１", "２", "３", "４", "５", "６", "７", "８", "９"];
const KANJI_RANK = ["", "一", "二", "三", "四", "五", "六", "七", "八", "九"];
const PIECE_KANJI: Record<string, string> = {
  P: "歩", L: "香", N: "桂", S: "銀", G: "金", B: "角", R: "飛", K: "玉",
  "+P": "と", "+L": "成香", "+N": "成桂", "+S": "成銀", "+B": "馬", "+R": "龍",
  // 英語小文字(後手)も対応しておく
  p: "歩", l: "香", n: "桂", s: "銀", g: "金", b: "角", r: "飛", k: "玉",
  "+p": "と", "+l": "成香", "+n": "成桂", "+s": "成銀", "+b": "馬", "+r": "龍",
};

export function formatUsiMoveJapanese(usi: string, pieces: Placed[], side: "b" | "w"): string {
  const prefix = side === "b" ? "▲" : "△";
  
  // Drop move: P*7f
  if (usi.includes("*")) {
    const [pieceChar, dest] = usi.split("*");
    const file = Number(dest[0]);
    const rankChar = dest[1];
    const rank = rankChar.charCodeAt(0) - "a".charCodeAt(0) + 1;
    
    const pName = PIECE_KANJI[pieceChar.toUpperCase()] || "";
    return `${prefix}${KANJI_NUM[file]}${KANJI_RANK[rank]}${pName}打`;
  }

  // Normal move: 7g7f or 7g7f+
  const srcFile = Number(usi[0]);
  const srcRank = usi[1].charCodeAt(0) - "a".charCodeAt(0) + 1;
  const dstFile = Number(usi[2]);
  const dstRank = usi[3].charCodeAt(0) - "a".charCodeAt(0) + 1;
  const promote = usi.endsWith("+");

  // Find piece at source
  // pieces coordinates: x=0..8 (9..1), y=0..8 (1..9)
  // srcFile 7 -> x = 9-7 = 2
  // srcRank 7 -> y = 7-1 = 6
  const sx = 9 - srcFile;
  const sy = srcRank - 1;
  
  const sourcePiece = pieces.find(p => p.x === sx && p.y === sy);
  let pName = "??";
  if (sourcePiece) {
    // piece code might be "P", "+P", "p", "+p"
    // We want the base name usually, but if it's already promoted, we use that name.
    // If the move is a promotion (ends in +), we append "成" to the base name (unless it's already promoted? No, you can't promote an already promoted piece).
    // Actually, if it's a promotion move, the source piece is unpromoted.
    
    // Normalize to uppercase for lookup if needed, but our map handles both
    let code = sourcePiece.piece;
    // If it's a promotion move, we use the base name + "成"
    // e.g. P -> 歩 -> 歩成
    if (promote) {
       // remove + from code if it exists (shouldn't for a promotion move)
       const base = code.replace("+", "").toUpperCase();
       pName = (PIECE_KANJI[base] || "") + "成";
    } else {
       // Not a promotion move. Could be unpromoted or already promoted.
       // e.g. +P -> と
       // e.g. P -> 歩
       // Normalize to uppercase key for map
       const key = code.startsWith("+") ? "+" + code[1].toUpperCase() : code.toUpperCase();
       pName = PIECE_KANJI[key] || "";
    }
  }

  return `${prefix}${KANJI_NUM[dstFile]}${KANJI_RANK[dstRank]}${pName}`;
}

