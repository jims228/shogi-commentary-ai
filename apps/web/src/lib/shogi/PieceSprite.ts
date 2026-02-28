import type { CSSProperties } from "react";

export type PieceType = 
  | "FU" | "KY" | "KE" | "GI" | "KI" | "KA" | "HI" | "OU"
  | "TO" | "NY" | "NK" | "NG" | "UM" | "RY";

export type Owner = "black" | "white";

export const PIECE_WIDTH = 60;
export const PIECE_HEIGHT = 64;
export const SPRITE_URL = "https://kishin-analytics.heroz.jp/static/img/piece.png";
const SPRITE_COLS = 14;
const SPRITE_ROWS = 1;

// スプライト画像内の位置定義 (x, y はインデックス。実際のpxは index * width/height)
// 仮定: 画像は横に並んでいる、またはグリッド状。
// ここでは一般的な並び順（歩、香、桂、銀、金、角、飛、王...）を仮定して定義します。
// 実際の画像に合わせて修正してください。
const SPRITE_MAP: Record<PieceType, { x: number; y: number }> = {
  "FU": { x: 0, y: 0 },
  "KY": { x: 1, y: 0 },
  "KE": { x: 2, y: 0 },
  "GI": { x: 3, y: 0 },
  "KI": { x: 4, y: 0 },
  "KA": { x: 5, y: 0 },
  "HI": { x: 6, y: 0 },
  "OU": { x: 7, y: 0 },
  "TO": { x: 8, y: 0 }, // 成歩
  "NY": { x: 9, y: 0 }, // 成香
  "NK": { x: 10, y: 0 }, // 成桂
  "NG": { x: 11, y: 0 }, // 成銀
  "UM": { x: 12, y: 0 }, // 馬
  "RY": { x: 13, y: 0 }, // 龍
};

export const getSpriteStyle = (type: PieceType, promoted: boolean = false): CSSProperties => {
  // 成り駒の処理: type自体が成駒の場合はそのまま、そうでない場合は変換マップを通すなどのロジックが必要ですが、
  // 今回は type に "TO" などが含まれている前提で、promoted フラグがある場合は type を変換するヘルパーを用意します。
  let targetType = type;
  if (promoted) {
    const promoteMap: Partial<Record<PieceType, PieceType>> = {
      "FU": "TO", "KY": "NY", "KE": "NK", "GI": "NG", "KA": "UM", "HI": "RY"
    };
    if (promoteMap[type]) {
      targetType = promoteMap[type]!;
    }
  }

  const pos = SPRITE_MAP[targetType] || { x: 0, y: 0 };
  const scale = "var(--piece-scale, 1)";

  return {
    backgroundImage: `url(${SPRITE_URL})`,
    backgroundPosition: `calc(-${pos.x * PIECE_WIDTH}px * ${scale}) calc(-${pos.y * PIECE_HEIGHT}px * ${scale})`,
    backgroundSize: `calc(${SPRITE_COLS * PIECE_WIDTH}px * ${scale}) calc(${SPRITE_ROWS * PIECE_HEIGHT}px * ${scale})`,
    width: `calc(${PIECE_WIDTH}px * ${scale})`,
    height: `calc(${PIECE_HEIGHT}px * ${scale})`,
    backgroundRepeat: "no-repeat",
    // 拡大縮小時のぼやけ防止
    imageRendering: "pixelated", 
  };
};
