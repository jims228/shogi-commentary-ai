"use client";

import React from "react";
import { PieceSprite } from "@/components/PieceSprite";
import type { PieceCode } from "@/lib/sfen";

const TEST_PIECES: Array<{ piece: PieceCode; x: number; y: number }> = [
  { piece: "P", x: 0, y: 0 },
  { piece: "+P", x: 1, y: 1 },
  { piece: "K", x: 2, y: 2 },
  { piece: "k", x: 3, y: 3 },
];

export default function SpriteTestPage() {
  const cellSize = 64;
  const boardSize = cellSize * 9;

  return (
    <div className="min-h-screen bg-[#f6f1e6] text-[#2b2b2b] p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold mb-2">Sprite Debug</h1>
        <p className="text-slate-600 text-sm">ベクターボード上で数枚の駒を表示して、スプライトの位置や回転を確認できます。</p>
      </div>

      <div
        className="relative border border-black/10 rounded-2xl bg-white"
        style={{ width: boardSize, height: boardSize }}
      >
        <svg width={boardSize} height={boardSize} className="absolute inset-0">
          {[...Array(10)].map((_, i) => (
            <line
              key={`v-${i}`}
              x1={i * cellSize}
              x2={i * cellSize}
              y1={0}
              y2={boardSize}
              stroke="#475569"
              strokeWidth={i === 0 || i === 9 ? 2 : 1}
            />
          ))}
          {[...Array(10)].map((_, i) => (
            <line
              key={`h-${i}`}
              y1={i * cellSize}
              y2={i * cellSize}
              x1={0}
              x2={boardSize}
              stroke="#475569"
              strokeWidth={i === 0 || i === 9 ? 2 : 1}
            />
          ))}
        </svg>
        <div className="absolute inset-0">
          {TEST_PIECES.map((p, idx) => (
            <PieceSprite key={idx} piece={p.piece} x={p.x} y={p.y} size={cellSize} />
          ))}
        </div>
      </div>

      <div>
        <p className="text-sm text-slate-600 mb-2">元画像</p>
        <img src="/images/pieces.png" alt="Pieces sprite" className="rounded-xl border border-black/10 max-w-full" />
      </div>
    </div>
  );
}
