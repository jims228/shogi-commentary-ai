import { BoardTracker, usiToSquare } from '../boardTracker';

describe('BoardTracker - 成駒の動き', () => {
  let board: BoardTracker;

  beforeEach(() => {
    board = new BoardTracker();
  });

  test('歩の成り', () => {
    // 歩を配置して成る
    board.putPiece(usiToSquare("5e"), 0, "P", "b");
    expect(board.canPromote("P", usiToSquare("5e"), usiToSquare("5d"), "b")).toBe(true);
    
    // 実際に成る
    board.makeMove(usiToSquare("5e"), usiToSquare("5d"), true);

    // と金の動きを確認
    const moves = board.findMoves("P", usiToSquare("5d"), "b");
    expect(moves).toContain(usiToSquare("5c")); // 前
    expect(moves).toContain(usiToSquare("4d")); // 左
    expect(moves).toContain(usiToSquare("6d")); // 右
    expect(moves).toContain(usiToSquare("5e")); // 後ろ
    expect(moves).toContain(usiToSquare("4c")); // 左前
    expect(moves).toContain(usiToSquare("6c")); // 右前
  });

  test('角の成り', () => {
    // 角を配置して成る
    board.putPiece(usiToSquare("5e"), 0, "B", "b");
    board.makeMove(usiToSquare("5e"), usiToSquare("5d"), true);

    // 馬の動きを確認
    const moves = board.findMoves("B", usiToSquare("5d"), "b");
    // 斜め方向の動き（長い利き）
    expect(moves).toContain(usiToSquare("4c")); // 左前
    expect(moves).toContain(usiToSquare("6c")); // 右前
    expect(moves).toContain(usiToSquare("4e")); // 左後ろ
    expect(moves).toContain(usiToSquare("6e")); // 右後ろ
    // 十字方向の動き（1マス）
    expect(moves).toContain(usiToSquare("5c")); // 前
    expect(moves).toContain(usiToSquare("4d")); // 左
    expect(moves).toContain(usiToSquare("6d")); // 右
    expect(moves).toContain(usiToSquare("5e")); // 後ろ
  });

  test('飛車の成り', () => {
    // 飛車を配置して成る
    board.putPiece(usiToSquare("5e"), 0, "R", "b");
    board.makeMove(usiToSquare("5e"), usiToSquare("5d"), true);

    // 龍の動きを確認
    const moves = board.findMoves("R", usiToSquare("5d"), "b");
    // 十字方向の動き（長い利き）
    expect(moves).toContain(usiToSquare("5c")); // 前
    expect(moves).toContain(usiToSquare("4d")); // 左
    expect(moves).toContain(usiToSquare("6d")); // 右
    expect(moves).toContain(usiToSquare("5e")); // 後ろ
    // 斜め方向の動き（1マス）
    expect(moves).toContain(usiToSquare("4c")); // 左前
    expect(moves).toContain(usiToSquare("6c")); // 右前
    expect(moves).toContain(usiToSquare("4e")); // 左後ろ
    expect(moves).toContain(usiToSquare("6e")); // 右後ろ
  });
});