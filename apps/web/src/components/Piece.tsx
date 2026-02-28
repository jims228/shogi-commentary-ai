import React from "react";
import { motion } from "framer-motion";
import type { PieceCode } from "@/lib/sfen";

/** 基本駒（成っていない）の表示 */
const baseMap: Record<string, string> = {
  P: "歩", L: "香", N: "桂", S: "銀", G: "金", B: "角", R: "飛", K: "玉",
};
/** 成り駒の表示 */
const promMap: Record<string, string> = {
  P: "と", L: "杏", N: "圭", S: "全", B: "馬", R: "竜",
  // 金と玉は成らないのでフォールバック
  G: "金", K: "玉",
};

function getLabel(pc: PieceCode) {
  const promoted = pc.startsWith("+");
  const code = promoted ? pc[1] : pc[0];          // 'p' | 'P' | ...
  const upper = code.toUpperCase();               // 'P' | 'L' | ...
  return promoted ? promMap[upper] : baseMap[upper];
}

function isBlackSide(pc: PieceCode) {
  const promoted = pc.startsWith("+");
  const code = promoted ? pc[1] : pc[0];
  return code === code.toUpperCase(); // 先手=大文字
}

type PieceProps = {
  piece: PieceCode;
  x: number;
  y: number;
};

export const Piece: React.FC<PieceProps> = ({ piece, x, y }) => {
  const label = getLabel(piece);
  const black = isBlackSide(piece);
  const rotation = black ? 0 : 180;

  return (
    <motion.text
      x={10 + x * 50 + 25}
      y={10 + y * 50 + 34}
      textAnchor="middle"
      fontSize="26"
      fontFamily="serif"
      fill={black ? "#111827" : "#b91c1c"}
      initial={{ scale: 0.9, opacity: 0, rotate: rotation }}
      animate={{ scale: 1, opacity: 1, rotate: rotation }}
      transition={{ duration: 0.2 }}
      style={{ userSelect: "none", pointerEvents: "none", transformOrigin: "center" }}
    >
      {label}
    </motion.text>
  );
};
