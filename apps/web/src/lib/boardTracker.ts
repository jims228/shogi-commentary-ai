/** 指定手番の駒が動ける元の位置を探索するためのヘルパー */
export type Square = number; // 0..80（先手視点で左上から9x9=81マス）
export type Piece = string; // "FU"/"KY"/"KE"/"GI"/"KI"/"KA"/"HI"/"OU"
export type Color = "b" | "w"; // 手番

const FILES = 9;
const RANKS = 9;
const N_SQUARES = FILES * RANKS;

// 各駒の利き（パターン）
// dx: -8〜+8, dy: -8〜+8 の差分で利き筋を表す
// 8以上の値は「最大8マス先まで」を意味する（飛車・角・香車用）
export type PieceType = "P"|"L"|"N"|"S"|"R"|"B"|"G"|"K";
const PIECE_MOVES: Record<PieceType, Array<[number, number]>> = {
  "P": [[0, -1]], // 歩は前に1マス
  "L": [[0, -8]], // 香は前に何マスでも
  "N": [[-1, -2], [1, -2]], // 桂は前に2・横に1
  "S": [[-1, -1], [0, -1], [1, -1], [-1, 1], [1, 1]], // 銀は前3マス＋斜め後ろ
  "G": [[-1, -1], [0, -1], [1, -1], [-1, 0], [1, 0], [0, 1]], // 金は前3マス＋横＋真後ろ
  "B": [[-8, -8], [8, -8], [-8, 8], [8, 8]], // 角は斜め何マスでも
  "R": [[0, -8], [-8, 0], [8, 0], [0, 8]], // 飛は縦横何マスでも
  "K": [[-1, -1], [0, -1], [1, -1], [-1, 0], [1, 0], [-1, 1], [0, 1], [1, 1]], // 玉は周囲1マス
};

// 成駒の利き
const PROMOTED_PIECE_MOVES: Record<PieceType, Array<[number, number]>> = {
  "P": [[-1, -1], [0, -1], [1, -1], [-1, 0], [1, 0], [0, 1]], // と金
  "L": [[-1, -1], [0, -1], [1, -1], [-1, 0], [1, 0], [0, 1]], // 成香
  "N": [[-1, -1], [0, -1], [1, -1], [-1, 0], [1, 0], [0, 1]], // 成桂
  "S": [[-1, -1], [0, -1], [1, -1], [-1, 0], [1, 0], [0, 1]], // 成銀
  "B": [[-8, -8], [8, -8], [-8, 8], [8, 8], [-1, 0], [1, 0], [0, -1], [0, 1]], // 馬
  "R": [[0, -8], [-8, 0], [8, 0], [0, 8], [-1, -1], [1, -1], [-1, 1], [1, 1]], // 龍
  "G": [[-1, -1], [0, -1], [1, -1], [-1, 0], [1, 0], [0, 1]], // 金は成れない
  "K": [[-1, -1], [0, -1], [1, -1], [-1, 0], [1, 0], [-1, 1], [0, 1], [1, 1]], // 玉は成れない
};

/** 数値とアルファベットの変換テーブル */
const NUM_TO_ALPHA: Record<number, string> = {
  1: "a", 2: "b", 3: "c", 4: "d", 5: "e",
  6: "f", 7: "g", 8: "h", 9: "i"
};
const ALPHA_TO_NUM: Record<string, number> = {
  a: 1, b: 2, c: 3, d: 4, e: 5,
  f: 6, g: 7, h: 8, i: 9
};

// 1..9 → a..i（先手視点で上段が a）
export function rankNumToLetter(n: number): string {
  const L = ["", "a", "b", "c", "d", "e", "f", "g", "h", "i"];
  return L[n] ?? "";
}

// 77 → "7g"
export function toUsiSquare(file: number, rank: number): string {
  // file は 9..1、rank は 1..9 を想定
  return `${file}${rankNumToLetter(rank)}`;
}

// from(7,7) → to(7,6) → "7g7f"
export function toUsiMove(
  fromFile: number,
  fromRank: number,
  toFile: number,
  toRank: number,
  promote = false
): string {
  const base = `${toUsiSquare(fromFile, fromRank)}${toUsiSquare(toFile, toRank)}`;
  return promote ? base + "+" : base;
}

/** USI座標（"7g"など）をSquare（0..80）に変換 */
export function usiToSquare(usi: string): Square {
  if (usi.length !== 2) return -1;
  const file = 9 - Number(usi[0]);
  const rank = ALPHA_TO_NUM[usi[1].toLowerCase()] - 1;
  if (rank < 0 || rank >= RANKS) return -1;
  return file + rank * FILES;
}

/** Square（0..80）をUSI座標に変換 */
export function squareToUsi(sq: Square): string {
  if (sq < 0 || sq >= N_SQUARES) return "";
  const file = 9 - (sq % FILES);
  const rank = NUM_TO_ALPHA[Math.floor(sq / FILES) + 1];
  if (!rank) return "";
  return `${file}${rank}`;
}

/** 座標が盤面内かチェック */
function isOnBoard(sq: Square): boolean {
  return sq >= 0 && sq < N_SQUARES;
}

/** 成り判定用の定数（未使用のため削除） */

/** 基本的な盤面追跡（初期局面＋指し手列から現局面を得る） */
export class BoardTracker {
  private board: (Square | null)[]; // null=空マス, 0..80=駒のID
  private turn: Color;
  private moveCount: number;
  private pieces: Map<number, { type: PieceType; color: Color; isPromoted: boolean }>;
  private lastMove: { file: number; rank: number } | null = null;

  constructor() {
    this.board = new Array(N_SQUARES).fill(null);
    this.turn = "b"; // 先手番
    this.moveCount = 0;
    this.pieces = new Map();
  }

  /** 成り判定 */
  canPromote(piece: PieceType, from: Square, to: Square, color: Color): boolean {
    // 先手: rank 小さいほど敵陣、後手は逆
    const intoOpp = (r: number) => color === "b" ? r <= 3 : r >= 7;
    const lastTwo = (r: number) => color === "b" ? r <= 2 : r >= 8;
    const lastOne = (r: number) => color === "b" ? r === 1 : r === 9;

    const fromRank = Math.floor(from / FILES);
    const toRank = Math.floor(to / FILES);

    // 成れない駒種は除外
    if (piece === "G" || piece === "K") return false;

    // 既に成っている駒は除外
    const pieceId = this.board[from];
    if (pieceId === null) return false;
    if (this.pieces.get(pieceId)?.isPromoted) return false;

    // 成りゾーンへの移動、またはゾーン内での移動なら成り可能
    if (intoOpp(toRank)) return true;
    if (intoOpp(fromRank)) return true;

    // 特定の駒種の強制成り判定
    if (piece === "P" || piece === "L") {
      if (lastOne(toRank)) return true;
    }
    if (piece === "N") {
      if (lastTwo(toRank)) return true;
    }

    return false;
  }

  /** 駒の利き（移動可能マス）をチェック（長い利きは障害物で止まる） */
  findMoves(piece: PieceType, from: Square, color: Color): Square[] {
    const moves: Square[] = [];
    const pieceId = this.board[from];
    if (pieceId === null) return moves;
    
    const pieceInfo = this.pieces.get(pieceId);
    if (!pieceInfo) return moves;

    const patterns = pieceInfo.isPromoted ? PROMOTED_PIECE_MOVES[piece] : PIECE_MOVES[piece] || [];
    const sign = color === "b" ? 1 : -1;

    for (const [dx, dy] of patterns) {
      const longRange = Math.abs(dx) >= 8 || Math.abs(dy) >= 8;
      const maxDist = longRange ? 8 : 1;

      // 方向ベクトルの正規化（-1,0,+1）
      const ndx = dx === 0 ? 0 : dx > 0 ? 1 : -1;
      const ndy = dy === 0 ? 0 : dy > 0 ? 1 : -1;

      for (let d = 1; d <= maxDist; d++) {
        const tx = (from % FILES) + ndx * d * sign;
        const ty = Math.floor(from / FILES) + ndy * d * sign;
        const to = tx + ty * FILES;

        if (!isOnBoard(to) || tx < 0 || tx >= FILES) break;
        if (this.board[to] !== null) break; // 味方も敵も問わず、駒があれば進めない
        moves.push(to);
        if (!longRange) break;
      }
    }
    return moves;
  }

  /** 駒を動かす（手番は自動で進む） */
  makeMove(from: Square, to: Square, isPromotion = false) {
    if (!isOnBoard(from) || !isOnBoard(to)) return;
    const pieceId = this.board[from];
    if (pieceId === null) return;

    // 駒を移動
    this.board[to] = pieceId;
    this.board[from] = null;

    // 成り処理
    if (isPromotion && this.pieces.has(pieceId)) {
      const piece = this.pieces.get(pieceId)!;
      piece.isPromoted = true;
      this.pieces.set(pieceId, piece);
    }

    this.turn = this.turn === "b" ? "w" : "b";
    this.moveCount++;
  }

  /** 座標に駒を置く（初期配置用） */
  putPiece(sq: Square, pieceId: Square | null, type?: PieceType, color?: Color) {
    if (!isOnBoard(sq)) return;
    this.board[sq] = pieceId;
    if (pieceId !== null && type && color) {
      this.pieces.set(pieceId, { type, color, isPromoted: false });
    }
  }

  /** 手番と位置から、移動可能な駒の候補を探す（優先順位付き） */
  findPotentialSources(piece: PieceType, to: Square, color: Color): Square[] {
    const sources: Square[] = [];
    // 長い利きを持つ駒は逆算が必要（飛車・角・香車）
    
    for (let sq = 0; sq < N_SQUARES; sq++) {
      if (this.board[sq] === null) continue;
      const pieceId = this.board[sq]!;
      const pieceInfo = this.pieces.get(pieceId);
      if (!pieceInfo || pieceInfo.color !== color || pieceInfo.type !== piece) continue;

      const moves = this.findMoves(piece, sq, color);
      if (moves.includes(to)) {
        sources.push(sq);
      }
    }

    // 優先順位による並び替え
    return sources.sort((a, b) => {
      // 1. 移動距離が短い方を優先
      const distA = Math.abs((a % FILES) - (to % FILES)) + 
                   Math.abs(Math.floor(a / FILES) - Math.floor(to / FILES));
      const distB = Math.abs((b % FILES) - (to % FILES)) + 
                   Math.abs(Math.floor(b / FILES) - Math.floor(to / FILES));
      if (distA !== distB) return distA - distB;

      // 2. 同じ筋にある方を優先
      const sameFileA = (a % FILES) === (to % FILES);
      const sameFileB = (b % FILES) === (to % FILES);
      if (sameFileA !== sameFileB) return sameFileA ? -1 : 1;

      // 3. 同じ段にある方を優先
      const sameRankA = Math.floor(a / FILES) === Math.floor(to / FILES);
      const sameRankB = Math.floor(b / FILES) === Math.floor(to / FILES);
      if (sameRankA !== sameRankB) return sameRankA ? -1 : 1;

      return 0;
    });
  }

  /** 平手初期局面を設定 */
  setInitialPosition() {
    // 先手の駒を配置
    this.putPiece(usiToSquare("9i"), 0, "L", "b"); // 香
    this.putPiece(usiToSquare("8i"), 1, "N", "b"); // 桂
    this.putPiece(usiToSquare("7i"), 2, "S", "b"); // 銀
    this.putPiece(usiToSquare("6i"), 3, "G", "b"); // 金
    this.putPiece(usiToSquare("5i"), 4, "K", "b"); // 玉
    this.putPiece(usiToSquare("4i"), 5, "G", "b"); // 金
    this.putPiece(usiToSquare("3i"), 6, "S", "b"); // 銀
    this.putPiece(usiToSquare("2i"), 7, "N", "b"); // 桂
    this.putPiece(usiToSquare("1i"), 8, "L", "b"); // 香
    this.putPiece(usiToSquare("8h"), 9, "R", "b"); // 飛
    this.putPiece(usiToSquare("2h"), 10, "B", "b"); // 角
    // 歩を配置
    for (let i = 0; i < 9; i++) {
      this.putPiece(usiToSquare(`${9-i}g`), 11 + i, "P", "b");
    }

    // 後手の駒を配置（IDは反転）
    this.putPiece(usiToSquare("9a"), 80, "L", "w"); // 香
    this.putPiece(usiToSquare("8a"), 79, "N", "w"); // 桂
    this.putPiece(usiToSquare("7a"), 78, "S", "w"); // 銀
    this.putPiece(usiToSquare("6a"), 77, "G", "w"); // 金
    this.putPiece(usiToSquare("5a"), 76, "K", "w"); // 玉
    this.putPiece(usiToSquare("4a"), 75, "G", "w"); // 金
    this.putPiece(usiToSquare("3a"), 74, "S", "w"); // 銀
    this.putPiece(usiToSquare("2a"), 73, "N", "w"); // 桂
    this.putPiece(usiToSquare("1a"), 72, "L", "w"); // 香
    this.putPiece(usiToSquare("8b"), 71, "R", "w"); // 飛
    this.putPiece(usiToSquare("2b"), 70, "B", "w"); // 角
    // 歩を配置
    for (let i = 0; i < 9; i++) {
      this.putPiece(usiToSquare(`${9-i}c`), 69 - i, "P", "w");
    }
  }
}