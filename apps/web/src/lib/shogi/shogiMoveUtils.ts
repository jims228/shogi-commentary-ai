// 将棋の座標定義
// file: 筋 (1-9), rank: 段 (1-9)
export type Square = { file: number; rank: number };

/**
 * 将棋の筋・段を USI 形式 ("7g" など) に変換する
 * file: 1-9 (1が右端、9が左端)
 * rank: 1-9 (1が上端、9が下端)
 */
export function squareToUSI(square: Square): string {
  const { file, rank } = square;
  if (file < 1 || file > 9 || rank < 1 || rank > 9) {
    throw new Error(`Invalid square: ${file}, ${rank}`);
  }
  // file はそのまま数字
  // rank は a=1, b=2, ... i=9
  const rankChar = String.fromCharCode('a'.charCodeAt(0) + rank - 1);
  return `${file}${rankChar}`;
}

/**
 * USI 形式 ("7g" など) を将棋の筋・段に変換する
 */
export function usiToSquare(usi: string): Square | null {
  if (usi.length < 2) return null;
  
  const fileChar = usi[0];
  const rankChar = usi[1];
  
  const file = parseInt(fileChar, 10);
  const rank = rankChar.charCodeAt(0) - 'a'.charCodeAt(0) + 1;
  
  if (isNaN(file) || file < 1 || file > 9 || rank < 1 || rank > 9) {
    return null;
  }
  
  return { file, rank };
}
