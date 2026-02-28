export type PieceType = "P"|"L"|"N"|"S"|"R"|"B"|"G"|"K";
export type Turn = "black"|"white";

/** 暗黙の成り判定（歩、香、桂の強制成りなど） */
export function implicitPromotionAllowed(
  piece: PieceType,
  turn: Turn,
  fromRank: number,
  toRank: number
): boolean {
  // 先手: rank 小さいほど敵陣、後手は逆
  const intoOpp = (r: number) => turn === "black" ? r <= 3 : r >= 7;
  const lastTwo = (r: number) => turn === "black" ? r <= 2 : r >= 8;
  const lastOne = (r: number) => turn === "black" ? r === 1 : r === 9;

  // 「そのままだと次の手が存在しない」系は強制的に成りやすい
  if (piece === "P" || piece === "L") {
    if (lastOne(toRank)) return true;        // 歩・香 1段（後手は9段）へ
    if (intoOpp(fromRank) || intoOpp(toRank)) return true;
  }
  if (piece === "N") {
    if (lastTwo(toRank)) return true;        // 桂 1,2段（後手は8,9段）へ
    if (intoOpp(fromRank) || intoOpp(toRank)) return true;
  }
  if (piece === "S" || piece === "B" || piece === "R") {
    if (intoOpp(fromRank) || intoOpp(toRank)) return true;
  }
  return false;
}