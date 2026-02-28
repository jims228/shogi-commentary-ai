import type { PieceBase, PieceCode, Placed } from "./sfen";
import { parseBoardSFEN, STARTPOS_SFEN } from "./sfen";

export type BoardMatrix = (PieceCode | null)[][];
export type Side = "b" | "w";
export type HandsState = {
  b: Partial<Record<PieceBase, number>>;
  w: Partial<Record<PieceBase, number>>;
};

const BOARD_SIZE = 9;

const START_BOARD = placedToBoard(parseBoardSFEN(STARTPOS_SFEN));

type ParsedBasePosition = {
  baseBoard: BoardMatrix;
  startTurn: Side;
  hands: HandsState;
  moves: string[];
};

function normalizePositionCommand(command: string): string {
  const trimmed = command.trim();
  if (!trimmed) return "";

  const tokens = trimmed.split(/\s+/);
  if (!tokens.length) return "";

  if (tokens[0].toLowerCase() === "position") {
    tokens.shift();
  }

  if (!tokens.length) return "";

  if (tokens[0].toLowerCase() === "moves") {
    tokens.unshift("startpos");
  }

  return tokens.join(" ");
}

function parseBasePosition(command: string): ParsedBasePosition {
  const normalized = normalizePositionCommand(command);

  const defaultState: ParsedBasePosition = {
    baseBoard: getStartBoard(),
    startTurn: "b",
    hands: createEmptyHands(),
    moves: [],
  };

  if (!normalized) {
    return defaultState;
  }

  const tokens = normalized.split(/\s+/);
  if (!tokens.length) {
    return defaultState;
  }

  const moveIndex = tokens.findIndex((token) => token.toLowerCase() === "moves");
  const moveTokens = (moveIndex === -1 ? [] : tokens.slice(moveIndex + 1)).filter(Boolean);
  const baseTokens = moveIndex === -1 ? tokens : tokens.slice(0, moveIndex);

  if (!baseTokens.length) {
    return { ...defaultState, moves: moveTokens };
  }

  const head = baseTokens[0];
  const headLower = head.toLowerCase();

  if (headLower === "startpos") {
    return {
      baseBoard: getStartBoard(),
      startTurn: "b",
      hands: createEmptyHands(),
      moves: moveTokens,
    };
  }

  if (headLower === "sfen") {
    if (baseTokens.length < 4) {
      throw new Error("Invalid SFEN command");
    }
    const boardPart = baseTokens[1];
    const turnToken = baseTokens[2];
    const handToken = baseTokens[3] ?? "-";
    return {
      baseBoard: placedToBoard(parseBoardSFEN(boardPart)),
      startTurn: turnToken === "w" || turnToken === "W" ? "w" : "b",
      hands: parseHands(handToken),
      moves: moveTokens,
    };
  }

  throw new Error("Unsupported USI command");
}

export type ParsedUsiPosition = {
  board: BoardMatrix;
  moves: string[];
  turn: Side; // side to move AFTER applying moves
  hands: HandsState; // initial hands parsed from command
};

export type BoardTimeline = {
  boards: BoardMatrix[]; // index = ply, 0 is initial position
  hands: HandsState[]; // parallel snapshot per ply (0 = initial hands)
  moves: string[];
};

export function createEmptyBoard(): BoardMatrix {
  return Array.from({ length: BOARD_SIZE }, () => Array<PieceCode | null>(BOARD_SIZE).fill(null));
}

export function cloneBoard(board: BoardMatrix): BoardMatrix {
  return board.map((row) => row.slice());
}

export function getStartBoard(): BoardMatrix {
  return cloneBoard(START_BOARD);
}

export function placedToBoard(placed: Placed[]): BoardMatrix {
  const board = createEmptyBoard();
  placed.forEach(({ piece, x, y }) => {
    if (board[y]) board[y][x] = piece;
  });
  return board;
}

export function boardToPlaced(board: BoardMatrix): Placed[] {
  const pieces: Placed[] = [];
  board.forEach((row, y) => {
    row.forEach((cell, x) => {
      if (cell) pieces.push({ piece: cell, x, y });
    });
  });
  return pieces;
}

export function buildPositionFromUsi(usiCommand: string): ParsedUsiPosition {
  const parsed = parseBasePosition(usiCommand);
  const board = cloneBoard(parsed.baseBoard);
  const turn = playMoves(board, parsed.moves, parsed.startTurn, parsed.hands);
  // Log initial parsed hands for debugging (check if sente has pawns)
  try {
    // eslint-disable-next-line no-console
    console.log("buildPositionFromUsi: parsed.hands", parsed.hands, "senteHasPawn:", !!(parsed.hands?.b && parsed.hands.b.P && parsed.hands.b.P > 0));
  } catch (e) {
    // ignore
  }

  return { board, moves: parsed.moves, turn, hands: cloneHands(parsed.hands) };
}

export function buildBoardTimeline(usiCommand: string): BoardTimeline {
  const parsed = parseBasePosition(usiCommand);
  const runtimeBoard = cloneBoard(parsed.baseBoard);
  const runtimeHands = cloneHands(parsed.hands);
  const boards: BoardMatrix[] = [cloneBoard(runtimeBoard)];
  const hands: HandsState[] = [cloneHands(runtimeHands)];
  let turn: Side = parsed.startTurn;

  parsed.moves.forEach((move) => {
    turn = applyMove(runtimeBoard, runtimeHands, move, turn);
    boards.push(cloneBoard(runtimeBoard));
    hands.push(cloneHands(runtimeHands));
  });

  return { boards, hands, moves: parsed.moves };
}

function createEmptyHands(): HandsState {
  return { b: {}, w: {} };
}

function parseHands(token: string): HandsState {
  if (!token || token === "-") return createEmptyHands();
  const hands = createEmptyHands();
  let i = 0;
  while (i < token.length) {
    let digits = "";
    while (i < token.length && /\d/.test(token[i])) {
      digits += token[i];
      i++;
    }
    const count = digits ? parseInt(digits, 10) : 1;
    const pieceChar = token[i];
    if (!pieceChar) break;
    const side: Side = pieceChar === pieceChar.toUpperCase() ? "b" : "w";
    const base = pieceChar.toUpperCase() as PieceBase;
    hands[side][base] = (hands[side][base] ?? 0) + count;
    i++;
  }
  return hands;
}

function playMoves(board: BoardMatrix, moves: string[], startTurn: Side, hands: HandsState): Side {
  const currentHands = cloneHands(hands);
  let turn: Side = startTurn;
  for (const move of moves) {
    const next = applyMove(board, currentHands, move, turn);
    turn = next;
  }
  return turn;
}

export function cloneHands(hands: HandsState): HandsState {
  return {
    b: { ...hands.b },
    w: { ...hands.w },
  };
}

export function applyMove(board: BoardMatrix, hands: HandsState, move: string, turn: Side): Side {
  const trimmed = move.trim();
  if (!trimmed || trimmed === "resign" || trimmed === "win" || trimmed === "draw") {
    return flipTurn(turn);
  }

  if (trimmed.includes("*")) {
    applyDrop(board, hands, trimmed, turn);
    return flipTurn(turn);
  }

  applyStandardMove(board, hands, trimmed, turn);
  return flipTurn(turn);
}

function applyDrop(board: BoardMatrix, hands: HandsState, move: string, turn: Side) {
  const [pieceLetter, , fileChar, rankChar] = move;
  if (!pieceLetter || !fileChar || !rankChar) return;
  const base = pieceLetter.toUpperCase() as PieceBase;
  const available = hands[turn][base] ?? 0;
  if (available <= 0) return;
  const x = fileToX(fileChar);
  const y = rankToY(rankChar);
  if (!isOnBoard(x, y)) return;
  if (board[y]?.[x]) return;
  const placingPiece = makePieceForSide(base, turn);
  board[y][x] = placingPiece;
  hands[turn][base] = available - 1;
}

function applyStandardMove(board: BoardMatrix, hands: HandsState, move: string, turn: Side) {
  const fromX = fileToX(move[0]);
  const fromY = rankToY(move[1]);
  const toX = fileToX(move[2]);
  const toY = rankToY(move[3]);
  if ([fromX, fromY, toX, toY].some((v) => Number.isNaN(v))) return;
  if (!isOnBoard(fromX, fromY) || !isOnBoard(toX, toY)) return;

  const piece = board[fromY]?.[fromX];
  if (!piece) return;
  if (isBlackPiece(piece) !== (turn === "b")) return;

  const capture = board[toY]?.[toX];
  if (capture) {
    if (isBlackPiece(capture) === (turn === "b")) {
      // 自分の駒には移動できない
      board[fromY][fromX] = piece;
      return;
    }
    const base = demotePiece(capture).toUpperCase() as PieceBase;
    hands[turn][base] = (hands[turn][base] ?? 0) + 1;
  }

  board[fromY][fromX] = null;
  const nextPiece = move.endsWith("+") ? promotePiece(piece) : piece;
  board[toY][toX] = nextPiece;
}

function makePieceForSide(base: PieceBase, side: Side, promoted = false): PieceCode {
  const char = side === "b" ? base : base.toLowerCase();
  if (promoted) {
    return (`+${char}`) as PieceCode;
  }
  return char as PieceCode;
}

export function promotePiece(piece: PieceCode): PieceCode {
  if (piece.startsWith("+")) return piece;
  const body = piece.toUpperCase() as PieceBase;
  return makePieceForSide(body, isBlackPiece(piece) ? "b" : "w", true);
}

export function demotePiece(piece: PieceCode): PieceCode {
  if (!piece.startsWith("+")) return piece;
  const body = piece[1];
  return (body === body.toUpperCase() ? body.toUpperCase() : body.toLowerCase()) as PieceCode;
}

function isBlackPiece(piece: PieceCode): boolean {
  const body = piece.startsWith("+") ? piece[1] : piece[0];
  return body === body.toUpperCase();
}

function fileToX(fileChar: string): number {
  return 9 - Number(fileChar);
}

function rankToY(rankChar: string): number {
  return rankChar.charCodeAt(0) - "a".charCodeAt(0);
}

function isOnBoard(x: number, y: number): boolean {
  return x >= 0 && x < BOARD_SIZE && y >= 0 && y < BOARD_SIZE;
}

function flipTurn(turn: Side): Side {
  return turn === "b" ? "w" : "b";
}

export function getPieceOwner(piece: PieceCode): "sente" | "gote" {
  const body = piece.startsWith("+") ? piece[1] : piece[0];
  return body === body.toUpperCase() ? "sente" : "gote";
}
