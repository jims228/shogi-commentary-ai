import React from "react";
import { Piece } from "./Piece";
import type { Placed } from "@/lib/sfen";

const FILES = ["９","８","７","６","５","４","３","２","１"];
const RANKS = ["一","二","三","四","五","六","七","八","九"];

export const Board: React.FC<{
  pieces: Placed[];
  bestmove?: { from:{x:number;y:number}, to:{x:number;y:number} } | null;
  onSquareClick?: (x: number, y: number) => void;
  highlightSquares?: {x:number, y:number}[];
}> = ({ pieces, bestmove, onSquareClick, highlightSquares }) => {
  return (
    <div className="flex justify-center items-center py-6">
      <svg
        viewBox="0 0 470 490"
        className="shadow-soft rounded-2xl border-4 border-amber-800 bg-amber-50"
        width={470}
        height={490}
      >
        {/* 升目 */}
        {[...Array(9)].flatMap((_, y) =>
          [...Array(9)].map((_, x) => {
            const isHighlighted = highlightSquares?.some(sq => sq.x === x && sq.y === y);
            return (
            <rect
              key={`c-${x}-${y}`}
              x={10 + x * 50}
              y={10 + y * 50}
              width="50"
              height="50"
              fill={isHighlighted ? "#fcd34d" : "#fef3c7"}
              stroke="#92400e"
              strokeWidth="1.5"
              rx="2"
              ry="2"
              onClick={() => onSquareClick?.(x, y)}
              style={{ cursor: onSquareClick ? "pointer" : "default" }}
            />
          )})
        )}

        {/* ベストムーブ矢印（あれば） */}
        {bestmove && (
          <Arrow
            x1={10 + bestmove.from.x * 50 + 25}
            y1={10 + bestmove.from.y * 50 + 25}
            x2={10 + bestmove.to.x * 50 + 25}
            y2={10 + bestmove.to.y * 50 + 25}
          />
        )}

        {/* 駒 */}
        <g>
          {pieces.map((p, i) => (
            <Piece key={i} piece={p.piece} x={p.x} y={p.y} />
          ))}
        </g>

        {/* 目盛り */}
        {FILES.map((f, i) => (
          <text key={`f${i}`} x={10 + i * 50 + 25} y={480} textAnchor="middle" fontSize="13" fill="#78350f">
            {f}
          </text>
        ))}
        {RANKS.map((r, i) => (
          <text key={`r${i}`} x={2} y={10 + i * 50 + 32} textAnchor="end" fontSize="13" fill="#78350f">
            {r}
          </text>
        ))}
      </svg>
    </div>
  );
};

const Arrow: React.FC<{x1:number;y1:number;x2:number;y2:number}> = ({ x1,y1,x2,y2 }) => {
  const dx = x2 - x1, dy = y2 - y1;
  const len = Math.hypot(dx, dy) || 1;
  const ux = dx / len, uy = dy / len;
  // 矢じり
  const ah = 10, aw = 6;
  const hx = x2 - ux * ah, hy = y2 - uy * ah;
  const leftX = hx + (-uy) * aw, leftY = hy + (ux) * aw;
  const rightX = hx - (-uy) * aw, rightY = hy - (ux) * aw;

  return (
    <g>
      <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="#16a34a" strokeWidth="6" strokeOpacity="0.5" />
      <polygon points={`${x2},${y2} ${leftX},${leftY} ${rightX},${rightY}`} fill="#16a34a" fillOpacity="0.7" />
    </g>
  );
};
